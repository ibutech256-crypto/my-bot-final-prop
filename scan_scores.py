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
from trading_engine.types import Candle, AccountSnapshot, Timeframe, Direction
from backend.apps.trading.models import TradingSymbol

bi = MT5BrokerIntelligence(mt5)
orch = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("50"), mode="AUTOMATED"))
snapshot = bi.account_snapshot()

symbols = [s.symbol for s in TradingSymbol.objects.filter(is_tradeable=True, is_deleted=False)]
print("Checking confluence scores across Exness symbols...")
scores_50_plus = []

for sym in symbols[:60]:
    try:
        spec = bi.symbol_spec(sym)
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 80)
        if rates is None or len(rates) < 60: continue
        candles = [Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc), open=Decimal(str(r["open"])), high=Decimal(str(r["high"])), low=Decimal(str(r["low"])), close=Decimal(str(r["close"])), volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)) for i, r in enumerate(rates)]
        completed = [c for c in candles if c.completed]
        crt_range = orch.crt.detect(completed)
        if not crt_range: continue
        
        structure = orch.structure.analyse(completed)
        direction = structure.bias if structure.bias != Direction.NEUTRAL else Direction.BUY
        
        sweep = orch.liquidity.detect_sweep(completed, crt_range, spec.tick_size)
        kod = orch.kod.confirmed(completed, sweep) if sweep else False
        cisd = orch.cisd.confirmed(completed, direction, structure)
        
        session_state = orch.session.evaluate(datetime.now(timezone.utc))
        news_state = orch.news.evaluate(datetime.now(timezone.utc), sym, [])
        htf_ok = True
        
        score = orch.scoring.score(direction, sweep, kod, cisd, htf_ok, session_state, structure, True, True, news_state, Decimal("50"))
        if score.total >= Decimal("50"):
            scores_50_plus.append((sym, float(score.total), [k for k, v in score.components.items() if v > 0]))
    except Exception as e:
        pass

scores_50_plus.sort(key=lambda x: x[1], reverse=True)
for s, sc, comps in scores_50_plus[:20]:
    print(f"[{s}] Score: {sc}/100 | Active Confluences: {comps}")
print(f"Total symbols scoring 50+ right now: {len(scores_50_plus)}")
mt5.shutdown()
