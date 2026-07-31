"""MetaTrader 5 broker gateway.

v2.4 — Module 3 + Module 4 + Module 7
-------------------------------------
Single dispatch point for every order the strategy can emit:

  * ``MARKET`` -- market deal on the KOD candle close (two-step ECN dispatch)
  * ``LIMIT``  -- pending limit at the sweep level, or at the FVG 50%
                  consequent encroachment, with an optional expiration
  * ``STOP``   -- pending stop for breakout/continuation entries

plus the position-maintenance operations the trade manager needs:
:meth:`modify_position`, :meth:`partial_close` and :meth:`close_position`.

Spread policy (changed in v2.4)
-------------------------------
The previous revision enforced a **2.5-pip absolute cap** on every order, in
addition to the 15%-of-risk-distance ratio gate. That cap was asset-class
blind: it compared a raw price spread against ``2.5 * pip_size``, where
``pip_size`` derives purely from ``spec.digits``. For anything that is not an
FX pair the threshold is unreachable by construction — live measurement gave
XAGUSD 3.0 pips, XAUUSD 24, DE30 16, US30 35, JP225 71, HK50 148, BTCUSD 1000,
and the audit log showed **3,212 of 3,243 rejections (99.0%)** were this single
check. Every index, metal and crypto symbol was permanently unreachable.

The absolute cap is now **disabled by default**. The ratio gate is retained as
the sole spread control, because it is the economically meaningful one: what
matters is the spread *relative to the stop distance you are risking*, which
self-scales across asset classes without per-class magic numbers. The absolute
cap can still be re-enabled for a specific deployment by setting the
``MT5_MAX_SPREAD_PIPS`` environment variable.

Reliability
-----------
``order_send`` is wrapped in :meth:`_order_send_with_retry`, which retries
transient broker conditions (requote, price changed/off, timeout, connection
loss, throttling) with exponential backoff, re-pricing market orders on each
attempt, and renegotiates the filling mode on ``TRADE_RETCODE_INVALID_FILL``
instead of failing outright.
"""

from __future__ import annotations

import importlib
import logging
import os
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

logger = logging.getLogger("broker")


def _env_decimal(name: str, default: str | None) -> Decimal | None:
    """Read a Decimal from the environment; ``None`` disables the control."""
    raw = os.getenv(name)
    if raw is None:
        return Decimal(default) if default is not None else None
    raw = raw.strip()
    if raw == "" or raw.lower() in {"none", "off", "disabled"}:
        return None
    try:
        return Decimal(raw)
    except Exception:
        logger.warning("Invalid %s=%r; ignoring this control.", name, raw)
        return None


# Absolute spread cap in pips. Disabled by default -- see the module docstring.
# Set MT5_MAX_SPREAD_PIPS=2.5 to restore the old FX-only behaviour.
MAX_SPREAD_PIPS: Decimal | None = _env_decimal("MT5_MAX_SPREAD_PIPS", None)

# Spread must not exceed this fraction of the entry-to-stop distance.
MAX_SPREAD_RISK_RATIO: Decimal = _env_decimal("MT5_MAX_SPREAD_RISK_RATIO", "0.15")

# Default magic number identifying this strategy's orders at the broker.
DEFAULT_MAGIC = int(os.getenv("MT5_MAGIC_NUMBER", "260628"))

# --- MT5 trade server return codes ----------------------------------------
RETCODE_REQUOTE = 10004
RETCODE_PLACED = 10008           # pending order registered
RETCODE_DONE = 10009             # request completed
RETCODE_DONE_PARTIAL = 10010     # partially filled
RETCODE_TIMEOUT = 10012
RETCODE_PRICE_CHANGED = 10020
RETCODE_PRICE_OFF = 10021
RETCODE_TOO_MANY_REQUESTS = 10024
RETCODE_INVALID_FILL = 10030
RETCODE_CONNECTION = 10031

SUCCESS_RETCODES = frozenset({RETCODE_PLACED, RETCODE_DONE, RETCODE_DONE_PARTIAL})

# Transient conditions worth retrying with a refreshed price.
RETRYABLE_RETCODES = frozenset({
    RETCODE_REQUOTE,
    RETCODE_TIMEOUT,
    RETCODE_PRICE_CHANGED,
    RETCODE_PRICE_OFF,
    RETCODE_TOO_MANY_REQUESTS,
    RETCODE_CONNECTION,
})

ORDER_SEND_MAX_ATTEMPTS = int(os.getenv("MT5_ORDER_MAX_ATTEMPTS", "3"))
ORDER_SEND_BACKOFF_SECONDS = float(os.getenv("MT5_ORDER_BACKOFF_SECONDS", "0.35"))

# Symbol filling-mode bit flags reported by ``symbol_info().filling_mode``.
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2


@dataclass(frozen=True)
class BrokerOrderRequest:
    symbol: str
    direction: str
    volume: Decimal
    price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    deviation: int = 20
    order_type: str = "MARKET"
    expiration: int | None = None
    is_pit_open: bool | None = None
    # Broker-side strategy identifier. Defaulted so existing constructions in
    # run_mt5_engine.py keep working unchanged.
    magic: int = DEFAULT_MAGIC
    comment: str = "RomeoTPT"


class SpreadRejection(RuntimeError):
    """Raised when spread protection vetoes an order."""


class OrderSendError(RuntimeError):
    """Raised when ``order_send`` fails after exhausting all retries."""


class MT5Client:
    """MT5 broker client with spread protection, retries and order placement."""

    def __init__(self, login: int, password: str, server: str, path: str | None = None):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.last_tick_time = 0
        self.last_tick_price = 0
        self.is_connected = False
        self.reconnect_attempts = 0
        self.mt5 = importlib.import_module("MetaTrader5")

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        """Initialise the terminal link.

        Returns True on success. Previously this returned ``None``, which meant
        ``if not self.client.connect(): return`` in ScaleOutEngine was always
        true -- the scale-out / breakeven pass silently aborted on every cycle
        and stop losses were never moved to breakeven at TP1.
        """
        if not self.mt5.initialize(
            path=self.path, login=self.login, password=self.password, server=self.server
        ):
            self.is_connected = False
            raise ConnectionError(f"MT5 initialization failed: {self.mt5.last_error()}")
        self.is_connected = True
        self.reconnect_attempts = 0
        return True

    def shutdown(self) -> None:
        self.mt5.shutdown()
        self.is_connected = False

    def ensure_connected(self) -> bool:
        """Verify the IPC link, reconnecting with exponential backoff if needed."""
        if getattr(self, "is_connected", False):
            try:
                if self.mt5.account_info() is not None:
                    self.reconnect_attempts = 0
                    return True
            except Exception:
                pass
            self.is_connected = False

        self.reconnect_attempts = getattr(self, "reconnect_attempts", 0) + 1
        delay = min(1.0 * (2 ** (self.reconnect_attempts - 1)), 30.0)
        logger.warning(
            "MT5 IPC link down (attempt %d); reconnecting in %.1fs. last_error=%s",
            self.reconnect_attempts, delay, self.mt5.last_error(),
        )
        time.sleep(delay)
        if self.mt5.initialize(
            path=self.path, login=self.login, password=self.password, server=self.server
        ):
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info("MT5 IPC link re-established.")
            return True
        logger.error("MT5 reconnect failed: %s", self.mt5.last_error())
        return False

    def account_info(self) -> dict:
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"Cannot read MT5 account info: {self.mt5.last_error()}")
        return info._asdict()

    # ------------------------------------------------------------------ #
    # Symbol helpers
    # ------------------------------------------------------------------ #

    def _spec(self, symbol: str):
        spec = self.mt5.symbol_info(symbol)
        if spec is None:
            raise RuntimeError(f"No symbol info for {symbol}: {self.mt5.last_error()}")
        return spec

    def _pip_size(self, spec) -> Decimal:
        point = Decimal(str(spec.point if spec.point else "0.00001"))
        return point * Decimal("10") if spec.digits in (3, 5) else point

    def _resolve_filling_mode(self, spec, *, pending: bool) -> int:
        """Choose a filling mode the symbol actually supports.

        ``spec.filling_mode`` is a bitmask of ``SYMBOL_FILLING_FOK`` (1) and
        ``SYMBOL_FILLING_IOC`` (2). Sending an unsupported mode returns
        ``TRADE_RETCODE_INVALID_FILL`` (10030) and the order is rejected, which
        the previous hard-coded ``ORDER_FILLING_IOC`` / ``ORDER_FILLING_RETURN``
        made unavoidable on brokers that do not offer those modes.
        """
        supported = int(getattr(spec, "filling_mode", 0) or 0)

        if pending:
            # Pending orders rest in the book; RETURN is the correct semantic
            # and is accepted regardless of the deal-filling bitmask.
            return self.mt5.ORDER_FILLING_RETURN

        if supported & SYMBOL_FILLING_IOC:
            return self.mt5.ORDER_FILLING_IOC
        if supported & SYMBOL_FILLING_FOK:
            return self.mt5.ORDER_FILLING_FOK
        return self.mt5.ORDER_FILLING_RETURN

    def _fallback_filling_modes(self, current: int, *, pending: bool) -> list[int]:
        """Remaining filling modes to try after ``TRADE_RETCODE_INVALID_FILL``."""
        order = [
            self.mt5.ORDER_FILLING_IOC,
            self.mt5.ORDER_FILLING_FOK,
            self.mt5.ORDER_FILLING_RETURN,
        ]
        if pending:
            order = [self.mt5.ORDER_FILLING_RETURN, self.mt5.ORDER_FILLING_IOC,
                     self.mt5.ORDER_FILLING_FOK]
        return [m for m in order if m != current]

    # ------------------------------------------------------------------ #
    # Spread safety
    # ------------------------------------------------------------------ #

    def _check_spread_safety(self, symbol: str, price: float, stop_loss: float | None) -> None:
        """Reject the order if the spread is economically unsafe.

        Sole active control is the ratio gate: the raw spread must not exceed
        ``MAX_SPREAD_RISK_RATIO`` of the entry-to-stop distance. The absolute
        pip cap is applied only when ``MT5_MAX_SPREAD_PIPS`` is configured.
        """
        spec = self.mt5.symbol_info(symbol)
        if not spec:
            logger.warning("No symbol info for %s, skipping spread check", symbol)
            return

        point = Decimal(str(spec.point if spec.point else "0.00001"))
        spread_points = Decimal(str(spec.spread if spec.spread else "5"))
        raw_spread = spread_points * point
        pip_size = self._pip_size(spec)
        spread_pips = raw_spread / pip_size if pip_size > 0 else Decimal("0")

        if MAX_SPREAD_PIPS is not None and raw_spread > MAX_SPREAD_PIPS * pip_size:
            raise SpreadRejection(
                f"SPREAD REJECTED [{symbol}]: raw spread {float(raw_spread):.6f} "
                f"({int(spread_points)} points / {float(spread_pips):.2f} pips) exceeds "
                f"the configured {MAX_SPREAD_PIPS} pip absolute cap."
            )

        if stop_loss is not None and MAX_SPREAD_RISK_RATIO is not None:
            risk_dist = abs(Decimal(str(price)) - Decimal(str(stop_loss)))
            if risk_dist > 0 and raw_spread / risk_dist > MAX_SPREAD_RISK_RATIO:
                raise SpreadRejection(
                    f"SPREAD REJECTED [{symbol}]: raw spread {float(raw_spread):.6f} exceeds "
                    f"{MAX_SPREAD_RISK_RATIO:.0%} of risk distance ({float(risk_dist):.6f}). "
                    f"Ratio: {float(raw_spread / risk_dist):.2%}"
                )

        logger.info(
            "Spread check PASSED [%s]: spread=%.6f (%d points / %.2f pips), pip=%.6f",
            symbol, float(raw_spread), int(spread_points), float(spread_pips), float(pip_size),
        )

    # ------------------------------------------------------------------ #
    # Resilient order_send
    # ------------------------------------------------------------------ #

    def _order_send_with_retry(self, build_request, *, label: str, pending: bool = False) -> dict:
        """Send an order, retrying transient broker conditions with backoff.

        Args:
            build_request: Callable taking ``(attempt, filling_mode)`` and
                returning a fresh MT5 request dict. It is re-invoked on every
                attempt so market orders re-price against the current tick
                instead of resubmitting a stale, guaranteed-to-requote price.
            label: Short description used in log lines.
            pending: True for pending orders, which changes filling-mode order.

        Returns:
            The MT5 result as a dict, with ``attempts`` and ``latency_ms`` added.

        Raises:
            OrderSendError: if every attempt failed.
        """
        filling_mode: int | None = None
        last_detail = "no attempt made"
        started = time.perf_counter()

        for attempt in range(1, ORDER_SEND_MAX_ATTEMPTS + 1):
            request = build_request(attempt, filling_mode)
            if filling_mode is None:
                filling_mode = request.get("type_filling")

            call_started = time.perf_counter()
            result = self.mt5.order_send(request)
            call_ms = (time.perf_counter() - call_started) * 1000.0

            if result is None:
                err = self.mt5.last_error()
                last_detail = f"order_send returned None: {err}"
                logger.warning(
                    "%s attempt %d/%d failed in %.0fms -- %s",
                    label, attempt, ORDER_SEND_MAX_ATTEMPTS, call_ms, last_detail,
                )
                # A None result is usually a dead IPC link; try to recover.
                self.is_connected = False
                if attempt < ORDER_SEND_MAX_ATTEMPTS:
                    self.ensure_connected()
                    continue
                break

            retcode = int(getattr(result, "retcode", -1))
            if retcode in SUCCESS_RETCODES:
                out = result._asdict()
                out["attempts"] = attempt
                out["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
                logger.info(
                    "%s ACCEPTED retcode=%s attempts=%d latency=%.0fms order=%s deal=%s",
                    label, retcode, attempt, out["latency_ms"],
                    out.get("order"), out.get("deal"),
                )
                return out

            last_detail = f"retcode={retcode} comment={getattr(result, 'comment', '')!r}"

            if retcode == RETCODE_INVALID_FILL:
                alternatives = self._fallback_filling_modes(filling_mode, pending=pending)
                if alternatives:
                    logger.warning(
                        "%s attempt %d rejected with INVALID_FILL (mode=%s); "
                        "renegotiating to mode=%s",
                        label, attempt, filling_mode, alternatives[0],
                    )
                    filling_mode = alternatives[0]
                    continue

            if retcode in RETRYABLE_RETCODES and attempt < ORDER_SEND_MAX_ATTEMPTS:
                delay = ORDER_SEND_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "%s attempt %d/%d transient (%s); retrying in %.2fs",
                    label, attempt, ORDER_SEND_MAX_ATTEMPTS, last_detail, delay,
                )
                time.sleep(delay)
                continue

            # Permanent rejection -- surface it to the caller immediately.
            out = result._asdict()
            out["attempts"] = attempt
            out["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
            logger.error("%s REJECTED (permanent) %s", label, last_detail)
            return out

        raise OrderSendError(f"{label} failed after {ORDER_SEND_MAX_ATTEMPTS} attempts: {last_detail}")

    # ------------------------------------------------------------------ #
    # Order placement
    # ------------------------------------------------------------------ #

    def place_order(self, req: BrokerOrderRequest) -> dict:
        """Dispatch an order according to ``req.order_type``.

        This is the entry point used by the execution loop. Returns the MT5
        result as a dict; callers check ``retcode in (10008, 10009)``.
        """
        order_type = (req.order_type or "MARKET").upper()
        if order_type == "LIMIT":
            return self.place_limit_order(req)
        if order_type == "STOP":
            return self.place_stop_order(req)
        if order_type in ("MARKET", "DEAL"):
            return self.place_market_order(req)
        raise ValueError(f"Unsupported order_type: {req.order_type!r}")

    def _place_pending(self, req: BrokerOrderRequest, *, stop: bool) -> dict:
        """Shared implementation for LIMIT and STOP pending orders.

        Unlike a market deal, a pending order rests away from the current
        price, so SL/TP can be attached in the same request without tripping
        Error 130 (invalid stops).
        """
        kind = "STOP" if stop else "LIMIT"
        if req.price is None:
            raise ValueError(f"{kind} order requires an entry price")

        spec = self._spec(req.symbol)
        digits = spec.digits if spec.digits else 5

        price = round(float(req.price), digits)
        sl = round(float(req.stop_loss), digits) if req.stop_loss else 0.0
        tp = round(float(req.take_profit), digits) if req.take_profit else 0.0

        self._check_spread_safety(req.symbol, price, sl if sl > 0 else None)

        if stop:
            typ = (self.mt5.ORDER_TYPE_BUY_STOP if req.direction == "BUY"
                   else self.mt5.ORDER_TYPE_SELL_STOP)
        else:
            typ = (self.mt5.ORDER_TYPE_BUY_LIMIT if req.direction == "BUY"
                   else self.mt5.ORDER_TYPE_SELL_LIMIT)

        default_fill = self._resolve_filling_mode(spec, pending=True)

        def build(attempt: int, filling_mode: int | None) -> dict:
            request = {
                "action": self.mt5.TRADE_ACTION_PENDING,
                "symbol": req.symbol,
                "volume": float(req.volume),
                "type": typ,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": req.deviation,
                "magic": int(req.magic),
                "type_filling": filling_mode if filling_mode is not None else default_fill,
                "comment": f"{req.comment} {kind}"[:31],
            }
            if req.expiration:
                request["type_time"] = self.mt5.ORDER_TIME_SPECIFIED
                request["expiration"] = int(req.expiration)
            else:
                request["type_time"] = self.mt5.ORDER_TIME_GTC
            return request

        label = (f"{kind} order [{req.symbol}] {req.direction} {float(req.volume):.2f} "
                 f"@ {price} sl={sl} tp={tp}")
        result_dict = self._order_send_with_retry(build, label=label, pending=True)
        result_dict["entry_mode"] = kind
        return result_dict

    def place_limit_order(self, req: BrokerOrderRequest) -> dict:
        """Pending limit entry — sweep level or FVG 50% consequent encroachment."""
        return self._place_pending(req, stop=False)

    def place_stop_order(self, req: BrokerOrderRequest) -> dict:
        """Pending stop entry — breakout / continuation above the displacement."""
        return self._place_pending(req, stop=True)

    def place_market_order(self, req: BrokerOrderRequest) -> dict:
        """Two-step ECN market dispatch with an emergency safety net."""
        spec = self._spec(req.symbol)
        digits = spec.digits if spec.digits else 5

        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")

        self.last_tick_time = tick.time
        self.last_tick_price = (tick.bid + tick.ask) / 2

        typ = (self.mt5.ORDER_TYPE_BUY if req.direction == "BUY"
               else self.mt5.ORDER_TYPE_SELL)
        price = round(tick.ask if req.direction == "BUY" else tick.bid, digits)
        sl = round(float(req.stop_loss), digits) if req.stop_loss else 0.0
        tp = round(float(req.take_profit), digits) if req.take_profit else 0.0

        self._check_spread_safety(req.symbol, price, sl if sl > 0 else None)

        default_fill = self._resolve_filling_mode(spec, pending=False)

        def build(attempt: int, filling_mode: int | None) -> dict:
            # Re-price on every retry: resubmitting a stale price is the single
            # most common cause of an endless requote loop.
            live = self.mt5.symbol_info_tick(req.symbol)
            px = price
            if live is not None:
                px = round(live.ask if req.direction == "BUY" else live.bid, digits)
            return {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": req.symbol,
                "volume": float(req.volume),
                "type": typ,
                "price": float(px),
                # Step 1 deliberately omits SL/TP -- attaching them to the deal
                # trips Error 130 on ECN feeds where the fill price is unknown
                # until execution completes.
                "sl": 0.0,
                "tp": 0.0,
                "deviation": req.deviation,
                "magic": int(req.magic),
                "type_filling": filling_mode if filling_mode is not None else default_fill,
                "comment": f"{req.comment} MARKET"[:31],
            }

        label = (f"MARKET order [{req.symbol}] {req.direction} {float(req.volume):.2f} "
                 f"@ ~{price}")
        result_dict = self._order_send_with_retry(build, label=label, pending=False)
        result_dict["entry_mode"] = "MARKET"

        if int(result_dict.get("retcode", -1)) not in SUCCESS_RETCODES:
            return result_dict

        ticket = result_dict.get("order") or None

        # Step 2: attach SL/TP by modifying the resulting position.
        if ticket and (sl > 0 or tp > 0):
            modify_result = self.mt5.order_send({
                "action": self.mt5.TRADE_ACTION_SLTP,
                "symbol": req.symbol,
                "position": int(ticket),
                "sl": sl,
                "tp": tp,
                "magic": int(req.magic),
            })
            if modify_result and modify_result.retcode in SUCCESS_RETCODES:
                result_dict["sltp_attached"] = True
            else:
                # Step 3: emergency safety net -- an unprotected position is
                # worse than no position, so close it immediately.
                err_code = modify_result.retcode if modify_result else "NO_RESULT"
                result_dict["sltp_attach_error"] = err_code
                logger.error(
                    "SL/TP attach FAILED for %s ticket %s (%s) -- emergency closing",
                    req.symbol, ticket, err_code,
                )
                try:
                    close_res = self.close_position(int(ticket), reason="sltp_attach_failed")
                    result_dict["emergency_closed"] = close_res.get("retcode")
                except Exception as close_err:
                    result_dict["emergency_close_error"] = str(close_err)
                    logger.critical(
                        "UNPROTECTED POSITION %s on %s -- emergency close failed: %s",
                        ticket, req.symbol, close_err,
                    )
                result_dict["note"] = f"Safety close: SL/TP modify returned {err_code}"
        else:
            result_dict["sltp_skipped"] = True

        return result_dict

    # ------------------------------------------------------------------ #
    # Position maintenance
    # ------------------------------------------------------------------ #

    def modify_position(self, ticket: int, stop_loss: Decimal | float,
                        take_profit: Decimal | float) -> dict:
        """Move SL/TP on an open position — used for breakeven at TP1."""
        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "sl": float(stop_loss),
            "tp": float(take_profit),
        })
        if result is None:
            raise RuntimeError(f"MT5 modify failed: {self.mt5.last_error()}")
        return result._asdict()

    def _find_position(self, ticket: int):
        positions = self.mt5.positions_get(ticket=int(ticket))
        if not positions:
            raise RuntimeError(
                f"Position {ticket} not found: {self.mt5.last_error()}"
            )
        return positions[0]

    def close_position(self, ticket: int, *, deviation: int = 50,
                       reason: str = "manual") -> dict:
        """Fully close an open position by ticket."""
        return self._close_volume(ticket, volume=None, deviation=deviation, reason=reason)

    def partial_close(self, ticket: int, volume: Decimal | float, *,
                      deviation: int = 50, reason: str = "partial") -> dict:
        """Close part of an open position — used for TP1 scale-outs.

        The requested volume is clamped to the symbol's volume step and
        minimum, and to the position's remaining volume. If the remainder
        after the partial would fall below the symbol minimum, the position is
        closed in full instead, because brokers reject orders that would leave
        a sub-minimum residual.
        """
        return self._close_volume(ticket, volume=Decimal(str(volume)),
                                  deviation=deviation, reason=reason)

    def _close_volume(self, ticket: int, volume: Decimal | None, *,
                      deviation: int, reason: str) -> dict:
        pos = self._find_position(ticket)
        symbol = pos.symbol
        spec = self._spec(symbol)

        step = Decimal(str(spec.volume_step if spec.volume_step else "0.01"))
        vol_min = Decimal(str(spec.volume_min if spec.volume_min else "0.01"))
        open_vol = Decimal(str(pos.volume))

        if volume is None:
            close_vol = open_vol
        else:
            # Quantise down to a legal volume step.
            close_vol = (volume / step).to_integral_value(rounding=ROUND_DOWN) * step
            close_vol = max(vol_min, min(close_vol, open_vol))
            remainder = open_vol - close_vol
            if remainder > 0 and remainder < vol_min:
                logger.info(
                    "Partial close of %s on %s would leave %s (< min %s); closing in full.",
                    close_vol, symbol, remainder, vol_min,
                )
                close_vol = open_vol

        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {symbol}")

        is_buy = pos.type == self.mt5.POSITION_TYPE_BUY
        close_type = self.mt5.ORDER_TYPE_SELL if is_buy else self.mt5.ORDER_TYPE_BUY
        default_fill = self._resolve_filling_mode(spec, pending=False)

        def build(attempt: int, filling_mode: int | None) -> dict:
            live = self.mt5.symbol_info_tick(symbol) or tick
            px = live.bid if is_buy else live.ask
            return {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(close_vol),
                "type": close_type,
                "position": int(ticket),
                "price": float(px),
                "deviation": deviation,
                "magic": int(getattr(pos, "magic", DEFAULT_MAGIC)),
                "type_filling": filling_mode if filling_mode is not None else default_fill,
                "comment": f"close:{reason}"[:31],
            }

        full = close_vol >= open_vol
        label = (f"{'CLOSE' if full else 'PARTIAL CLOSE'} [{symbol}] ticket={ticket} "
                 f"vol={float(close_vol):.2f}/{float(open_vol):.2f} reason={reason}")
        out = self._order_send_with_retry(build, label=label, pending=False)
        out["closed_volume"] = float(close_vol)
        out["remaining_volume"] = float(open_vol - close_vol)
        out["full_close"] = full
        return out
