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

bi = MT5BrokerIntelligence(mt5)
orch = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("75"), mode="AUTOMATED"))
snapshot = bi.account_snapshot()

for sym in ["EURUSDm", "GBPUSDm", "BTCUSDm", "ETHUSDm", "XAUUSDm"]:
    try:
        spec = bi.symbol_spec(sym)
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 80)
        if rates is None or len(rates) < 60:
            print(f"{sym} -> No rates or < 60 bars")
            continue
        candles = [Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc), open=Decimal(str(r["open"])), high=Decimal(str(r["high"])), low=Decimal(str(r["low"])), close=Decimal(str(r["close"])), volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)) for i, r in enumerate(rates)]
        completed = [c for c in candles if c.completed]
        crt_range = orch.crt.detect(completed)
        if not crt_range:
            print(f"{sym} -> No CRT range")
            continue
        sweep = orch.liquidity.detect_sweep(completed, crt_range, spec.tick_size)
        if not sweep or sweep.failed:
            print(f"{sym} -> CRT Range OK ({crt_range.state}), but awaiting Liquidity Sweep of EQH/EQL/BSL/SSL")
            continue
        kod = orch.kod.confirmed(completed, sweep)
        if not kod:
            print(f"{sym} -> Sweep detected ({sweep.direction} @ {sweep.swept_level}), waiting for KOD displacement confirmation")
            continue
        print(f"{sym} -> KOD confirmed! Checking CISD...")
    except Exception as e:
        print(f"{sym} -> Error: {e}")
mt5.shutdown()
