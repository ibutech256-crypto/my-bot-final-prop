"""Signal lifecycle tracing and funnel telemetry.

Modules 2 / 3 / 4 (Phases 2-4)
------------------------------
Before this module the engine could not answer the single most important
operational question: *where did my signal go?* An evaluation that failed any
of ~15 checks either logged a free-text line or, in the worst cases, executed a
bare ``continue`` and vanished. The 30-minute duplicate-signal test in
``run_mt5_engine`` was the most damaging example — it silently discarded a
fully qualified, execution-ready setup with no log line at all, because a
non-executable WATCHLIST row for the same symbol happened to exist.

Two objects fix that:

``SignalTrace``
    Accumulates one ordered list of stages per symbol/timeframe evaluation.
    Every terminal decision must go through :meth:`SignalTrace.terminate`,
    which requires a machine-readable ``code`` *and* a human-readable
    ``reason``. There is no code path that ends an evaluation without one.

``FunnelCounters``
    Process-wide, thread-safe stage counters with per-session (London / New
    York / Asia / Off-session) buckets, rejection-reason histograms, spread and
    HTF distributions, and execution latency samples. Renders to text for the
    log, to JSON for the dashboard endpoint, and to a snapshot file for the
    validation report.

Nothing in this module touches the database or the broker, so it is safe to
import from anywhere and trivial to unit test.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable

logger = logging.getLogger("trading")


# --------------------------------------------------------------------------- #
# Lifecycle stages
# --------------------------------------------------------------------------- #

class Stage(str, Enum):
    """Ordered lifecycle of a single symbol/timeframe evaluation.

    The order of declaration is the order of the funnel: each stage can only be
    reached from the one above it, which is what makes stage-to-stage
    conversion percentages meaningful.
    """

    SCANNED = "SCANNED"
    DATA_OK = "DATA_OK"
    CRT_CONFIRMED = "CRT_CONFIRMED"
    LIQUIDITY_FOUND = "LIQUIDITY_FOUND"
    SWEEP_VALID = "SWEEP_VALID"
    KOD_CONFIRMED = "KOD_CONFIRMED"
    HTF_CONFIRMED = "HTF_CONFIRMED"
    SCORE_CALCULATED = "SCORE_CALCULATED"
    TIER_QUALIFIED = "TIER_QUALIFIED"
    SIGNAL_PERSISTED = "SIGNAL_PERSISTED"
    RISK_APPROVED = "RISK_APPROVED"
    EXECUTION_GATE_PASSED = "EXECUTION_GATE_PASSED"
    SIZED = "SIZED"
    ORDER_SENT = "ORDER_SENT"
    FILLED = "FILLED"
    POSITION_MANAGED = "POSITION_MANAGED"
    CLOSED = "CLOSED"


#: The funnel is reported in exactly this order.
FUNNEL_ORDER: tuple[Stage, ...] = tuple(Stage)


class Outcome(str, Enum):
    """How an evaluation ended. Every trace has exactly one."""

    NO_SETUP = "NO_SETUP"                 # no CRT / no sweep: not a Romeo TPT setup
    WATCHLIST = "WATCHLIST"               # valid setup, did not qualify for a tier
    WAITING_FOR_RETRACEMENT = "WAITING_FOR_RETRACEMENT"  # qualified, limit resting
    REJECTED = "REJECTED"                 # qualified, a gate said no
    SHADOW = "SHADOW"                     # qualified, suppressed by shadow mode
    ACTIVE = "ACTIVE"                     # order accepted by the broker
    ERROR = "ERROR"                       # exception on the evaluation path


# Machine-readable rejection codes. Every one maps to a specific, non-generic
# operator-facing explanation. ``run_mt5_engine`` may not invent new strings.
class Reason(str, Enum):
    # --- data / setup ---
    NO_MT5_RATES = "NO_MT5_RATES"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_SYMBOL_SPEC = "NO_SYMBOL_SPEC"
    STALE_DATA = "STALE_DATA"
    NO_CRT_RANGE = "NO_CRT_RANGE"
    NO_LIQUIDITY_SWEEP = "NO_LIQUIDITY_SWEEP"
    SWEEP_INVALIDATED = "SWEEP_INVALIDATED"
    # --- confluence ---
    AWAITING_KOD_DISPLACEMENT = "AWAITING_KOD_DISPLACEMENT"
    KOD_NOT_CONFIRMED = "KOD_NOT_CONFIRMED"
    AWAITING_HTF_CONFIRMATION = "AWAITING_HTF_CONFIRMATION"
    HTF_CONFLICT = "HTF_CONFLICT"
    HTF_DATA_UNAVAILABLE = "HTF_DATA_UNAVAILABLE"
    FVG_CE_NOT_MITIGATED = "FVG_CE_NOT_MITIGATED"
    BELOW_TIER_1 = "BELOW_TIER_1"
    TIER_NOT_QUALIFIED = "TIER_NOT_QUALIFIED"
    # --- risk / session / execution ---
    AUTOTRADING_DISABLED = "AUTOTRADING_DISABLED"
    SESSION_CLOSED = "SESSION_CLOSED"
    EAT_PHASE_BLOCK = "EAT_PHASE_BLOCK"
    NEWS_BLACKOUT = "NEWS_BLACKOUT"
    ADAPTIVE_BRAIN_BLOCK = "ADAPTIVE_BRAIN_BLOCK"
    RISK_CAP_REACHED = "RISK_CAP_REACHED"
    DUPLICATE_OPEN_POSITION = "DUPLICATE_OPEN_POSITION"
    EXECUTION_COOLDOWN = "EXECUTION_COOLDOWN"
    CORRELATION_BLOCK = "CORRELATION_BLOCK"
    SPREAD_ABSOLUTE_CAP = "SPREAD_ABSOLUTE_CAP"
    SPREAD_RISK_RATIO = "SPREAD_RISK_RATIO"
    GATE_SPREAD = "GATE_SPREAD"
    GATE_VOLATILITY = "GATE_VOLATILITY"
    GATE_MOMENTUM_ADX = "GATE_MOMENTUM_ADX"
    GATE_MOMENTUM_RSI = "GATE_MOMENTUM_RSI"
    GATE_LATE_ENTRY = "GATE_LATE_ENTRY"
    GATE_LIQUIDITY_VOLUME = "GATE_LIQUIDITY_VOLUME"
    GATE_MORNING_GUARD = "GATE_MORNING_GUARD"
    GATE_MISSING_TICK = "GATE_MISSING_TICK"
    MARKET_CLOSED = "MARKET_CLOSED"
    INVALID_LOT_SIZE = "INVALID_LOT_SIZE"
    LIMIT_NOT_REACHED = "LIMIT_NOT_REACHED"
    PRICE_RETRACED_TOO_FAR = "PRICE_RETRACED_TOO_FAR"
    # --- terminal successes / broker ---
    SHADOW_MODE = "SHADOW_MODE"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PENDING = "ORDER_PENDING"
    EVALUATION_ERROR = "EVALUATION_ERROR"


#: Human-readable template for every code, so no caller can emit a generic
#: message such as "blocked" or "rejected".
REASON_TEXT: dict[str, str] = {
    Reason.NO_MT5_RATES: "MT5 returned no rate history for this symbol/timeframe",
    Reason.INSUFFICIENT_HISTORY: "fewer than 60 completed candles available",
    Reason.NO_SYMBOL_SPEC: "MT5 has no symbol specification for this instrument",
    Reason.STALE_DATA: "latest candle timestamp is stale; refusing to score old prices",
    Reason.NO_CRT_RANGE: "no CRT range could be built from the lookback window",
    Reason.NO_LIQUIDITY_SWEEP: "no buy-side or sell-side liquidity sweep in the lookback window",
    Reason.SWEEP_INVALIDATED: "sweep invalidated - a later candle closed beyond the swept level",
    Reason.AWAITING_KOD_DISPLACEMENT: "sweep is on the newest completed candle; the displacement candle has not formed yet",
    Reason.KOD_NOT_CONFIRMED: "KOD displacement did not confirm",
    Reason.AWAITING_HTF_CONFIRMATION: "higher-timeframe bias not yet confirmed for this direction",
    Reason.HTF_CONFLICT: "higher-timeframe bias opposes the trade direction",
    Reason.HTF_DATA_UNAVAILABLE: "higher-timeframe candles unavailable; alignment cannot be proven",
    Reason.FVG_CE_NOT_MITIGATED: "price has not traded into the 50% consequent encroachment of an aligned FVG",
    Reason.BELOW_TIER_1: "confluence score below the Tier 1 threshold",
    Reason.TIER_NOT_QUALIFIED: "score reached but tier-specific confluences missing",
    Reason.AUTOTRADING_DISABLED: "autotrading is switched off in broker settings",
    Reason.SESSION_CLOSED: "outside the configured liquid trading session",
    Reason.EAT_PHASE_BLOCK: "blocked by the EAT phase engine (session gap / asset phase)",
    Reason.NEWS_BLACKOUT: "high-impact news blackout window active for this instrument",
    Reason.ADAPTIVE_BRAIN_BLOCK: "adaptive brain has quarantined this symbol",
    Reason.RISK_CAP_REACHED: "account risk cap reached (max open positions / daily trades / drawdown)",
    Reason.DUPLICATE_OPEN_POSITION: "a position is already open on this symbol",
    Reason.EXECUTION_COOLDOWN: "an order was already executed on this symbol/direction inside the cooldown window",
    Reason.CORRELATION_BLOCK: "correlated exposure limit reached",
    Reason.SPREAD_ABSOLUTE_CAP: "spread exceeds the configured absolute pip cap",
    Reason.SPREAD_RISK_RATIO: "spread exceeds the permitted fraction of the entry-to-stop distance",
    Reason.GATE_SPREAD: "execution gate: transaction cost too high",
    Reason.GATE_VOLATILITY: "execution gate: ATR below the timeframe-scaled volatility floor",
    Reason.GATE_MOMENTUM_ADX: "execution gate: market trending too hard to fade a liquidity sweep",
    Reason.GATE_MOMENTUM_RSI: "execution gate: RSI not extended enough to fade the sweep",
    Reason.GATE_LATE_ENTRY: "execution gate: price drifted too far from the signalled entry",
    Reason.GATE_LIQUIDITY_VOLUME: "execution gate: zero or stagnant bar volume",
    Reason.GATE_MORNING_GUARD: "execution gate: pre-London morning guard",
    Reason.GATE_MISSING_TICK: "execution gate: no live tick or symbol info available",
    Reason.MARKET_CLOSED: "market closed or trading disabled for this symbol",
    Reason.INVALID_LOT_SIZE: "computed lot size is zero or below the broker minimum",
    Reason.LIMIT_NOT_REACHED: "limit entry resting; price has not reached the entry level",
    Reason.PRICE_RETRACED_TOO_FAR: "price retraced beyond the invalidation level before entry",
    Reason.SHADOW_MODE: "shadow mode enabled - order constructed but not transmitted",
    Reason.ORDER_REJECTED: "broker rejected the order",
    Reason.ORDER_FILLED: "order filled",
    Reason.ORDER_PENDING: "pending order accepted by the broker",
    Reason.EVALUATION_ERROR: "unhandled exception during evaluation",
}


def describe(code: str, detail: str = "") -> str:
    """Compose a non-generic human-readable reason for ``code``."""
    base = REASON_TEXT.get(code, code.replace("_", " ").lower())
    return f"{base}: {detail}" if detail else base


# --------------------------------------------------------------------------- #
# Session classification
# --------------------------------------------------------------------------- #

def classify_session(now: datetime, cfg=None) -> str:
    """Bucket ``now`` (UTC) into LONDON / NEW_YORK / OVERLAP / ASIA / OFF.

    Used to split the validation statistics by trading session, which is what
    Phase 8 of the brief asks for. Windows come from ``StrategyConfig`` so the
    report and the engine can never disagree about when London starts.
    """
    if cfg is None:
        from trading_engine.strategy_config import CONFIG as cfg  # local import: avoids a cycle
    u = now.astimezone(timezone.utc)
    hour = u.hour + u.minute / 60.0

    def inside(window: tuple[float, float]) -> bool:
        start, end = window
        return start <= hour < end if start <= end else (hour >= start or hour < end)

    in_london = inside(cfg.sessions.london)
    in_ny = inside(cfg.sessions.new_york)
    if in_london and in_ny:
        return "OVERLAP"
    if in_london:
        return "LONDON"
    if in_ny:
        return "NEW_YORK"
    if inside(cfg.sessions.tokyo) or inside(cfg.sessions.sydney):
        return "ASIA"
    return "OFF"


# --------------------------------------------------------------------------- #
# SignalTrace
# --------------------------------------------------------------------------- #

@dataclass
class SignalTrace:
    """The complete, ordered lifecycle of one symbol/timeframe evaluation."""

    symbol: str
    timeframe: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stages: list[str] = field(default_factory=list)
    details: "OrderedDict[str, str]" = field(default_factory=OrderedDict)
    facts: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    reason_code: str = ""
    reason_text: str = ""
    terminated: bool = False
    signal_id: int | None = None

    # -- recording ---------------------------------------------------------- #

    def mark(self, stage: Stage, detail: str = "", **facts: Any) -> "SignalTrace":
        """Record that ``stage`` was reached, with optional supporting facts."""
        self.stages.append(stage.value)
        if detail:
            self.details[stage.value] = detail
        if facts:
            self.facts.update({k: _jsonable(v) for k, v in facts.items()})
        return self

    def fact(self, **facts: Any) -> "SignalTrace":
        """Attach facts without advancing the funnel."""
        self.facts.update({k: _jsonable(v) for k, v in facts.items()})
        return self

    def reached(self, stage: Stage) -> bool:
        return stage.value in self.stages

    def terminate(self, outcome: Outcome, code: Reason | str, detail: str = "") -> "SignalTrace":
        """End the evaluation with an explicit, machine-readable reason.

        This is the *only* way an evaluation may end. ``code`` is always one of
        :class:`Reason`, and ``reason_text`` is always a full sentence — there
        is no code path that produces "blocked" or "rejected" on its own.
        """
        code_value = code.value if isinstance(code, Reason) else str(code)
        self.outcome = outcome.value if isinstance(outcome, Outcome) else str(outcome)
        self.reason_code = code_value
        self.reason_text = describe(code_value, detail)
        self.terminated = True
        return self

    # -- rendering ---------------------------------------------------------- #

    @property
    def elapsed_ms(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000.0

    def arrow_chain(self) -> str:
        """``SCANNED -> CRT_CONFIRMED -> ... -> WATCHLIST`` for the log."""
        chain = list(self.stages)
        if self.outcome:
            chain.append(self.outcome)
        return " -> ".join(chain)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "started_at": self.started_at.isoformat(),
            "elapsed_ms": round(self.elapsed_ms, 1),
            "stages": list(self.stages),
            "stage_details": dict(self.details),
            "facts": dict(self.facts),
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "signal_id": self.signal_id,
        }

    def log(self, log=logger, level: int = logging.INFO) -> None:
        """Emit the single canonical LIFECYCLE line for this evaluation."""
        log.log(
            level,
            "LIFECYCLE %s %s | %s | code=%s | %s | %s",
            self.symbol,
            self.timeframe,
            self.arrow_chain(),
            self.reason_code or "-",
            self.reason_text or "-",
            " ".join(f"{k}={v}" for k, v in self.facts.items()) or "-",
        )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


# --------------------------------------------------------------------------- #
# FunnelCounters
# --------------------------------------------------------------------------- #

@dataclass
class _SessionBucket:
    stages: Counter = field(default_factory=Counter)
    outcomes: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)
    scores: list[float] = field(default_factory=list)
    spreads: list[float] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)
    htf: Counter = field(default_factory=Counter)
    tiers: Counter = field(default_factory=Counter)
    kod_subchecks: Counter = field(default_factory=Counter)


class FunnelCounters:
    """Thread-safe funnel aggregation for the whole process.

    Two views are kept simultaneously:

    * **cumulative** — since process start, used by the validation report;
    * **per-session** — LONDON / NEW_YORK / OVERLAP / ASIA / OFF, which is what
      Phase 8 requires.
    """

    #: Rolling window of the most recent traces retained for the dashboard.
    RECENT_LIMIT = 400

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.started_at = datetime.now(timezone.utc)
        self.cycles = 0
        self._all = _SessionBucket()
        self._sessions: dict[str, _SessionBucket] = {}
        self._recent: deque[dict[str, Any]] = deque(maxlen=self.RECENT_LIMIT)
        self._watchlist: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    # -- ingestion ---------------------------------------------------------- #

    def _bucket(self, session: str) -> _SessionBucket:
        if session not in self._sessions:
            self._sessions[session] = _SessionBucket()
        return self._sessions[session]

    def record(self, trace: SignalTrace, session: str | None = None) -> None:
        """Fold one completed :class:`SignalTrace` into the counters."""
        session = session or classify_session(trace.started_at)
        with self._lock:
            for bucket in (self._all, self._bucket(session)):
                for stage in dict.fromkeys(trace.stages):  # de-duplicate, keep order
                    bucket.stages[stage] += 1
                if trace.outcome:
                    bucket.outcomes[trace.outcome] += 1
                if trace.reason_code:
                    bucket.reasons[trace.reason_code] += 1
                score = trace.facts.get("score")
                if isinstance(score, (int, float)):
                    bucket.scores.append(float(score))
                spread = trace.facts.get("spread_pips")
                if isinstance(spread, (int, float)):
                    bucket.spreads.append(float(spread))
                latency = trace.facts.get("order_latency_ms")
                if isinstance(latency, (int, float)):
                    bucket.latencies.append(float(latency))
                htf = trace.facts.get("htf_status")
                if htf:
                    bucket.htf[str(htf)] += 1
                tier = trace.facts.get("tier")
                if tier:
                    bucket.tiers[str(tier)] += 1
                sub = trace.facts.get("kod_subcheck")
                if sub:
                    bucket.kod_subchecks[str(sub)] += 1

            self._recent.append(trace.as_dict())
            key = f"{trace.symbol}|{trace.timeframe}"
            if trace.outcome in {Outcome.WATCHLIST.value, Outcome.WAITING_FOR_RETRACEMENT.value}:
                self._watchlist[key] = {
                    "symbol": trace.symbol,
                    "timeframe": trace.timeframe,
                    "outcome": trace.outcome,
                    "reason_code": trace.reason_code,
                    "reason_text": trace.reason_text,
                    "score": trace.facts.get("score"),
                    "tier": trace.facts.get("tier"),
                    "direction": trace.facts.get("direction"),
                    "htf_status": trace.facts.get("htf_status"),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "signal_id": trace.signal_id,
                }
                self._watchlist.move_to_end(key)
                while len(self._watchlist) > self.RECENT_LIMIT:
                    self._watchlist.popitem(last=False)
            else:
                self._watchlist.pop(key, None)

    def cycle_complete(self) -> int:
        with self._lock:
            self.cycles += 1
            return self.cycles

    def note_kod_subchecks(self, results: dict[str, bool], session: str | None = None) -> None:
        """Record which individual KOD sub-checks passed on one evaluation."""
        session = session or classify_session(datetime.now(timezone.utc))
        with self._lock:
            for bucket in (self._all, self._bucket(session)):
                bucket.kod_subchecks["_evaluated"] += 1
                for name, ok in results.items():
                    if ok:
                        bucket.kod_subchecks[name] += 1

    # -- reporting ---------------------------------------------------------- #

    def _funnel_rows(self, bucket: _SessionBucket) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        top = bucket.stages.get(Stage.SCANNED.value, 0)
        previous = top
        for stage in FUNNEL_ORDER:
            count = bucket.stages.get(stage.value, 0)
            rows.append({
                "stage": stage.value,
                "count": count,
                "pct_of_scanned": round(count / top * 100.0, 2) if top else 0.0,
                "pct_of_previous": round(count / previous * 100.0, 2) if previous else 0.0,
            })
            previous = count if count else previous
        return rows

    @staticmethod
    def _stats(values: Iterable[float]) -> dict[str, float]:
        data = [v for v in values]
        if not data:
            return {"count": 0, "min": 0.0, "avg": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
        data_sorted = sorted(data)
        idx95 = min(len(data_sorted) - 1, int(round(0.95 * (len(data_sorted) - 1))))
        return {
            "count": len(data_sorted),
            "min": round(data_sorted[0], 4),
            "avg": round(statistics.fmean(data_sorted), 4),
            "median": round(statistics.median(data_sorted), 4),
            "p95": round(data_sorted[idx95], 4),
            "max": round(data_sorted[-1], 4),
        }

    def _bucket_dict(self, bucket: _SessionBucket) -> dict[str, Any]:
        evaluated = bucket.kod_subchecks.get("_evaluated", 0)
        return {
            "funnel": self._funnel_rows(bucket),
            "outcomes": dict(bucket.outcomes.most_common()),
            "rejection_reasons": [
                {"code": code, "count": n, "text": REASON_TEXT.get(code, code)}
                for code, n in bucket.reasons.most_common()
            ],
            "score": self._stats(bucket.scores),
            "spread_pips": self._stats(bucket.spreads),
            "order_latency_ms": self._stats(bucket.latencies),
            "htf_distribution": dict(bucket.htf.most_common()),
            "tier_distribution": dict(bucket.tiers.most_common()),
            "kod_subcheck_pass_rate": {
                name: {
                    "passed": n,
                    "evaluated": evaluated,
                    "pct": round(n / evaluated * 100.0, 2) if evaluated else 0.0,
                }
                for name, n in sorted(bucket.kod_subchecks.items())
                if name != "_evaluated"
            },
        }

    def snapshot(self, include_recent: bool = True) -> dict[str, Any]:
        with self._lock:
            data: dict[str, Any] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "started_at": self.started_at.isoformat(),
                "uptime_seconds": round((datetime.now(timezone.utc) - self.started_at).total_seconds(), 1),
                "scan_cycles": self.cycles,
                "current_session": classify_session(datetime.now(timezone.utc)),
                "cumulative": self._bucket_dict(self._all),
                "by_session": {name: self._bucket_dict(b) for name, b in sorted(self._sessions.items())},
                "watchlist_reasons": list(reversed(list(self._watchlist.values()))),
            }
            if include_recent:
                data["recent_traces"] = list(reversed(list(self._recent)))[:120]
            return data

    def render_text(self, session: str | None = None) -> str:
        """ASCII funnel with per-stage percentages, for the engine log."""
        with self._lock:
            bucket = self._all if session is None else self._sessions.get(session, _SessionBucket())
            rows = self._funnel_rows(bucket)
        title = f"FUNNEL ({session or 'CUMULATIVE'}) after {self.cycles} scan cycles"
        lines = [title, "-" * len(title)]
        for row in rows:
            bar = "#" * int(row["pct_of_scanned"] / 2.5)
            lines.append(
                f"  {row['stage']:<22} {row['count']:>8}  "
                f"{row['pct_of_scanned']:>6.2f}% of scanned  "
                f"{row['pct_of_previous']:>6.2f}% of prev  {bar}"
            )
        top_reasons = bucket.reasons.most_common(8)
        if top_reasons:
            lines.append("  top rejection reasons:")
            total_reasons = sum(bucket.reasons.values()) or 1
            for code, n in top_reasons:
                lines.append(
                    f"    {code:<28} {n:>7}  {n / total_reasons * 100:>5.1f}%  "
                    f"{REASON_TEXT.get(code, '')}"
                )
        return "\n".join(lines)

    def write_snapshot(self, path: str) -> str | None:
        """Persist the snapshot atomically so readers never see a partial file."""
        try:
            directory = os.path.dirname(os.path.abspath(path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.snapshot(), handle, indent=2, default=str)
            os.replace(tmp, path)
            return path
        except Exception as exc:  # pragma: no cover - disk failures only
            logger.warning("Could not write funnel snapshot to %s: %s", path, exc)
            return None


#: Process-wide funnel. ``run_mt5_engine`` feeds it; the API endpoint reads the
#: snapshot file so the web process never needs shared memory with the engine.
FUNNEL = FunnelCounters()


def timed() -> float:
    """Monotonic timestamp helper, kept here so callers need no extra import."""
    return time.perf_counter()
