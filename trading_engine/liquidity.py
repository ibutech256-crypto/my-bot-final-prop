"""Buy-side / sell-side liquidity sweep detection (stop hunts, turtle soup).

v2.4 — corrected ``failed`` semantics
-------------------------------------
A *sweep* is a candle that trades through a known liquidity pool — the CRT
range extreme, or a cluster of equal highs/lows — and then **closes back on the
original side** of that pool. The wick takes the resting stops; the close shows
the excursion was rejected. That is the setup the strategy wants to trade.

``LiquidityEvent.failed`` now means *the sweep was invalidated*: price
subsequently **accepted** beyond the swept pool, proving it was a genuine
breakout rather than a stop hunt. It is therefore decided by what happens on
the candles **after** the sweep, not by how deeply the sweep candle closed back
into the range.

Why this changed
~~~~~~~~~~~~~~~~
The previous revision computed the flag as::

    failed = c.close <= crt.internal_high   # buy-side sweep
    failed = c.close >= crt.internal_low    # sell-side sweep

``CRTEngine`` builds ``internal_high`` as ``midpoint + 25% of width`` and
``internal_low`` as ``midpoint - 25% of width`` — i.e. the 75th and 25th
percentiles of the range. So those expressions marked a sweep as *failed*
precisely when price rejected **deeply** back into the range, which is the
textbook high-quality turtle-soup reversal. Only shallow rejections that
closed in the outer quartile survived — and those are the ones most likely to
simply continue breaking out.

``ScoringEngine`` awards its 15-point ``Liquidity`` component only when
``not liquidity.failed``, and ``orchestrator`` discards the setup outright on
``sweep.failed``. The inverted flag therefore stripped 15 points from exactly
the best setups and vetoed them. Live sampling across 60 symbol/timeframe
pairs found 32 of 43 detected sweeps (74.4%) incorrectly flagged as failed,
which is the dominant reason scores stalled in the 55-70 band and the live
audit log is full of ``score 67 ... no valid liquidity sweep``.
"""

from __future__ import annotations

from decimal import Decimal

from trading_engine.types import CRTRange, Candle, Direction, LiquidityEvent

# How many of the most recent completed candles may host the sweep.
SWEEP_LOOKBACK_OFFSETS = (-1, -2, -3)


class LiquiditySweepEngine:
    """Detects liquidity sweeps against the CRT range and equal high/low pools."""

    def __init__(self, equal_tolerance_ticks: int = 3) -> None:
        self.equal_tolerance_ticks = equal_tolerance_ticks

    # ------------------------------------------------------------------ #
    # Equal-high / equal-low pools
    # ------------------------------------------------------------------ #

    def equal_highs(self, candles: list[Candle], tick_size: Decimal) -> tuple[Decimal, ...]:
        tol = tick_size * self.equal_tolerance_ticks
        levels: list[Decimal] = []
        highs = [c.high for c in candles if c.completed]
        for i, h in enumerate(highs):
            if sum(1 for x in highs[max(0, i - 10):i + 11] if abs(x - h) <= tol) >= 2:
                levels.append(h)
        return tuple(sorted(set(levels)))

    def equal_lows(self, candles: list[Candle], tick_size: Decimal) -> tuple[Decimal, ...]:
        tol = tick_size * self.equal_tolerance_ticks
        levels: list[Decimal] = []
        lows = [c.low for c in candles if c.completed]
        for i, l in enumerate(lows):
            if sum(1 for x in lows[max(0, i - 10):i + 11] if abs(x - l) <= tol) >= 2:
                levels.append(l)
        return tuple(sorted(set(levels)))

    # ------------------------------------------------------------------ #
    # Swept-level resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _swept_high(
        c: Candle, crt: CRTRange, eq_h: tuple[Decimal, ...], tol: Decimal
    ) -> Decimal | None:
        """Highest buy-side pool this candle pierced *and* closed back below.

        Both conditions are enforced per level. The previous implementation
        selected the level with ``crt.high if c.high > crt.high + tol else ...``,
        which could report ``crt.high`` as the swept level even when the candle
        closed *above* it (i.e. no rejection at all) as long as some equal-high
        matched — an internally inconsistent event.
        """
        levels: list[Decimal] = []
        if c.high > crt.high + tol and c.close < crt.high:
            levels.append(crt.high)
        levels.extend(h for h in eq_h if c.high > h + tol and c.close < h)
        return max(levels) if levels else None

    @staticmethod
    def _swept_low(
        c: Candle, crt: CRTRange, eq_l: tuple[Decimal, ...], tol: Decimal
    ) -> Decimal | None:
        """Lowest sell-side pool this candle pierced *and* closed back above."""
        levels: list[Decimal] = []
        if c.low < crt.low - tol and c.close > crt.low:
            levels.append(crt.low)
        levels.extend(l for l in eq_l if c.low < l - tol and c.close > l)
        return min(levels) if levels else None

    @staticmethod
    def _rejection_ratio(c: Candle, direction: Direction) -> Decimal:
        """Strength of the rejection on the sweep candle, in ``[0, 1]``.

        For a bearish (buy-side) sweep this is the share of the candle range
        left above the close — a long upper wick with a close near the low
        approaches 1.0. Reported for telemetry and ranking; it deliberately
        does **not** gate the event, because thresholding it is what produced
        the original inverted-filter bug.
        """
        span = c.high - c.low
        if span <= 0:
            return Decimal("0")
        num = (c.high - c.close) if direction == Direction.SELL else (c.close - c.low)
        return max(Decimal("0"), min(Decimal("1"), num / span))

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #

    def detect_sweep(
        self, candles: list[Candle], crt: CRTRange, tick_size: Decimal
    ) -> LiquidityEvent | None:
        """Return the most recent valid liquidity sweep, or ``None``.

        Scans the last three completed candles. A sweep is *failed* only if a
        later completed candle closed beyond the swept level, which means the
        market accepted the breakout instead of reversing.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 2:
            return None

        tol = tick_size * self.equal_tolerance_ticks
        eq_h = self.equal_highs(completed[:-1], tick_size)
        eq_l = self.equal_lows(completed[:-1], tick_size)

        for idx_offset in SWEEP_LOOKBACK_OFFSETS:
            if abs(idx_offset) > len(completed):
                continue
            c = completed[idx_offset]
            idx = len(completed) + idx_offset
            subsequent = completed[idx + 1:]

            # --- Buy-side / equal-high sweep -> bearish reversal ----------
            swept_high = self._swept_high(c, crt, eq_h, tol)
            if swept_high is not None:
                # Invalidated only if price later *closed* back above the pool.
                failed = any(x.close > swept_high for x in subsequent)
                ratio = self._rejection_ratio(c, Direction.SELL)
                verdict = (
                    f"invalidated: a later candle closed above {swept_high}"
                    if failed
                    else f"rejection holding (strength {float(ratio):.0%})"
                )
                return LiquidityEvent(
                    Direction.SELL,
                    swept_high,
                    "BUY_SIDE_LIQUIDITY_SWEEP",
                    idx,
                    failed,
                    f"Buy-side/Equal-high liquidity ({swept_high}) swept and "
                    f"closed back inside range; {verdict}.",
                    ratio,
                )

            # --- Sell-side / equal-low sweep -> bullish reversal ----------
            swept_low = self._swept_low(c, crt, eq_l, tol)
            if swept_low is not None:
                failed = any(x.close < swept_low for x in subsequent)
                ratio = self._rejection_ratio(c, Direction.BUY)
                verdict = (
                    f"invalidated: a later candle closed below {swept_low}"
                    if failed
                    else f"rejection holding (strength {float(ratio):.0%})"
                )
                return LiquidityEvent(
                    Direction.BUY,
                    swept_low,
                    "SELL_SIDE_LIQUIDITY_SWEEP",
                    idx,
                    failed,
                    f"Sell-side/Equal-low liquidity ({swept_low}) swept and "
                    f"closed back inside range; {verdict}.",
                    ratio,
                )

        return None
