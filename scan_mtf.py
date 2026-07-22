import os, sys
sys.path.insert(0, "C:/prop-frim-bot")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
import django; django.setup()
from datetime import datetime, timezone
from decimal import Decimal
import MetaTrader5 as mt5
mt5.initialize()
from trading_engine.broker_intelligence import MT5BrokerIntelligence
from trading_engine.orchestrator import RomeoTPTOrchestrator, EngineConfig
from trading_engine.types import Candle, AccountSnapshot, Timeframe
from backend.apps.trading.models import TradingSymbol

bi = MT5BrokerIntelligence(mt5)
orch = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("50"), mode="AUTOMATED"))
snapshot = bi.account_snapshot()

symbols = ["EURUSDm", "GBPUSDm", "BTCUSDm", "ETHUSDm", "XAUUSDm", "US30m", "AUDUSDm", "USDJPYm", "GBPJPYm", "XAGUSDm"]
tf_map = {mt5.TIMEFRAME_M5: Timeframe.M5, mt5.TIMEFRAME_M15: Timeframe.M15, mt5.TIMEFRAME_H1: Timeframe.H1}

print("Scanning MTF (M5, M15, H1) across top Exness symbols...")
for sym in symbols:
    for mt5_tf, tf_enum in tf_map.items():
        try:
            spec = bi.symbol_spec(sym)
            rates = mt5.copy_rates_from_pos(sym, mt5_tf, 0, 80)
            if rates is None or len(rates) < 60: continue
            candles = [Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc), open=Decimal(str(r["open"])), high=Decimal(str(r["high"])), low=Decimal(str(r["low"])), close=Decimal(str(r["close"])), volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)) for i, r in enumerate(rates)]
            completed = [c for c in candles if c.completed]
            crt_range = orch.crt.detect(completed)
            if not crt_range: continue
            
            # Check recent 3 completed candles for sweep
            tol = spec.tick_size * orch.liquidity.equal_tolerance_ticks
            for idx_offset in [-1, -2, -3]:
                c = completed[idx_offset]
                if c.high > crt_range.high + tol and c.close < crt_range.high:
                    print(f"[{sym} {tf_enum.value}] BSL Sweep detected on bar {idx_offset} (@ {c.high})")
                elif c.low < crt_range.low - tol and c.close > crt_range.low:
                    print(f"[{sym} {tf_enum.value}] SSL Sweep detected on bar {idx_offset} (@ {c.low})")
        except Exception as e:
            pass
mt5.shutdown()
