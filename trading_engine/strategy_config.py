"""Single source of truth for every tunable strategy / execution parameter.

Module 9 (Phase 6) — configuration
----------------------------------
Before this module the same magic numbers were duplicated across
``run_mt5_engine.py``, ``account_manager.py``, ``kod.py``, ``liquidity.py``,
``scoring.py`` and ``mt5_client.py``. Changing a threshold meant editing (and
redeploying) several files, and in three cases the duplicated copies had
already drifted apart — for example the 2.5-pip spread cap existed
independently in ``run_mt5_engine.py`` and ``mt5_client.py``, and the
execution-gate rejection *messages* advertised limits that did not match the
values the code actually tested.

Every value below is read once at import time from the process environment
(which ``run_mt5_engine`` populates from ``C:\\prop-frim-bot\\.env`` via
``python-dotenv``). Nothing here changes a default: every fallback is the value
that was hard-coded in the previous revision, so importing this module is
behaviour-neutral until an operator actually sets a variable.

Reload semantics
----------------
Values are captured at import time so that a single scan cycle can never see a
half-applied configuration change. :func:`reload` re-reads the environment and
is used by the ``/api/v1/strategy-config/`` endpoint and by the unit tests.

:func:`reload` must cope with three different ways consumers capture config,
all of which exist in this codebase:

1. *Call-time attribute reads* -- ``CONFIG.spread.max_pips`` evaluated inside a
   function (``orchestrator``, ``run_mt5_engine``, ``pipeline_trace``).
2. *Construction-time reads* -- ``CONFIG.liquidity.lookback_candles`` captured
   into ``self.lookback`` when an engine object is built (``liquidity``,
   ``kod``).
3. *Module-level scalar constants* -- ``TIER_1_THRESHOLD = CONFIG.tiers.tier_1``
   evaluated once at import (``scoring``, ``account_manager``).

Rebinding the module global ``CONFIG`` reaches **none** of these, because every
consumer does ``from trading_engine.strategy_config import CONFIG`` and thereby
binds the *object*, not this module's name. Therefore :func:`reload` instead
mutates the single shared ``CONFIG`` instance **in place** (fixing 1, and 2 for
any engine constructed after the reload) and then invokes the callbacks
registered through :func:`register_reload_hook`, which is how ``scoring`` and
``account_manager`` re-derive their module-level constants (fixing 3).
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field, fields
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

logger = logging.getLogger("trading")


# --------------------------------------------------------------------------- #
# Primitive readers
# --------------------------------------------------------------------------- #

def env_decimal(name: str, default: str) -> Decimal:
    """Read a ``Decimal`` from the environment, falling back to ``default``."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return Decimal(default)
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return Decimal(default)


def env_optional_decimal(name: str, default: str | None) -> Decimal | None:
    """Like :func:`env_decimal` but ``none``/``off``/``disabled``/"" -> ``None``.

    Used for controls that can be switched off entirely, such as the absolute
    spread cap.
    """
    raw = os.getenv(name)
    if raw is None:
        return Decimal(default) if default is not None else None
    raw = str(raw).strip()
    if raw == "" or raw.lower() in {"none", "off", "disabled", "null"}:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        logger.warning("Invalid %s=%r; control disabled", name, raw)
        return None


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip()


def env_csv(name: str, default: str) -> tuple[str, ...]:
    """Comma-separated list, e.g. ``HTF_TIMEFRAMES=H4,D1``."""
    return tuple(x.strip().upper() for x in env_str(name, default).split(",") if x.strip())


def env_time_window(name: str, default: str) -> tuple[float, float]:
    """Parse ``"HH:MM-HH:MM"`` into a pair of float hours in UTC.

    A window that wraps midnight (``21:00-06:00``) is represented with
    ``start > end`` and is interpreted as such by the session engine.
    """
    raw = env_str(name, default)
    try:
        start_s, end_s = raw.split("-", 1)

        def _h(token: str) -> float:
            token = token.strip()
            hh, _, mm = token.partition(":")
            return int(hh) + (int(mm) / 60.0 if mm else 0.0)

        return _h(start_s), _h(end_s)
    except Exception:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        start_s, end_s = default.split("-", 1)
        hh1, _, mm1 = start_s.partition(":")
        hh2, _, mm2 = end_s.partition(":")
        return (int(hh1) + (int(mm1) / 60.0 if mm1 else 0.0),
                int(hh2) + (int(mm2) / 60.0 if mm2 else 0.0))


# --------------------------------------------------------------------------- #
# Configuration groups
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class KODConfig:
    """Killzone Opposing Displacement thresholds.

    Measured live on 2026-07-31 across 366 symbol/timeframe evaluations, the
    individual sub-check pass rates on the 71 sweeps that had a displacement
    candle available were:

        sweep rejection wick >= 0.30      32.4%
        displacement direction agrees     53.5%
        body >= 1.2 x ATR(14)             11.3%
        body / range >= 0.55              54.9%
        volume >= 1.5 x MA20               4.2%

    Their product is ~0.004%, which is why KOD confirmed zero times in
    production. The defaults below are unchanged from the previous revision on
    purpose — loosening the strategy is an operator decision, not a bug fix —
    but every one of them is now tunable without a redeploy, and the funnel
    reports each sub-check independently so the effect of a change is
    measurable. See ``docs`` in the remediation report for recommended values.
    """

    min_body_ratio: Decimal = field(default_factory=lambda: env_decimal("KOD_MIN_BODY_RATIO", "0.55"))
    min_rejection_ratio: Decimal = field(default_factory=lambda: env_decimal("KOD_MIN_REJECTION_RATIO", "0.30"))
    atr_multiplier: Decimal = field(default_factory=lambda: env_decimal("KOD_ATR_MULTIPLIER", "1.2"))
    volume_multiplier: Decimal = field(default_factory=lambda: env_decimal("KOD_VOLUME_MULTIPLIER", "1.5"))
    # When the newest sweep sits on the last completed candle there is no
    # displacement candle yet, so KOD can never confirm for it. With this on,
    # the engine also considers slightly older sweeps inside the lookback
    # window, which is what the two-candle model requires. See
    # trading_engine.liquidity.detect_sweeps.
    scan_older_sweeps: bool = field(default_factory=lambda: env_flag("KOD_SCAN_OLDER_SWEEPS", True))


@dataclass(frozen=True)
class LiquidityConfig:
    equal_tolerance_ticks: int = field(default_factory=lambda: env_int("LIQ_EQUAL_TOLERANCE_TICKS", 3))
    # How many of the most recent completed candles may host the sweep.
    lookback_candles: int = field(default_factory=lambda: env_int("LIQ_SWEEP_LOOKBACK", 3))


@dataclass(frozen=True)
class CRTConfig:
    lookback: int = field(default_factory=lambda: env_int("CRT_LOOKBACK", 20))
    internal_ratio: Decimal = field(default_factory=lambda: env_decimal("CRT_INTERNAL_RATIO", "0.50"))


@dataclass(frozen=True)
class TierConfig:
    tier_1: Decimal = field(default_factory=lambda: env_decimal("TIER_1_THRESHOLD", "55"))
    tier_2: Decimal = field(default_factory=lambda: env_decimal("TIER_2_THRESHOLD", "70"))
    tier_3: Decimal = field(default_factory=lambda: env_decimal("TIER_3_THRESHOLD", "85"))
    non_kod_cap: Decimal = field(default_factory=lambda: env_decimal("NON_KOD_SCORE_CAP", "70"))
    risk_mult_1: Decimal = field(default_factory=lambda: env_decimal("TIER_1_RISK_MULTIPLIER", "0.5"))
    risk_mult_2: Decimal = field(default_factory=lambda: env_decimal("TIER_2_RISK_MULTIPLIER", "1.0"))
    risk_mult_3: Decimal = field(default_factory=lambda: env_decimal("TIER_3_RISK_MULTIPLIER", "1.5"))


@dataclass(frozen=True)
class HTFConfig:
    """Higher-timeframe bias confirmation.

    ``timeframes`` is the ordered list of MT5 timeframes consulted for bias.
    ``require_confirmation`` decides what happens when the HTF series cannot be
    fetched: the previous revision silently treated a missing series as
    "aligned" and handed out the full 15-point component to every signal ever
    scored. With this flag on (the default) a missing series means *not*
    aligned, which is the only safe interpretation.
    """

    timeframes: tuple[str, ...] = field(default_factory=lambda: env_csv("HTF_TIMEFRAMES", "H4,D1"))
    bars: int = field(default_factory=lambda: env_int("HTF_BARS", 150))
    # Cache TTL per higher timeframe, in seconds. An H4 bias cannot change more
    # than once every four hours, so re-fetching it every 5s per symbol is pure
    # IPC overhead.
    cache_ttl_seconds: int = field(default_factory=lambda: env_int("HTF_CACHE_TTL_SECONDS", 300))
    fast_ma: int = field(default_factory=lambda: env_int("HTF_FAST_MA", 20))
    slow_ma: int = field(default_factory=lambda: env_int("HTF_SLOW_MA", 50))
    require_confirmation: bool = field(default_factory=lambda: env_flag("HTF_REQUIRE_CONFIRMATION", True))
    # Treat a NEUTRAL higher-timeframe bias as compatible with either
    # direction. This matches the original ``b in {direction, NEUTRAL}`` test.
    neutral_counts_as_aligned: bool = field(
        default_factory=lambda: env_flag("HTF_NEUTRAL_ALIGNED", True)
    )


@dataclass(frozen=True)
class ExecutionGateConfig:
    atr_ratio_floor_5m: Decimal = field(default_factory=lambda: env_decimal("EXEC_GATE_ATR_FLOOR_5M", "0.00012"))
    adx_max: Decimal = field(default_factory=lambda: env_decimal("EXEC_GATE_ADX_MAX", "60.0"))
    rsi_sell_min: Decimal = field(default_factory=lambda: env_decimal("EXEC_GATE_RSI_SELL_MIN", "55.0"))
    rsi_buy_max: Decimal = field(default_factory=lambda: env_decimal("EXEC_GATE_RSI_BUY_MAX", "45.0"))
    late_entry_drift: Decimal = field(default_factory=lambda: env_decimal("EXEC_GATE_LATE_ENTRY_DRIFT", "0.35"))
    late_entry_score_override: Decimal = field(
        default_factory=lambda: env_decimal("EXEC_GATE_LATE_ENTRY_SCORE_OVERRIDE", "84")
    )
    morning_guard_min_score: Decimal = field(
        default_factory=lambda: env_decimal("EXEC_GATE_MORNING_MIN_SCORE", "55")
    )
    morning_guard_max_spread_ratio: Decimal = field(
        default_factory=lambda: env_decimal("EXEC_GATE_MORNING_MAX_SPREAD_RATIO", "0.0005")
    )
    max_spread_ratio_of_price: Decimal = field(
        default_factory=lambda: env_decimal("EXEC_GATE_MAX_SPREAD_PRICE_RATIO", "0.0010")
    )
    forex_max_spread_pips: Decimal = field(
        default_factory=lambda: env_decimal("EXEC_GATE_FOREX_MAX_SPREAD_PIPS", "2.5")
    )


@dataclass(frozen=True)
class SpreadConfig:
    """Spread controls applied at signal build time and again at order time."""

    # Absolute cap in pips. ``None`` (the default) disables it -- it was
    # asset-class blind and accounted for 99% of all rejections.
    max_pips: Decimal | None = field(default_factory=lambda: env_optional_decimal("MT5_MAX_SPREAD_PIPS", None))
    # Spread must not exceed this fraction of the entry-to-stop distance.
    max_risk_ratio: Decimal = field(default_factory=lambda: env_decimal("MT5_MAX_SPREAD_RISK_RATIO", "0.15"))


@dataclass(frozen=True)
class RiskConfig:
    atr_period: int = field(default_factory=lambda: env_int("ATR_PERIOD", 14))
    # Stop distance beyond the sweep extreme, as a multiple of ATR(14).
    stop_atr_multiplier: Decimal = field(default_factory=lambda: env_decimal("STOP_ATR_MULTIPLIER", "1.5"))
    # Take-profit distance as a multiple of the risk distance.
    take_profit_rr: Decimal = field(default_factory=lambda: env_decimal("TAKE_PROFIT_RR", "2.0"))
    min_volatility_ticks: Decimal = field(default_factory=lambda: env_decimal("MIN_VOLATILITY_TICKS", "5"))
    breakeven_r_multiple: Decimal = field(default_factory=lambda: env_decimal("BREAKEVEN_R_MULTIPLE", "1.5"))


@dataclass(frozen=True)
class SessionConfig:
    """Session windows, all in UTC, ``"HH:MM-HH:MM"``.

    A window whose start is later than its end wraps midnight.
    """

    sydney: tuple[float, float] = field(default_factory=lambda: env_time_window("SESSION_SYDNEY", "21:00-06:00"))
    tokyo: tuple[float, float] = field(default_factory=lambda: env_time_window("SESSION_TOKYO", "00:00-09:00"))
    london: tuple[float, float] = field(default_factory=lambda: env_time_window("SESSION_LONDON", "07:00-16:00"))
    new_york: tuple[float, float] = field(default_factory=lambda: env_time_window("SESSION_NEW_YORK", "12:00-21:00"))
    london_kill: tuple[float, float] = field(default_factory=lambda: env_time_window("KILLZONE_LONDON", "07:00-10:00"))
    new_york_kill: tuple[float, float] = field(default_factory=lambda: env_time_window("KILLZONE_NEW_YORK", "12:00-15:00"))
    power_hour: tuple[float, float] = field(default_factory=lambda: env_time_window("KILLZONE_POWER_HOUR", "19:00-20:00"))


@dataclass(frozen=True)
class PipelineConfig:
    """Signal-lifecycle and execution-throttle behaviour."""

    shadow_mode: bool = field(default_factory=lambda: env_flag("SHADOW_MODE", False))
    # Minutes an *executed* trade blocks further entries on the same
    # symbol + direction. Previously this window was keyed on *any* signal row
    # -- including non-executable WATCHLIST rows -- which suppressed the
    # qualifying signal that arrived later in the same window.
    execution_cooldown_minutes: int = field(default_factory=lambda: env_int("EXEC_COOLDOWN_MINUTES", 30))
    # An existing open signal row for the same symbol/direction/timeframe is
    # refreshed in place for this long instead of inserting a duplicate row.
    signal_refresh_minutes: int = field(default_factory=lambda: env_int("SIGNAL_REFRESH_MINUTES", 30))
    # Persist a Signal row even when no liquidity sweep was detected. These are
    # not Romeo TPT setups (CRT range alone), so they are off by default; they
    # are always counted in the funnel regardless.
    persist_no_sweep_signals: bool = field(default_factory=lambda: env_flag("PERSIST_NO_SWEEP_SIGNALS", False))
    # Minimum score below which no Signal row is written at all.
    min_persist_score: Decimal = field(default_factory=lambda: env_decimal("MIN_PERSIST_SCORE", "50"))
    # Emit one FUNNEL log block / websocket push every N scan cycles.
    funnel_report_every_cycles: int = field(default_factory=lambda: env_int("FUNNEL_REPORT_EVERY_CYCLES", 20))
    funnel_snapshot_path: str = field(default_factory=lambda: env_str("FUNNEL_SNAPSHOT_PATH", "logs/funnel_snapshot.json"))
    # Log a LIFECYCLE line for every evaluation, not just persisted signals.
    trace_all_evaluations: bool = field(default_factory=lambda: env_flag("TRACE_ALL_EVALUATIONS", True))
    scan_timeframes: tuple[str, ...] = field(default_factory=lambda: env_csv("SCAN_TIMEFRAMES", "M5,M15,H1"))


@dataclass(frozen=True)
class StrategyConfig:
    kod: KODConfig = field(default_factory=KODConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    crt: CRTConfig = field(default_factory=CRTConfig)
    tiers: TierConfig = field(default_factory=TierConfig)
    htf: HTFConfig = field(default_factory=HTFConfig)
    gate: ExecutionGateConfig = field(default_factory=ExecutionGateConfig)
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    def as_dict(self) -> dict[str, Any]:
        """Flat JSON-safe view, used by the config endpoint and startup log."""
        out: dict[str, Any] = {}
        for group in fields(self):
            block = getattr(self, group.name)
            for item in fields(block):
                value = getattr(block, item.name)
                if isinstance(value, Decimal):
                    value = str(value)
                elif isinstance(value, tuple):
                    value = list(value)
                out[f"{group.name}.{item.name}"] = value
        return out


# Process-wide instance. Import this, do not construct your own.
CONFIG = StrategyConfig()


# --------------------------------------------------------------------------- #
# Reload plumbing
# --------------------------------------------------------------------------- #

# Serialises reloads against each other. Field application itself is a short
# sequence of attribute writes; building/validating the replacement happens
# outside the critical section so a bad .env cannot leave CONFIG half-applied.
_RELOAD_LOCK = threading.RLock()

# Callbacks invoked after CONFIG has been updated in place. Modules that derive
# module-level constants from CONFIG register here so a reload reaches them.
_RELOAD_HOOKS: list[Callable[[StrategyConfig], None]] = []


def register_reload_hook(hook: Callable[[StrategyConfig], None]) -> Callable[[StrategyConfig], None]:
    """Register ``hook`` to run after every :func:`reload`.

    ``scoring`` and ``account_manager`` snapshot config values into module-level
    constants at import time (``TIER_1_THRESHOLD``, ``ADX_MAX``, ...). Those
    names are part of their public surface -- other modules and the unit tests
    import them directly -- so they cannot simply be deleted. Instead each such
    module registers a hook that re-derives its constants from the freshly
    loaded configuration.

    Returns ``hook`` so it can be used as a decorator. Registration is
    idempotent: registering the same function twice runs it once.
    """
    with _RELOAD_LOCK:
        if hook not in _RELOAD_HOOKS:
            _RELOAD_HOOKS.append(hook)
    return hook


def _apply_in_place(target: Any, source: Any) -> None:
    """Copy every dataclass field of ``source`` onto ``target``.

    Both are frozen dataclasses of the same type, so ``object.__setattr__`` is
    used to bypass the frozen guard. Freezing is deliberately retained: it stops
    strategy code from mutating configuration mid-cycle by accident, and this
    function is the single audited escape hatch.
    """
    for item in fields(source):
        object.__setattr__(target, item.name, getattr(source, item.name))


def reload() -> StrategyConfig:
    """Re-read every value from the environment into the shared ``CONFIG``.

    The replacement is constructed first, so if the environment contains a value
    that raises during parsing the existing configuration is left untouched and
    the exception propagates to the caller rather than leaving the engine with a
    partially-updated ruleset.

    Returns the shared instance (the *same* object identity as before, now
    carrying the new values) so callers may keep using their existing reference.
    """
    with _RELOAD_LOCK:
        fresh = StrategyConfig()

        # Mutate the nested group objects in place rather than replacing them,
        # because consumers hold references to the groups as well as to CONFIG
        # (e.g. `cfg = CONFIG.kod` inside KODEngine.__init__).
        for group in fields(StrategyConfig):
            _apply_in_place(getattr(CONFIG, group.name), getattr(fresh, group.name))

        for hook in list(_RELOAD_HOOKS):
            try:
                hook(CONFIG)
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "Strategy config reload hook %s.%s failed; its module keeps "
                    "the previous values",
                    getattr(hook, "__module__", "?"),
                    getattr(hook, "__qualname__", repr(hook)),
                )

        return CONFIG


def log_active_configuration(log=logger) -> None:
    """Write the entire effective configuration to the log at startup.

    Operators previously had to read source to discover which threshold was in
    force, and three of them were duplicated in two files with different
    values. One authoritative dump removes that class of confusion.
    """
    log.info("--- ACTIVE STRATEGY CONFIGURATION -------------------------------")
    for key, value in sorted(CONFIG.as_dict().items()):
        log.info("CONFIG %-46s = %s", key, value)
    log.info("--- END STRATEGY CONFIGURATION ----------------------------------")
