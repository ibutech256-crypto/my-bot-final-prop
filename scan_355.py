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

symbols = [s.symbol for s in TradingSymbol.objects.filter(is_tradeable=True, is_deleted=False)]
print(f"Scanning {len(symbols)} Exness symbols for active Liquidity Sweeps / Scores...")
sweeps_found = 0
kod_found = 0
cisd_found = 0

for sym in symbols:
    try:
        spec = bi.symbol_spec(sym)
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 80)
        if rates is None or len(rates) < 60: continue
        candles = [Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc), open=Decimal(str(r["open"])), high=Decimal(str(r["high"])), low=Decimal(str(r["low"])), close=Decimal(str(r["close"])), volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)) for i, r in enumerate(rates)]
        completed = [c for c in candles if c.completed]
        crt_range = orch.crt.detect(completed)
        if not crt_range: continue
        sweep = orch.liquidity.detect_sweep(completed, crt_range, spec.tick_size)
        if not sweep or sweep.failed: continue
        sweeps_found += 1
        kod = orch.kod.confirmed(completed, sweep)
        if not kod:
            print(f"[{sym}] Sweep active ({sweep.direction} @ {sweep.swept_level}), waiting for KOD confirmation")
            continue
        kod_found += 1
        structure = orch.structure.analyse(completed)
        cisd = orch.cisd.confirmed(completed, sweep.direction, structure)
        if not cisd:
            print(f"[{sym}] KOD active! Waiting for CISD delivery shift...")
            continue
        cisd_found += 1
        setup = orch.evaluate(sym, Timeframe.M15, candles, {}, snapshot, spec, None, [], [])
        if setup:
            print(f"[{sym}] FULL SETUP QUALIFIED! Score: {setup.score.total}/100")
    except Exception as e:
        pass

print(f"Scan complete: {sweeps_found} active sweeps, {kod_found} KOD confirmed, {cisd_found} CISD confirmed.")
mt5.shutdown()
