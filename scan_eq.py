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
from trading_engine.types import Candle, AccountSnapshot, Timeframe, LiquidityEvent, Direction
from backend.apps.trading.models import TradingSymbol

bi = MT5BrokerIntelligence(mt5)
orch = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("50"), mode="AUTOMATED"))
snapshot = bi.account_snapshot()

symbols = [s.symbol for s in TradingSymbol.objects.filter(is_tradeable=True, is_deleted=False)]
print(f"Scanning {len(symbols)} symbols across M5, M15, H1 for EQH/EQL and BSL/SSL sweeps...")
found = 0

for sym in symbols[:50]: # check top 50
    try:
        spec = bi.symbol_spec(sym)
        for mt5_tf, tf_enum in [(mt5.TIMEFRAME_M5, Timeframe.M5), (mt5.TIMEFRAME_M15, Timeframe.M15), (mt5.TIMEFRAME_H1, Timeframe.H1)]:
            rates = mt5.copy_rates_from_pos(sym, mt5_tf, 0, 80)
            if rates is None or len(rates) < 60: continue
            candles = [Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc), open=Decimal(str(r["open"])), high=Decimal(str(r["high"])), low=Decimal(str(r["low"])), close=Decimal(str(r["close"])), volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)) for i, r in enumerate(rates)]
            completed = [c for c in candles if c.completed]
            crt_range = orch.crt.detect(completed)
            if not crt_range: continue
            
            eq_h = orch.liquidity.equal_highs(completed, spec.tick_size)
            eq_l = orch.liquidity.equal_lows(completed, spec.tick_size)
            
            # Check last 3 completed bars against crt range OR eqh/eql
            tol = spec.tick_size * orch.liquidity.equal_tolerance_ticks
            for idx_offset in [-1, -2, -3]:
                c = completed[idx_offset]
                idx = len(completed) + idx_offset
                
                # Check EQH sweep
                for h_lvl in eq_h:
                    if c.high > h_lvl + tol and c.close < h_lvl:
                        print(f"[{sym} {tf_enum.value}] EQH Sweep at bar {idx_offset} (level {h_lvl})")
                        found += 1
                # Check EQL sweep
                for l_lvl in eq_l:
                    if c.low < l_lvl - tol and c.close > l_lvl:
                        print(f"[{sym} {tf_enum.value}] EQL Sweep at bar {idx_offset} (level {l_lvl})")
                        found += 1
    except Exception as e:
        pass

print(f"Total EQH/EQL/BSL/SSL sweeps found across top 50: {found}")
mt5.shutdown()
