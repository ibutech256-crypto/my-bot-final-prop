from datetime import datetime, timezone
from decimal import Decimal
from trading_engine.broker_intelligence import classify_asset
from trading_engine.fvg import FairValueGapEngine
from trading_engine.risk import PositionSizingEngine
from trading_engine.types import AccountSnapshot, AssetClass, Candle, SymbolSpec


def spec(symbol="BTCUSD", leverage="20"):
    return SymbolSpec(symbol, AssetClass.CRYPTO, "Broker", "Server", "USD", Decimal(leverage), Decimal("1"), 2, Decimal("0.01"), Decimal("1"), Decimal("0.01"), Decimal("0.01"), Decimal("50"), Decimal("2"), Decimal("0"), Decimal("0"), Decimal("0"), "MARKET", ("IOC",), ("MARKET",), tuple(), True)


def candle(o, h, l, c):
    return Candle(datetime.now(timezone.utc), Decimal(o), Decimal(h), Decimal(l), Decimal(c), completed=True)


def test_crypto_position_sizing_uses_broker_leverage():
    account = AccountSnapshot("Broker", "Server", "USD", Decimal("10000"), Decimal("10000"), Decimal("5000"), Decimal("1000"), Decimal("20"))
    low_lev = PositionSizingEngine().calculate(account, spec(leverage="2"), Decimal("50000"), Decimal("49000"), Decimal("1"))
    high_lev = PositionSizingEngine().calculate(account, spec(leverage="20"), Decimal("50000"), Decimal("49000"), Decimal("1"))
    assert high_lev.maximum_allowed_position > low_lev.maximum_allowed_position


def test_asset_classification_supports_mt5_crypto_symbols():
    assert classify_asset("BTCUSD") == AssetClass.CRYPTO
    assert classify_asset("XAUUSD") == AssetClass.METAL
    assert classify_asset("US30.cash") == AssetClass.INDEX


def test_fvg_detection_and_permission():
    candles = [candle("1.00", "1.02", "0.99", "1.01"), candle("1.01", "1.04", "1.00", "1.03"), candle("1.06", "1.08", "1.05", "1.07")]
    gaps = FairValueGapEngine().detect(candles)
    assert gaps
    assert gaps[-1].kind == "BULLISH_FVG"
