"""MetaTrader 5 broker gateway.

v2.3 — Module 3 + Module 4
--------------------------
``run_mt5_engine.py`` has always called ``client.place_order(req)``, but this
class only ever defined ``place_market_order``. Any setup that reached the
execution branch would have died on ``AttributeError: 'MT5Client' object has no
attribute 'place_order'``. Nothing reached it, so the defect stayed latent.

``place_order`` is implemented here as the single dispatch point for all three
entry types required by Module 4:

  * ``MARKET`` -- market order on KOD candle close (two-step ECN dispatch)
  * ``LIMIT``  -- direct limit at the sweep level, or at the FVG 50%
                  consequent encroachment, with an optional expiration

Every path runs through :meth:`_check_spread_safety` first, so the 2.5-pip
absolute cap and the 15%-of-risk-distance cap apply uniformly.
"""

from dataclasses import dataclass
from decimal import Decimal
import importlib
import logging

logger = logging.getLogger("broker")

# Module 3 spread protection thresholds.
MAX_SPREAD_PIPS = Decimal("2.5")
MAX_SPREAD_RISK_RATIO = Decimal("0.15")

# MT5 retcodes that indicate the request was accepted.
RETCODE_PLACED = 10008   # TRADE_RETCODE_PLACED  (pending order registered)
RETCODE_DONE = 10009     # TRADE_RETCODE_DONE    (request completed)


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


class SpreadRejection(RuntimeError):
    """Raised when Module 3 spread protection vetoes an order."""


class MT5Client:
    """MT5 broker client with spread protection and order placement."""

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
        import time as _t

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
        _t.sleep(delay)
        if self.mt5.initialize(
            path=self.path, login=self.login, password=self.password, server=self.server
        ):
            self.is_connected = True
            self.reconnect_attempts = 0
            return True
        return False

    def account_info(self) -> dict:
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"Cannot read MT5 account info: {self.mt5.last_error()}")
        return info._asdict()

    # ------------------------------------------------------------------ #
    # Module 3 — spread safety
    # ------------------------------------------------------------------ #

    def _pip_size(self, spec) -> Decimal:
        point = Decimal(str(spec.point if spec.point else "0.00001"))
        return point * Decimal("10") if spec.digits in (3, 5) else point

    def _check_spread_safety(self, symbol: str, price: float, stop_loss: float | None) -> None:
        """Reject the order if the spread is unsafe.

        1. raw spread must not exceed 2.5 pips
        2. raw spread must not exceed 15% of the entry-to-stop-loss distance
        """
        spec = self.mt5.symbol_info(symbol)
        if not spec:
            logger.warning("No symbol info for %s, skipping spread check", symbol)
            return

        point = Decimal(str(spec.point if spec.point else "0.00001"))
        spread_points = Decimal(str(spec.spread if spec.spread else "5"))
        raw_spread = spread_points * point
        pip_size = self._pip_size(spec)

        if raw_spread > MAX_SPREAD_PIPS * pip_size:
            raise SpreadRejection(
                f"SPREAD REJECTED [{symbol}]: raw spread {float(raw_spread):.6f} "
                f"({int(spread_points)} points) exceeds {MAX_SPREAD_PIPS} pips limit."
            )

        if stop_loss is not None:
            risk_dist = abs(Decimal(str(price)) - Decimal(str(stop_loss)))
            if risk_dist > 0 and raw_spread / risk_dist > MAX_SPREAD_RISK_RATIO:
                raise SpreadRejection(
                    f"SPREAD REJECTED [{symbol}]: raw spread {float(raw_spread):.6f} exceeds "
                    f"{MAX_SPREAD_RISK_RATIO:.0%} of risk distance ({float(risk_dist):.6f}). "
                    f"Ratio: {float(raw_spread / risk_dist):.2%}"
                )

        logger.info(
            "Spread check PASSED [%s]: spread=%.6f (%d points), pip=%.6f",
            symbol, float(raw_spread), int(spread_points), float(pip_size),
        )

    # ------------------------------------------------------------------ #
    # Module 4 — order placement
    # ------------------------------------------------------------------ #

    def place_order(self, req: BrokerOrderRequest) -> dict:
        """Dispatch an order according to ``req.order_type``.

        This is the entry point used by the execution loop. Returns the MT5
        result as a dict; callers check ``retcode in (10008, 10009)``.
        """
        order_type = (req.order_type or "MARKET").upper()
        if order_type == "LIMIT":
            return self.place_limit_order(req)
        if order_type in ("MARKET", "DEAL"):
            return self.place_market_order(req)
        raise ValueError(f"Unsupported order_type: {req.order_type!r}")

    def place_limit_order(self, req: BrokerOrderRequest) -> dict:
        """Pending limit entry — sweep level or FVG 50% consequent encroachment.

        Unlike a market deal, a pending order sits away from the current price,
        so SL/TP can be attached in the same request without tripping Error 130.
        """
        if req.price is None:
            raise ValueError("LIMIT order requires an entry price")

        spec = self.mt5.symbol_info(req.symbol)
        if spec is None:
            raise RuntimeError(f"No symbol info for {req.symbol}")
        digits = spec.digits if spec else 5

        price = round(float(req.price), digits)
        sl = round(float(req.stop_loss), digits) if req.stop_loss else 0.0
        tp = round(float(req.take_profit), digits) if req.take_profit else 0.0

        self._check_spread_safety(req.symbol, price, sl if sl > 0 else None)

        typ = (
            self.mt5.ORDER_TYPE_BUY_LIMIT
            if req.direction == "BUY"
            else self.mt5.ORDER_TYPE_SELL_LIMIT
        )

        request = {
            "action": self.mt5.TRADE_ACTION_PENDING,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_RETURN,
            "comment": "RomeoTPT LIMIT",
        }

        if req.expiration:
            request["type_time"] = self.mt5.ORDER_TIME_SPECIFIED
            request["expiration"] = int(req.expiration)
        else:
            request["type_time"] = self.mt5.ORDER_TIME_GTC

        result = self.mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")

        result_dict = result._asdict()
        result_dict["entry_mode"] = "LIMIT"
        logger.info(
            "LIMIT order [%s] %s %.2f @ %s sl=%s tp=%s -> retcode=%s",
            req.symbol, req.direction, float(req.volume), price, sl, tp,
            result_dict.get("retcode"),
        )
        return result_dict

    def place_market_order(self, req: BrokerOrderRequest) -> dict:
        """Two-step ECN market dispatch with an emergency safety net."""
        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")

        self.last_tick_time = tick.time
        self.last_tick_price = (tick.bid + tick.ask) / 2

        spec = self.mt5.symbol_info(req.symbol)
        digits = spec.digits if spec else 5

        typ = (
            self.mt5.ORDER_TYPE_BUY
            if req.direction == "BUY"
            else self.mt5.ORDER_TYPE_SELL
        )
        price = round(tick.ask if req.direction == "BUY" else tick.bid, digits)
        sl = round(float(req.stop_loss), digits) if req.stop_loss else 0.0
        tp = round(float(req.take_profit), digits) if req.take_profit else 0.0

        self._check_spread_safety(req.symbol, price, sl if sl > 0 else None)

        # Step 1: market entry WITHOUT SL/TP (prevents Error 130 on ECN feeds).
        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": float(price),
            "sl": 0.0,
            "tp": 0.0,
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")

        result_dict = result._asdict()
        result_dict["entry_mode"] = "MARKET"
        ticket = result.order if getattr(result, "order", None) else None

        # Step 2: attach SL/TP by modifying the resulting position.
        if ticket and (sl > 0 or tp > 0):
            modify_result = self.mt5.order_send({
                "action": self.mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp,
            })
            if modify_result and modify_result.retcode in (RETCODE_PLACED, RETCODE_DONE):
                result_dict["sltp_attached"] = True
            else:
                # Step 3: emergency safety net — an unprotected position is
                # worse than no position, so close it immediately.
                err_code = modify_result.retcode if modify_result else "NO_RESULT"
                result_dict["sltp_attach_error"] = err_code
                close_side = (
                    self.mt5.ORDER_TYPE_SELL if req.direction == "BUY"
                    else self.mt5.ORDER_TYPE_BUY
                )
                close_price = tick.bid if req.direction == "BUY" else tick.ask
                close_result = self.mt5.order_send({
                    "action": self.mt5.TRADE_ACTION_DEAL,
                    "symbol": req.symbol,
                    "volume": float(req.volume),
                    "type": close_side,
                    "position": ticket,
                    "price": float(close_price),
                    "deviation": 100,
                    "type_filling": self.mt5.ORDER_FILLING_IOC,
                })
                if close_result:
                    result_dict["emergency_closed"] = close_result.retcode
                    result_dict["note"] = f"Safety close: SL/TP modify returned {err_code}"
        else:
            result_dict["sltp_skipped"] = True

        return result_dict

    # ------------------------------------------------------------------ #
    # Position maintenance (breakeven / trailing)
    # ------------------------------------------------------------------ #

    def modify_position(self, ticket: int, stop_loss: Decimal | float, take_profit: Decimal | float) -> dict:
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
