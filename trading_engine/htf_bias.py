"""Higher-timeframe bias resolution.

Module 1 (Phase 1) — the highest-priority defect
------------------------------------------------
``RomeoTPTOrchestrator.evaluate_signal`` contained::

    htf_ok = True
    if htf_candles:
        htf_biases = [...]
        htf_ok = all(...)

and ``run_mt5_engine.py`` line 535 called it **without ever passing
``htf_candles``**. The guard was therefore dead code and ``htf_ok`` was
unconditionally ``True`` for every signal the platform has ever produced.

Consequences, all confirmed against the live database on 2026-07-31:

* ``ScoringEngine`` awards ``HTF Alignment`` 15 points on ``if htf``, so every
  signal received the full component. A query over the last six hours returned
  **460 of 460 signals (100%) carrying 'HTF Alignment'** in their confluence
  list, while the real H4+D1 bias agreed with the trade direction on only
  **144 of 366 (39.3%)** live evaluations measured at the same moment.
* Every "70-point Tier 2" signal was really a 55-point signal. The Tier 2
  qualification test ``total >= 70 and htf and fvg_mitigated`` was reduced to
  ``total >= 70 and fvg_mitigated`` — the "HTF aligned" half of the Tier 2
  definition was vacuous.
* Tier 3 (``sweep and kod and htf``) was likewise missing its HTF leg.

This module computes the bias for real. It never returns "aligned" because
data was missing: an unavailable series yields
``HTFStatus.DATA_UNAVAILABLE``, which is *not* alignment, and the caller
records ``HTF_DATA_UNAVAILABLE`` as the rejection reason.

Cost control
------------
The engine scans 121 instruments x 3 timeframes every cycle. Fetching two
extra series per symbol per cycle would add ~242 ``copy_rates_from_pos``
round-trips every few seconds. An H4 bias cannot change more than once every
four hours, so results are cached per symbol with a TTL
(``HTF_CACHE_TTL_SECONDS``, default 300s). Cache hits cost nothing and the
whole HTF layer adds roughly 242 IPC calls per five minutes rather than per
cycle.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from trading_engine.strategy_config import CONFIG
from trading_engine.trend import TrendEngine
from trading_engine.types import Candle, Direction

logger = logging.getLogger("trading")


class HTFStatus(str, Enum):
    """Outcome of the higher-timeframe check. Only ``ALIGNED`` scores."""

    ALIGNED = "ALIGNED"                     # every consulted TF agrees (or is neutral)
    CONFLICT = "CONFLICT"                   # at least one TF opposes the direction
    NEUTRAL_ONLY = "NEUTRAL_ONLY"           # every TF neutral and neutral does not count
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"   # series missing/short: alignment unprovable
    NOT_EVALUATED = "NOT_EVALUATED"         # no direction supplied


@dataclass(frozen=True)
class HTFBiasResult:
    """Result of the higher-timeframe alignment check."""

    status: HTFStatus
    aligned: bool
    biases: dict[str, str] = field(default_factory=dict)
    conflicting: tuple[str, ...] = ()
    detail: str = ""

    @property
    def summary(self) -> str:
        """Compact ``H4=BUY|D1=NEUTRAL`` string for logs and telemetry."""
        if not self.biases:
            return self.status.value
        return "|".join(f"{tf}={bias}" for tf, bias in sorted(self.biases.items()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "aligned": self.aligned,
            "biases": dict(self.biases),
            "conflicting": list(self.conflicting),
            "detail": self.detail,
            "summary": self.summary,
        }


#: Sentinel meaning "alignment could not be proven". Never scores.
UNAVAILABLE = HTFBiasResult(
    status=HTFStatus.DATA_UNAVAILABLE,
    aligned=False,
    detail="higher-timeframe candles unavailable",
)


class HTFBiasEngine:
    """Fetches, caches and evaluates higher-timeframe directional bias.

    Args:
        rate_loader: callable ``(symbol, timeframe_name, bars) -> list[Candle]``
            returning completed candles newest-last, or an empty list when the
            series is unavailable. Injected so the engine is testable without
            MetaTrader5 and so the MT5 timeframe constants stay in the
            adapter layer.
        config: optional override of the process configuration.
    """

    def __init__(
        self,
        rate_loader: Callable[[str, str, int], list[Candle]],
        config=None,
    ) -> None:
        self._load = rate_loader
        self._config = config or CONFIG
        self._trend = TrendEngine()
        self._lock = threading.RLock()
        # symbol -> (expires_at_monotonic, {timeframe: Direction})
        self._cache: dict[str, tuple[float, dict[str, Direction]]] = {}
        self.fetches = 0
        self.cache_hits = 0
        self.failures = 0

    # ------------------------------------------------------------------ #
    # Bias resolution
    # ------------------------------------------------------------------ #

    def _bias_for(self, symbol: str) -> dict[str, Direction]:
        """Directional bias per configured higher timeframe, cached by TTL."""
        cfg = self._config.htf
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(symbol)
            if cached is not None and cached[0] > now:
                self.cache_hits += 1
                return cached[1]

        biases: dict[str, Direction] = {}
        for timeframe in cfg.timeframes:
            try:
                candles = self._load(symbol, timeframe, cfg.bars)
            except Exception as exc:
                logger.warning("HTF fetch failed for %s %s: %s", symbol, timeframe, exc)
                candles = []
            if not candles or len(candles) < cfg.slow_ma:
                self.failures += 1
                continue
            biases[timeframe] = self._trend.bias(candles, fast=cfg.fast_ma, slow=cfg.slow_ma)

        self.fetches += 1
        with self._lock:
            self._cache[symbol] = (now + cfg.cache_ttl_seconds, biases)
        return biases

    def evaluate(self, symbol: str, direction: Direction | None) -> HTFBiasResult:
        """Resolve higher-timeframe alignment for ``symbol`` and ``direction``.

        Returns a result whose ``aligned`` flag is ``True`` **only** when every
        configured higher timeframe was successfully loaded and none of them
        opposes ``direction``. Missing data is never treated as agreement.
        """
        if direction is None or direction == Direction.NEUTRAL:
            return HTFBiasResult(
                status=HTFStatus.NOT_EVALUATED,
                aligned=False,
                detail="no directional bias supplied by the setup",
            )

        cfg = self._config.htf
        biases = self._bias_for(symbol)

        missing = [tf for tf in cfg.timeframes if tf not in biases]
        if missing:
            if cfg.require_confirmation:
                return HTFBiasResult(
                    status=HTFStatus.DATA_UNAVAILABLE,
                    aligned=False,
                    biases={tf: b.value for tf, b in biases.items()},
                    detail=f"no usable history for {', '.join(missing)}",
                )
            logger.debug(
                "HTF_REQUIRE_CONFIRMATION is off; treating missing %s on %s as neutral",
                ", ".join(missing), symbol,
            )

        if not biases:
            return HTFBiasResult(
                status=HTFStatus.DATA_UNAVAILABLE,
                aligned=False,
                detail="no higher timeframe could be evaluated",
            )

        acceptable = {direction}
        if cfg.neutral_counts_as_aligned:
            acceptable.add(Direction.NEUTRAL)

        conflicting = tuple(tf for tf, bias in sorted(biases.items()) if bias not in acceptable)
        bias_map = {tf: bias.value for tf, bias in biases.items()}

        if conflicting:
            return HTFBiasResult(
                status=HTFStatus.CONFLICT,
                aligned=False,
                biases=bias_map,
                conflicting=conflicting,
                detail=(
                    f"{', '.join(f'{tf}={bias_map[tf]}' for tf in conflicting)} "
                    f"opposes a {direction.value} entry"
                ),
            )

        if all(bias == Direction.NEUTRAL for bias in biases.values()):
            if cfg.neutral_counts_as_aligned:
                return HTFBiasResult(
                    status=HTFStatus.ALIGNED,
                    aligned=True,
                    biases=bias_map,
                    detail="all higher timeframes neutral; no opposition to the entry",
                )
            return HTFBiasResult(
                status=HTFStatus.NEUTRAL_ONLY,
                aligned=False,
                biases=bias_map,
                detail="no higher timeframe supports the entry direction",
            )

        return HTFBiasResult(
            status=HTFStatus.ALIGNED,
            aligned=True,
            biases=bias_map,
            detail=(
                f"{', '.join(f'{tf}={b}' for tf, b in sorted(bias_map.items()))} "
                f"supports a {direction.value} entry"
            ),
        )

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #

    def invalidate(self, symbol: str | None = None) -> None:
        with self._lock:
            if symbol is None:
                self._cache.clear()
            else:
                self._cache.pop(symbol, None)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "cached_symbols": len(self._cache),
                "fetches": self.fetches,
                "cache_hits": self.cache_hits,
                "series_failures": self.failures,
            }


def build_mt5_rate_loader(mt5_module, candle_factory=None) -> Callable[[str, str, int], list[Candle]]:
    """Adapter turning the MetaTrader5 module into a ``rate_loader``.

    Kept out of :class:`HTFBiasEngine` so that the engine itself has no
    dependency on MetaTrader5 and can be unit tested with synthetic candles.
    """
    name_to_constant = {
        "M1": "TIMEFRAME_M1",
        "M5": "TIMEFRAME_M5",
        "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30",
        "H1": "TIMEFRAME_H1",
        "H4": "TIMEFRAME_H4",
        "D1": "TIMEFRAME_D1",
        "W1": "TIMEFRAME_W1",
        "MN1": "TIMEFRAME_MN1",
    }

    def _to_candles(rates) -> list[Candle]:
        out: list[Candle] = []
        count = len(rates)
        for index, row in enumerate(rates):
            out.append(
                Candle(
                    time=datetime.fromtimestamp(row["time"], tz=timezone.utc),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["tick_volume"])),
                    # The final bar of any series is still forming; the trend
                    # engine filters on ``completed`` so it must be marked.
                    completed=(index < count - 1),
                )
            )
        return out

    factory = candle_factory or _to_candles

    def loader(symbol: str, timeframe: str, bars: int) -> list[Candle]:
        attribute = name_to_constant.get(timeframe.upper())
        if attribute is None:
            logger.warning("Unknown higher timeframe %r; skipping", timeframe)
            return []
        constant = getattr(mt5_module, attribute, None)
        if constant is None:
            logger.warning("MetaTrader5 has no %s constant; skipping", attribute)
            return []
        rates = mt5_module.copy_rates_from_pos(symbol, constant, 0, bars)
        if rates is None or len(rates) == 0:
            return []
        return factory(rates)

    return loader
