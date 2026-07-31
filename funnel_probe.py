"""One-shot measurement of every strategy stage against live MT5 data.

Runs inside the VPS venv with Django configured. Read-only: it never sends an
order and never writes to the database.
"""
import os, sys, json, collections
sys.path.insert(0, r"C:\prop-frim-bot")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
import django; django.setup()

from decimal import Decimal
from datetime import datetime, timezone
from broker_engine.mt5_client import MT5Client
from trading_engine.orchestrator import RomeoTPTOrchestrator, EngineConfig
from trading_engine.types import Candle, Direction, Timeframe
from dotenv import load_dotenv
load_dotenv(r"C:\prop-frim-bot\.env", override=True)

client = MT5Client(login=int(os.getenv("MT5_LOGIN")), password=os.getenv("MT5_PASSWORD"),
                   server=os.getenv("MT5_SERVER"), path=os.getenv("MT5_PATH"))
client.connect()
mt5 = client.mt5
orch = RomeoTPTOrchestrator(EngineConfig(minimum_score=Decimal("50"), mode="AUTOMATED"))

from backend.apps.trading.management.commands.run_mt5_engine import FOCUS_SYMBOLS
TFS = [(mt5.TIMEFRAME_M5, "M5"), (mt5.TIMEFRAME_M15, "M15"), (mt5.TIMEFRAME_H1, "H1")]
HTF = [(mt5.TIMEFRAME_H4, "H4"), (mt5.TIMEFRAME_D1, "D1")]

def to_candles(rates):
    out = []
    for i, r in enumerate(rates):
        out.append(Candle(time=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                          open=Decimal(str(r["open"])), high=Decimal(str(r["high"])),
                          low=Decimal(str(r["low"])), close=Decimal(str(r["close"])),
                          volume=Decimal(str(r["tick_volume"])), completed=(i < len(rates)-1)))
    return out

C = collections.Counter()
kod_reasons = collections.Counter()
htf_dist = collections.Counter()
fvg_states = collections.Counter()
samples = []

# cache HTF per symbol
htf_cache = {}

for sym in FOCUS_SYMBOLS:
    si = mt5.symbol_info(sym)
    if si is None:
        C["no_spec"] += 1; continue
    for mt5_tf, tfname in TFS:
        C["scanned"] += 1
        rates = mt5.copy_rates_from_pos(sym, mt5_tf, 0, 80)
        if rates is None or len(rates) < 60:
            C["insufficient_bars"] += 1; continue
        candles = to_candles(rates)
        completed = [c for c in candles if c.completed]
        C["bars_ok"] += 1
        try:
            from trading_engine.broker_intelligence import MT5BrokerIntelligence
            spec = MT5BrokerIntelligence(mt5).symbol_spec(sym)
        except Exception:
            C["spec_err"] += 1; continue

        crt = orch.crt.detect(completed)
        if not crt:
            C["no_crt"] += 1; continue
        C["crt_ok"] += 1

        sweep = orch.liquidity.detect_sweep(completed, crt, spec.tick_size)
        if sweep is None:
            C["no_sweep"] += 1
        elif sweep.failed:
            C["sweep_failed"] += 1
        else:
            C["sweep_ok"] += 1

        atr = orch._calculate_atr_14(completed)
        if sweep is not None:
            ok, reason = orch.kod.confirmed_with_reason(completed, sweep, atr)
            if ok: C["kod_ok"] += 1
            kod_reasons[reason.split(":")[0].split("(")[0].strip()[:60]] += 1
            # measure sub-parts individually
            si_ = int(sweep.candle_index)
            if 0 <= si_ < len(completed)-1:
                sc = completed[si_]; dc = completed[si_+1]
                if sc.range() > 0 and dc.range() > 0:
                    wick = (sc.lower_wick() if sweep.direction == Direction.BUY else sc.upper_wick())/sc.range()
                    C["k_wick_pass"] += int(wick >= Decimal("0.30"))
                    C["k_dir_pass"] += int(dc.direction() == sweep.direction)
                    C["k_body_atr_pass"] += int(atr <= 0 or dc.body() >= Decimal("1.2")*atr)
                    C["k_bodyratio_pass"] += int(dc.body()/dc.range() >= Decimal("0.55"))
                    w = completed[max(0, si_+1-20):si_+1]
                    av = sum(x.volume for x in w)/Decimal(str(len(w))) if w else Decimal("0")
                    C["k_vol_pass"] += int(av <= 0 or dc.volume >= Decimal("1.5")*av)
                    C["k_measured"] += 1

        structure = orch.structure.analyse(completed)
        dir_struct = structure.bias if structure.bias != Direction.NEUTRAL else Direction.BUY
        dir_sweep = sweep.direction if sweep is not None else None
        if dir_sweep is not None:
            C["dir_agree" if dir_sweep == dir_struct else "dir_conflict"] += 1

        # CISD under both direction conventions
        C["cisd_struct"] += int(orch.cisd.confirmed(completed, dir_struct, structure))
        if dir_sweep: C["cisd_sweep"] += int(orch.cisd.confirmed(completed, dir_sweep, structure))

        # FVG
        gaps = orch.fvg.detect(completed)
        for g in gaps: fvg_states[g.state] += 1
        for d in (dir_struct,):
            C["fvg_mitigated"] += int(any(g.direction == d and g.state in {"MITIGATED","FILLED"} for g in gaps))

        # HTF real bias
        if sym not in htf_cache:
            hc = {}
            for h_tf, h_name in HTF:
                hr = mt5.copy_rates_from_pos(sym, h_tf, 0, 120)
                if hr is not None and len(hr) >= 60:
                    hc[h_name] = to_candles(hr)
            htf_cache[sym] = hc
        hc = htf_cache[sym]
        biases = {k: orch.trend.bias(v).value for k, v in hc.items()}
        htf_dist["|".join(f"{k}={v}" for k,v in sorted(biases.items())) or "none"] += 1
        if biases:
            aligned_struct = all(b in {dir_struct.value, "NEUTRAL"} for b in biases.values())
            C["htf_aligned_struct"] += int(aligned_struct)
            if dir_sweep:
                C["htf_aligned_sweep"] += int(all(b in {dir_sweep.value,"NEUTRAL"} for b in biases.values()))
            C["htf_measured"] += 1

        sess = orch.session.evaluate(datetime.now(timezone.utc))
        C["session_liquid"] += int(sess.liquid)

        if len(samples) < 25 and sweep is not None and not sweep.failed:
            samples.append(dict(sym=sym, tf=tfname, sweep=sweep.direction.value,
                                struct=dir_struct.value, biases=biases,
                                kod=orch.kod.confirmed_with_reason(completed, sweep, atr)[1][:90]))

print("=== COUNTERS ==="); [print(f"  {k:24s} {v}") for k,v in sorted(C.items())]
print("=== KOD REJECTION REASONS ==="); [print(f"  {v:6d}  {k}") for k,v in kod_reasons.most_common(20)]
print("=== FVG STATES ==="); [print(f"  {k:12s} {v}") for k,v in fvg_states.most_common()]
print("=== HTF BIAS COMBOS (top 15) ==="); [print(f"  {v:6d}  {k}") for k,v in htf_dist.most_common(15)]
print("=== SAMPLES ===")
for s in samples[:25]: print("  ", json.dumps(s))
