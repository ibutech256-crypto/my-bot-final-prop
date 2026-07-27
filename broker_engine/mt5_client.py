from dataclasses import dataclass
from decimal import Decimal
import importlib
import logging

logger = logging.getLogger("broker")


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


class MT5Client:
    """MT5 broker client with spread protection and order placement (v2.0.0)."""

    def __init__(self, login: int, password: str, server: str, path: str | None = None):
        self.login = login
        self.last_tick_time = 0
        self.last_tick_price = 0
        self.password = password
        self.server = server
        self.path = path
        self.is_connected = False
        self.reconnect_attempts = 0
        self.is_connected = False
        self.reconnect_attempts = 0
        self.mt5 = importlib.import_module("MetaTrader5")

    def connect(self) -> None:
        if not self.mt5.initialize(
            path=self.path, login=self.login, password=self.password, server=self.server
        ):
            raise ConnectionError(f"MT5 initialization failed: {self.mt5.last_error()}")

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def account_info(self) -> dict:
        info = self.mt5.account_info()
        if info is None:
            raise RuntimeError(f"Cannot read MT5 account info: {self.mt5.last_error()}")
        return info._asdict()

    def _check_spread_safety(self, symbol: str, price: float, stop_loss: float | None) -> None:
        """Comprehensive spread safety checks (Module 3).
        
        1. Reject if raw spread > 2.5 pips
        2. Reject if current spread > 15% of entry-to-stop-loss distance
        """
        spec = self.mt5.symbol_info(symbol)
        if not spec:
            logger.warning(f"No symbol info for {symbol}, skipping spread check")
            return

        point = Decimal(str(spec.point if spec.point else "0.00001"))
        spread_points = Decimal(str(spec.spread if spec.spread else "5"))
        raw_spread = spread_points * point
        pip_size = point * Decimal("10") if spec.digits in [3, 5] else point

        # 1. Reject if raw spread > 2.5 pips
        if raw_spread > Decimal("2.5") * pip_size:
            raise RuntimeError(
                f"SPREAD REJECTED: Raw spread {float(raw_spread):.6f} "
                f"({float(spread_points):.0f} points) exceeds 2.5 pips limit."
            )

        # 2. Reject if spread > 15% of Entry-to-SL distance
        if stop_loss is not None:
            risk_dist = abs(Decimal(str(price)) - Decimal(str(stop_loss)))
            if risk_dist > 0 and raw_spread / risk_dist > Decimal("0.15"):
                raise RuntimeError(
                    f"SPREAD REJECTED: Raw spread {float(raw_spread):.6f} exceeds "
                    f"15% of risk buffer ({float(risk_dist):.6f}). "
                    f"Ratio: {float(raw_spread / risk_dist):.2%}"
                )

        logger.info(
            f"Spread check PASSED for {symbol}: "
            f"spread={float(raw_spread):.6f}, "
            f"spread_points={float(spread_points):.0f}, "
            f"pip_size={float(pip_size):.6f}"
        )

    def place_market_order(self, req: BrokerOrderRequest) -> dict:
            """Two-step ECN dispatch with emergency safety net."""
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

            # Step 1: Market entry WITHOUT SL/TP (prevents Error 130)
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
            ticket = result.order if hasattr(result, 'order') and result.order else None

            # Step 2: Attach SL/TP via position modify
            if ticket and (sl > 0 or tp > 0):
                modify_result = self.mt5.order_send({
                    "action": self.mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "sl": sl,
                    "tp": tp,
                })
                if modify_result and modify_result.retcode in (10008, 10009):
                    result_dict['sltp_attached'] = True
                else:
                    # Step 3: Emergency safety net - SL/TP failed, close position
                    err_code = modify_result.retcode if modify_result else 'NO_RESULT'
                    result_dict['sltp_attach_error'] = err_code
                    close_side = self.mt5.ORDER_TYPE_SELL if req.direction == 'BUY' else self.mt5.ORDER_TYPE_BUY
                    close_price = tick.bid if req.direction == 'BUY' else tick.ask
                    close_result = self.mt5.order_send({
                        'action': self.mt5.TRADE_ACTION_DEAL,
                        'symbol': req.symbol,
                        'volume': float(req.volume),
                        'type': close_side,
                        'position': ticket,
                        'price': float(close_price),
                        'deviation': 100,
                        'type_filling': self.mt5.ORDER_FILLING_IOC,
                    })
                    if close_result:
                        result_dict['emergency_closed'] = close_result.retcode
                        result_dict['note'] = f'Safety close: SL/TP modify returned {err_code}'
            else:
                result_dict['sltp_skipped'] = True

            return result_dict
    def ensure_connected(self) -> bool:
        import time as _t
        if getattr(self, 'is_connected', False):
            try:
                info = self.mt5.account_info()
                if info is not None:
                    self.reconnect_attempts = 0
                    return True
            except:
                pass
            self.is_connected = False
        self.reconnect_attempts = getattr(self, 'reconnect_attempts', 0) + 1
        delay = min(1.0 * (2 ** (self.reconnect_attempts - 1)), 30.0)
        _t.sleep(delay)
        if self.mt5.initialize() and self.mt5.login(self.login, self.password, self.server):
            self.is_connected = True
            self.reconnect_attempts = 0
            return True
        return False


