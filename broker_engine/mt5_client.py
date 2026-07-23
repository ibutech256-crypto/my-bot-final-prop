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
    order_type: str = "MARKET"  # MARKET, LIMIT


class MT5Client:
    """MT5 broker client with spread protection and order placement (v2.0.0)."""

    def __init__(self, login: int, password: str, server: str, path: str | None = None):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
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
        """Place a market order with spread protection."""
        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")

        typ = (
            self.mt5.ORDER_TYPE_BUY
            if req.direction == "BUY"
            else self.mt5.ORDER_TYPE_SELL
        )
        price = tick.ask if req.direction == "BUY" else tick.bid

        # Run spread safety checks before placing order
        self._check_spread_safety(req.symbol, price, float(req.stop_loss) if req.stop_loss else None)

        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": float(price),
            "sl": float(req.stop_loss or 0),
            "tp": float(req.take_profit or 0),
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")

        result_dict = result._asdict()
        logger.info(
            f"Market order placed: {req.direction} {req.volume} {req.symbol} "
            f"@ {price:.5f}, SL={req.stop_loss}, TP={req.take_profit}, "
            f"ticket={result_dict.get('order', 'N/A')}"
        )
        return result_dict

    def place_limit_order(self, req: BrokerOrderRequest) -> dict:
        """Place a limit order with spread protection."""
        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")

        if req.price is None:
            raise RuntimeError(f"Price is required for limit order on {req.symbol}")

        typ = (
            self.mt5.ORDER_TYPE_BUY_LIMIT
            if req.direction == "BUY"
            else self.mt5.ORDER_TYPE_SELL_LIMIT
        )

        # Run spread safety checks
        self._check_spread_safety(
            req.symbol,
            float(req.price),
            float(req.stop_loss) if req.stop_loss else None,
        )

        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_PENDING,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": float(req.price),
            "sl": float(req.stop_loss or 0),
            "tp": float(req.take_profit or 0),
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
            "type_time": self.mt5.ORDER_TIME_GTC,
        })
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")

        result_dict = result._asdict()
        logger.info(
            f"Limit order placed: {req.direction} {req.volume} {req.symbol} "
            f"@ {req.price:.5f}, SL={req.stop_loss}, TP={req.take_profit}, "
            f"ticket={result_dict.get('order', 'N/A')}"
        )
        return result_dict

    def modify_position(self, ticket: int, sl: float | None = None, tp: float | None = None) -> dict:
        """Modify an existing position's SL/TP."""
        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(sl or 0),
            "tp": float(tp or 0),
        })
        if result is None:
            raise RuntimeError(f"MT5 modify_position failed: {self.mt5.last_error()}")
        return result._asdict()

    def close_position(self, ticket: int, volume: float | None = None) -> dict:
        """Close a position partially or fully."""
        position = self.mt5.positions_get(ticket=ticket)
        if not position:
            raise RuntimeError(f"Position {ticket} not found")
        position = position[0]

        close_volume = volume if volume else position.volume
        typ = (
            self.mt5.ORDER_TYPE_SELL
            if position.type == self.mt5.ORDER_TYPE_BUY
            else self.mt5.ORDER_TYPE_BUY
        )
        tick = self.mt5.symbol_info_tick(position.symbol)
        price = tick.bid if position.type == self.mt5.ORDER_TYPE_BUY else tick.ask

        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": float(close_volume),
            "type": typ,
            "position": ticket,
            "price": float(price),
            "deviation": 20,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        if result is None:
            raise RuntimeError(f"MT5 close_position failed: {self.mt5.last_error()}")
        return result._asdict()
