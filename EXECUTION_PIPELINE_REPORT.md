# Execution Pipeline Remediation — Final Report

**System:** `prop-frim-bot` (CRT + Turtle Soup / Romeo TPT)
**Host:** `194.37.80.107` · **Repo:** `ibutech256-crypto/my-bot-final-prop` @ `main`
**Date:** 2026-07-31 · **Mode:** `SHADOW_MODE=1` (no orders transmitted)
**Commits this session:** `b9bd032` → `640f55b` → `345f01f` (pushed)

---

## 1. Executive summary

The system was not failing to *find* setups. It was failing to *finish* them. Three
defects silently truncated the pipeline, and a fourth made the failure invisible:

| # | Defect | Effect | Status |
|---|--------|--------|--------|
| 1 | HTF alignment hard-defaulted to `True` | Every signal got a free 15-point confluence; the Tier 2 "HTF aligned" condition was vacuous | **Fixed & verified live** |
| 2 | Direction taken from `structure.bias`, not `sweep.direction` | KOD/CISD evaluated against the wrong side on 63.4% of sweeps | **Fixed & verified live** |
| 3 | Duplicate-signal throttle keyed on *any* row incl. WATCHLIST | The qualifying signal was suppressed every cycle by a bare `continue` with no log | **Fixed & verified live** |
| 4 | Gate rejections mapped to DB status by matching English prose | RSI/ADX rejections stored as `BLOCKED_RISK_CAP_REACHED`; `status` column also silently truncated | **Fixed & verified live** |
| 5 | `strategy_config.reload()` rebound a module global only | Env overrides never reached `scoring` / `account_manager` | **Fixed & verified live** |
| 6 | 36 orders referenced hard-deleted signals | Latent DB corruption; blocked any future schema change | **Fixed (migration 0002)** |

**Result:** the pipeline now runs end-to-end. In 84 scan cycles / **30,744 evaluations**
during the London session it produced a complete `TRADE-DECISION` and a
`SHADOW-TRADE … WOULD SEND` — the first time the execution path has completed.

**The remaining blocker is not a bug.** It is one over-tight execution-gate
threshold, now measured precisely and tunable from `.env` without a redeploy.
See §5. **I have not changed it**, because it is a strategy decision, not a defect.

---

## 2. Defect analysis

### 2.1 HTF alignment was never actually computed

| | |
|---|---|
| **File** | `trading_engine/orchestrator.py:341` (old), caller `run_mt5_engine.py:535` |
| **Root cause** | `evaluate_signal` initialised `htf_ok = True`, then refined it inside `if htf_candles:`. The engine called it *without* `htf_candles`, so the refinement never ran. |
| **Impact** | Every signal received the 15-point HTF component. Tier 2 (`score >= 70 and htf and fvg_mitigated`) degraded to `score >= 70 and fvg_mitigated`. Tier 3's `htf` leg was vacuous. |
| **Evidence (before)** | 460 / 460 stored signals carried the `'HTF Alignment'` confluence — a 100% rate that no real market produces. |
| **Fix** | New `trading_engine/htf_bias.py` (`HTFBiasEngine`, per-symbol TTL cache, H4+D1). `htf_ok` now starts `False` and is set only from a real `HTFBiasResult.aligned`. `DATA_UNAVAILABLE` is explicitly **not** aligned. |
| **Evidence (after)** | **ALIGNED 6,074 (51.0%) / CONFLICT 5,832 (49.0%)** across 11,906 scored evaluations. |
| **Side effects** | Scores legitimately drop by 15 points where HTF conflicts, so fewer setups reach Tier 2 — this is the correction working. HTF adds 2 rate calls per symbol, absorbed by a 300 s cache. |

A live line showing the difference — same engine, same cycle:

```
US30m  M5  … htf_status=CONFLICT htf_biases=D1=BUY|H4=BUY  … 'HTF Alignment': '0'   score=67
USTECm M5  … htf_status=ALIGNED  htf_biases=D1=SELL|H4=NEUTRAL … 'HTF Alignment': '15' score=60
```

### 2.2 Trade direction was read from the wrong source

| | |
|---|---|
| **File** | `backend/apps/trading/management/commands/run_mt5_engine.py` (scan loop) |
| **Root cause** | Used `structure.bias`, falling back to `BUY`. The canonical `orchestrator.evaluate()` uses `sweep.direction`. Turtle Soup *fades* a sweep, so the sweep defines the side. |
| **Impact** | Measured **130 / 205 sweeps (63.4%)** had `structure.bias != sweep.direction`, producing a 339:121 BUY:SELL skew and evaluating KOD/CISD against the wrong direction. |
| **Fix** | `direction = sweep.direction`. |
| **Evidence (after)** | `direction=SELL structure_bias=BUY structure_event=BOS_UP` — the sweep now wins, and the disagreement is logged for audit. |
| **Side effects** | Intentional behaviour change. Historical signals before this commit are not comparable on direction. |

### 2.3 A silent `continue` suppressed every qualifying signal

| | |
|---|---|
| **Root cause** | After writing a WATCHLIST row, the code re-queried `Signal.objects.filter(symbol, direction, strategy, created_at__gte=now-30min).exists()` and `continue`d if true — **with no log**. The row it had just written almost always matched. |
| **Impact** | The single mechanism behind *501 WATCHLIST / 0 ACTIVE*. A setup could never progress, and nothing recorded why. |
| **Fix** | Cooldown now keyed **only on executed trades** (`Order`, or `Signal.status in (EXECUTED, SHADOW_WOULD_EXECUTE)`), and it terminates the trace with `EXECUTION_COOLDOWN` instead of vanishing. |
| **Evidence (after)** | `EXECUTION_COOLDOWN` appears 31 times as an explicit, counted reason. |
| **Side effects** | Slightly more orders per symbol/day than the accidental throttle allowed — the intended behaviour. `EXEC_COOLDOWN_MINUTES` controls it. |

### 2.4 Block reasons were derived by matching English prose

| | |
|---|---|
| **Root cause** | `run_mt5_engine` inspected `score.gate_reason` / gate message substrings to choose a DB status. |
| **Impact** | 80 RSI/ADX/volatility rejections were recorded as `BLOCKED_RISK_CAP_REACHED` — the dashboard blamed the risk cap for rejections the risk cap never made. Additionally `Signal.status` was `max_length=16` while the engine wrote `BLOCKED_RISK_CAP_REACHED` (24 chars): SQLite truncated silently. |
| **Fix** | `TradeExecutionGate.evaluate` returns `meta["code"]` (a `pipeline_trace.Reason`). `SignalStatus` expanded 5 → 14 members, `status` widened to 32, and `block_code` / `block_reason` columns added. |
| **Side effects** | Any external consumer matching the old truncated strings must switch to `block_code`. |

### 2.5 Config reload reached almost nothing *(the item carried over from last session)*

The previous session flagged this as unresolved. The proposed fix (mutate in place)
would have been **insufficient** — there are three distinct capture patterns:

| Pattern | Example | Reached by rebinding? | Reached by in-place mutation? |
|---|---|---|---|
| Call-time attribute read | `CONFIG.spread.max_pips` in `orchestrator` | No | **Yes** |
| Construction-time read | `cfg = CONFIG.kod` in `KODEngine.__init__` | No | **Yes** (for engines built after) |
| Module-level scalar | `TIER_1_THRESHOLD = CONFIG.tiers.tier_1` in `scoring` | No | **No** |

`scoring.py` and `account_manager.py` snapshot *values*, so no amount of object
mutation can reach them. The implemented fix does both:

1. `reload()` builds a replacement, then copies fields onto the **existing** nested
   group objects via `object.__setattr__` (frozen dataclasses retained deliberately,
   with this as the single audited escape hatch).
2. A `register_reload_hook` registry lets `scoring` and `account_manager` re-derive
   their constants. A failing hook is logged and isolated, never aborting the reload.

**Proof it was broken, and is now fixed** (simulating the old `reload()`):

```
PRE-FIX   scoring.TIER_2_THRESHOLD: 70   (env said 66)
PRE-FIX   account_manager.ADX_MAX : 60.0 (env said 41)
POST-FIX  scoring.TIER_2_THRESHOLD: 66
POST-FIX  account_manager.ADX_MAX : 41
```

**Proof in production** — `FUNNEL_REPORT_EVERY_CYCLES=2` added to `.env`, engine
restarted, startup banner reports `CONFIG pipeline.funnel_report_every_cycles = 2`.

### 2.6 Orphaned foreign keys — found while migrating

Applying the lifecycle migration aborted:

```
IntegrityError: trading_order.signal_id contains a value '4470' that does not
have a corresponding value in trading_signal.id
```

| | |
|---|---|
| **Root cause** | `Order.signal` is `on_delete=SET_NULL`, so the declared intent is that orders survive signal deletion. 36 signals were nonetheless hard-deleted **out of band** (raw SQL cleanup), bypassing Django's cascade. SQLite does not enforce FKs unless `PRAGMA foreign_keys=ON`, so it was accepted silently and lay dormant. |
| **Why it surfaced now** | Altering a column on SQLite is *rebuild → copy → swap*, and Django runs `PRAGMA foreign_key_check` on schema-editor exit. |
| **Fix** | Migration `0002_repair_orphan_order_signals` nulls exactly those references — what Django itself would have produced. Versioned, not an ad-hoc server-side `UPDATE`, so it replays on any restored environment. The lifecycle migration became `0003` and depends on it. |
| **Verification** | `fk_violations 0` · `orders 87` (unchanged, all `FILLED`) · no row deleted. |

---

## 3. What was built

| Module | Purpose |
|---|---|
| `trading_engine/strategy_config.py` | Single source of truth; ~60 env-tunable parameters; defaults identical to the previous hard-coded values (behaviour-neutral) |
| `trading_engine/pipeline_trace.py` | 17 ordered `Stage`s, `Outcome`s, 43 `Reason` codes each with a non-generic sentence; `FunnelCounters` with per-session buckets |
| `trading_engine/htf_bias.py` | Real H4/D1 bias with TTL cache; never returns "aligned" on missing data |
| `backend/apps/trading/pipeline_views.py` | `GET /funnel/`, `GET /funnel/watchlist/`, `GET\|POST /strategy-config/` |
| `frontend/app/FunnelPanel.tsx` | "Signal Funnel" dashboard tab |
| `tests/` | 59 new tests (69 total on the VPS, including 10 pre-existing — all pass) |

Two supporting fixes worth calling out:

- **`SignalViewSet.get_queryset` filtered on `ACTIVE_MONITORING` and `EXECUTION_READY`
  — two statuses the engine has never written.** The dashboard could therefore only
  ever display WATCHLIST rows; the 4 `ACTIVE` signals in the database were invisible.
  This is a large part of why the system *looked* like it never traded.
- The `FUNNEL_UPDATE` websocket frame is a trimmed projection (the full snapshot is
  ~220 KB — too heavy to broadcast every 2 cycles), so the client **overlays** it onto
  the polled document rather than replacing it.

---

## 4. Live validation — London session, 84 cycles, 30,744 evaluations

### Funnel

| Stage | Count | % scanned | % of previous |
|---|---:|---:|---:|
| SCANNED | 30,744 | 100.0% | 100.0% |
| DATA_OK | 30,744 | 100.0% | 100.0% |
| CRT_CONFIRMED | 30,744 | 100.0% | 100.0% |
| LIQUIDITY_FOUND | 15,822 | 51.5% | 51.5% |
| SWEEP_VALID | 11,906 | 38.7% | 75.2% |
| **KOD_CONFIRMED** | **0** | **0.0%** | **0.0%** |
| HTF_CONFIRMED | 6,074 | 19.8% | — |
| SCORE_CALCULATED | 11,906 | 38.7% | — |
| TIER_QUALIFIED | 523 | 1.7% | — |
| RISK_APPROVED | 492 | 1.6% | 94.1% |
| **EXECUTION_GATE_PASSED** | **1** | **0.003%** | **0.2%** |
| SIZED / (shadow) | 1 | — | — |

### Termination reasons

| Code | Count | Share |
|---|---:|---:|
| NO_LIQUIDITY_SWEEP | 14,715 | 47.9% |
| SPREAD_RISK_RATIO | 5,385 | 17.5% |
| SWEEP_INVALIDATED | 4,123 | 13.4% |
| KOD_NOT_CONFIRMED | 3,549 | 11.5% |
| FVG_CE_NOT_MITIGATED | 1,588 | 5.2% |
| BELOW_TIER_1 | 861 | 2.8% |
| GATE_MOMENTUM_RSI | 373 | 1.2% |
| GATE_VOLATILITY | 84 | 0.3% |
| GATE_MOMENTUM_ADX | 34 | 0.1% |
| EXECUTION_COOLDOWN | 31 | 0.1% |
| SHADOW_MODE (would execute) | 1 | 0.003% |

Distributions: HTF **51.0% aligned / 49.0% conflict**; score median 67, p95 70, max 70;
spread median 27.7 pips, p95 1,306, max 4,038.

---

## 5. The remaining bottleneck — measured, not guessed

**492 setups were risk-approved. Exactly 1 passed the execution gate.**
Of the 522 execution-stage rejections:

| Gate | Count | Share of exec-stage |
|---|---:|---:|
| **GATE_MOMENTUM_RSI** | **373** | **71.5%** |
| GATE_VOLATILITY | 84 | 16.1% |
| GATE_MOMENTUM_ADX | 34 | 6.5% |
| EXECUTION_COOLDOWN | 31 | 5.9% |

The RSI gate is reversal-aware: a SELL (fading a sweep of highs) requires
`RSI >= 55`. I extracted the actual RSI at every rejection:

| Rejected SELLs (n=214) | min | p25 | median | p75 | **max** |
|---|---:|---:|---:|---:|---:|
| RSI(14) | 38.4 | 39.3 | 46.9 | 50.2 | **53.4** |

**No rejected SELL setup reached RSI 53.5, yet the gate demands 55.** In this regime
the threshold is not selective — it is a near-total block. Sensitivity:

| `EXEC_GATE_RSI_SELL_MIN` | Currently-rejected SELLs that would pass |
|---:|---:|
| 55 (current) | 0 / 214 (0.0%) |
| 52 | 43 / 214 (20.1%) |
| 50 | 74 / 214 (34.6%) |
| 45 | 117 / 214 (54.7%) |

**I have not changed this.** It is a strategy calibration decision and your brief was
explicit that the strategy is not to be redesigned. It is now a one-line `.env` change
plus an engine restart — no redeploy.

### Two other observations (not defects)

**KOD is structurally unreachable at current thresholds.** Sub-checks, measured
independently over 9,595 evaluable patterns:

| Sub-check | Pass rate |
|---|---:|
| `displacement_volume` (≥1.5× avg) | 7.07% |
| `displacement_atr` (body ≥1.2× ATR) | 7.51% |
| `displacement_body_ratio` (≥0.55) | 50.01% |
| `sweep_rejection_wick` (≥0.30) | 51.43% |
| `displacement_direction` | 78.12% |
| **Compound (all five)** | **0.107%** |

Expected ≈10 confirmations in 9,595; observed 0 (the checks are positively
correlated — a weak displacement fails ATR *and* body-ratio together). Since Tier 1
and Tier 3 both require KOD, **only Tier 2 is currently reachable** — which matches
the tier distribution exactly (TIER_2: 114, everything else NONE). Knobs:
`KOD_VOLUME_MULTIPLIER`, `KOD_ATR_MULTIPLIER`.

**The symbol universe is fighting the spread gate.** `SPREAD_RISK_RATIO` is the
second-largest blocker overall (5,385, 17.5%), and with a p95 of 1,306 pips and a max
of 4,038 the 121-symbol `FOCUS_SYMBOLS` list contains many instruments whose spread
cannot clear a 15% risk-distance ceiling on M5. Trimming the universe would raise
throughput more cheaply than loosening the ceiling.

---

## 6. Go-live checklist

| # | Step | State |
|---|---|---|
| 1 | Migrations `0002`, `0003` applied; `fk_violations 0`; 87 orders intact | **Done** |
| 2 | 69/69 tests pass on the VPS | **Done** |
| 3 | `manage.py check` clean; frontend `tsc --noEmit` clean; `npm run build` succeeds | **Done** |
| 4 | All 7 services running; funnel/config APIs HTTP 200; frontend HTTP 200 | **Done** |
| 5 | Committed & pushed (`345f01f`) | **Done** |
| 6 | **Observe the New York session** (opens 12:00 UTC) | **Pending — see below** |
| 7 | Decide on `EXEC_GATE_RSI_SELL_MIN` / `RSI_BUY_MAX` (§5) | **Your call** |
| 8 | Set `SHADOW_MODE=0` + restart `TradingMT5Engine` to promote to demo trading | **Not done — deliberate** |
| 9 | Rotate credentials (§7) | **Not done — needs you** |

**New York validation.** The engine already buckets statistics by session
automatically; nothing further needs to be deployed. After 12:00 UTC:

```
GET http://194.37.80.107:8000/api/v1/funnel/     ->  by_session.NEW_YORK
```
or open the **Signal Funnel** tab and switch scope to `NEW_YORK`. Compare
`GATE_MOMENTUM_RSI` share and HTF aligned% against the London figures in §4.

**Do not set `SHADOW_MODE=0` until step 6 and 7 are settled** — at present the gate
config would let through roughly one trade per session, which is too thin a sample to
justify going live.

---

## 7. Security items (unchanged — these need you)

| Item | Detail |
|---|---|
| GitHub PAT in the git remote URL | `ghp_qKye7…` is embedded in `origin`. Rotate, then `git remote set-url origin <clean-url>`. |
| VPS password | Reused across this work; rotate. |
| `frontend/.env` | Contains `MT5_PASSWORD`; scrub. |
| DB backup was briefly committed | The 53 MB `db.sqlite3.bak` landed in `640f55b`. Untracked in `345f01f` and `.gitignore`d, but **it remains in history** — if that history is sensitive, rewrite with `git filter-repo`/BFG and force-push. |
| Whole API is read-open | `ReadOnlyOrPrivileged` allows unauthenticated GET on every endpoint, and the dashboard depends on that. The new endpoints match this posture rather than diverging from it. Tightening must be done for all endpoints at once. |

---

## 8. Notes / not addressed

- **`position_sync.py` / `engine_runner.py`** remain dormant duplicate-IPC risks (§6.1 of the prior report) — untouched, not on the live path.
- **SMT divergence** is a genuine gap rather than a bug, and out of scope.
- **`spread_pips` for indices** is reported in raw points (e.g. `USTECm 360.0`). Cosmetic only: the absolute pip cap is disabled by default and the forex-only cap does not apply to indices. The ratio test, which does gate, is computed from raw price and is correct.
- **Risk per trade** on the shadow entry was 2.11% — a floor effect of the 0.01 minimum lot on a $91 account, not a sizing bug. It will fall as the balance grows.
