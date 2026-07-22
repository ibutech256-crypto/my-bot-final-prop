from __future__ import annotations
from datetime import time
from decimal import Decimal
from typing import Any
from trading_engine.types import AccountSnapshot, AssetClass, SymbolSpec

def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None: return Decimal(default)
    return Decimal(str(value))

def classify_asset(symbol: str, description: str = "") -> AssetClass:
    text = f"{symbol} {description}".upper()
    crypto = ("BTC","ETH","SOL","XRP","ADA","BNB","AVAX","LINK","DOGE","LTC","MATIC","DOT","TRX","SHIB")
    if any(x in text for x in crypto): return AssetClass.CRYPTO
    if any(x in text for x in ("XAU","GOLD","XAG","SILVER")): return AssetClass.METAL
    if any(x in text for x in ("US30","NAS","SPX","GER","UK100","DJI","DAX","INDEX")): return AssetClass.INDEX
    if any(x in text for x in ("OIL","WTI","BRENT","GAS","NGAS")): return AssetClass.COMMODITY
    if len(symbol.replace(".","").replace("_","").replace("-","")[:6]) >= 6 and any(ccy in text for ccy in ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")): return AssetClass.FOREX
    return AssetClass.OTHER

class MT5BrokerIntelligence:
    """Reads account, symbol and execution specifications directly from the connected MT5 terminal."""
    def __init__(self, mt5_module: Any):
        self.mt5 = mt5_module
    def account_snapshot(self) -> AccountSnapshot:
        info = self.mt5.account_info()
        if info is None: raise ConnectionError(f"MT5 account_info unavailable: {self.mt5.last_error()}")
        data = info._asdict()
        return AccountSnapshot(
            broker_name=str(data.get("company", "")), server=str(data.get("server", "")), currency=str(data.get("currency", "USD")),
            balance=_dec(data.get("balance")), equity=_dec(data.get("equity")), free_margin=_dec(data.get("margin_free")),
            margin_level=_dec(data.get("margin_level")), leverage=_dec(data.get("leverage"), "1"),
        )
    def discover_symbols(self, include_invisible: bool = False) -> tuple[str, ...]:
        symbols = self.mt5.symbols_get()
        if symbols is None: raise ConnectionError(f"MT5 symbols_get unavailable: {self.mt5.last_error()}")
        names = []
        for sym in symbols:
            data = sym._asdict()
            if include_invisible or data.get("visible", False): names.append(str(data["name"]))
        return tuple(sorted(set(names)))
    def symbol_spec(self, symbol: str) -> SymbolSpec:
        account = self.account_snapshot()
        info = self.mt5.symbol_info(symbol)
        if info is None: raise ValueError(f"Symbol not available from broker: {symbol}")
        if not getattr(info, "visible", False): self.mt5.symbol_select(symbol, True)
        data = info._asdict()
        filling = tuple(str(x) for x in [data.get("filling_mode")] if x is not None)
        orders = tuple(str(x) for x in [data.get("order_mode")] if x is not None)
        return SymbolSpec(
            symbol=symbol, asset_class=classify_asset(symbol, str(data.get("description", ""))), broker_name=account.broker_name,
            server=account.server, account_currency=account.currency, leverage=account.leverage,
            contract_size=_dec(data.get("trade_contract_size"), "1"), digits=int(data.get("digits", 0)),
            tick_size=_dec(data.get("trade_tick_size"), "0.00001"), tick_value=_dec(data.get("trade_tick_value"), "0"),
            volume_step=_dec(data.get("volume_step"), "0.01"), min_volume=_dec(data.get("volume_min"), "0.01"), max_volume=_dec(data.get("volume_max"), "100"),
            spread_points=_dec(data.get("spread"), "0"), commission_per_lot=_dec(data.get("commission"), "0"),
            swap_long=_dec(data.get("swap_long"), "0"), swap_short=_dec(data.get("swap_short"), "0"),
            execution_mode=str(data.get("trade_exemode", "")), filling_modes=filling, order_types=orders,
            trade_hours=((time(0,0), time(23,59,59)),), visible=bool(data.get("visible", False)), margin_initial=_dec(data.get("margin_initial"), "0"),
        )
