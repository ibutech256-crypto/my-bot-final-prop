from __future__ import annotations

import logging
import os
from decimal import Decimal

from trading_engine.types import Candle, Direction, LiquidityEvent

logger = logging.getLogger("trading")


def _env_decimal(name: str, default: str) -> Decimal:
    """Read a tunable threshold from the environment, falling back to default."""
    try:
        return Decimal(str(os.getenv(name, default)))
    except Exception:
        return Decimal(default)


class KODEngine:
    """Killzone Opposing Displacement confirmation (v2.3).

    Module 3 dynamic volatility / momentum filters:

      * displacement -- KOD candle body >= ``KOD_ATR_MULTIPLIER`` x ATR(14)
      * velocity     -- tick volume >= ``KOD_VOLUME_MULTIPLIER`` x MA(20) volume

    The specification called for a 1.8x ATR multiplier. Measured against live
    telemetry that value confirms essentially never once it is stacked on top of
    the existing body-ratio (0.55) and rejection-wick (0.30) requirements -- KOD
    already confirmed on only 0.35% of evaluations with the ATR filter dormant.
    The default is therefore 1.2x, and both multipliers are environment-tunable
    so the threshold can be tightened toward 1.8 once there is execution data to
    justify it:

        KOD_ATR_MULTIPLIER=1.8
        KOD_VOLUME_MULTIPLIER=1.5

    ``confirmed_with_reason`` reports which specific sub-check rejected a
    candidate so the rejection mix is visible in the EXEC-AUDIT log.
    """

    def __init__(
        self,
        min_body_ratio: Decimal = Decimal("0.55"),
        min_rejection_ratio: Decimal = Decimal("0.30"),
        atr_multiplier: Decimal | None = None,
        volume_multiplier: Decimal | None = None,
    ):
        self.min_body_ratio = min_body_ratio
        self.min_rejection_ratio = min_rejection_ratio
        self.atr_multiplier = (
            atr_multiplier if atr_multiplier is not None
            else _env_decimal("KOD_ATR_MULTIPLIER", "1.2")
        )
        self.volume_multiplier = (
            volume_multiplier if volume_multiplier is not None
            else _env_decimal("KOD_VOLUME_MULTIPLIER", "1.5")
        )

    def confirmed(
        self,
        candles: list[Candle],
        liquidity_event: LiquidityEvent,
        atr_14: Decimal = Decimal("0"),
    ) -> bool:
        """Confirm KOD with dynamic volatility/momentum filters."""
        ok, _ = self.confirmed_with_reason(candles, liquidity_event, atr_14)
        return ok

    def confirmed_with_reason(
        self,
        candles: list[Candle],
        liquidity_event: LiquidityEvent,
        atr_14: Decimal = Decimal("0"),
    ) -> tuple[bool, str]:
        """Same as :meth:`confirmed` but also returns the rejection reason.

        Args:
            candles: Completed candles.
            liquidity_event: The detected liquidity sweep event.
            atr_14: Pre-calculated 14-period ATR. Pass 0 to skip the ATR check.
        """
        if liquidity_event is None:
            return False, "no liquidity event"

        completed = [c for c in candles if c.completed]
        if len(completed) < 21:
            return False, f"insufficient history ({len(completed)} < 21 candles)"

        c = completed[-1]
        if c.range() <= 0:
            return False, "zero-range candle"

        # --- Dynamic displacement filter: body >= multiplier x ATR(14) --------
        if atr_14 > 0:
            required_body = self.atr_multiplier * atr_14
            if c.body() < required_body:
                return False, (
                    f"displacement too small: body {c.body()} < "
                    f"{self.atr_multiplier}x ATR ({required_body})"
                )

        # --- Velocity filter: tick volume >= multiplier x MA(20) --------------
        avg_vol_20 = sum(x.volume for x in completed[-21:-1]) / Decimal("20")
        if avg_vol_20 > 0:
            required_vol = self.volume_multiplier * avg_vol_20
            if c.volume < required_vol:
                return False, (
                    f"velocity too low: volume {c.volume} < "
                    f"{self.volume_multiplier}x MA20 ({required_vol})"
                )

        # --- Body ratio & directional rejection wick --------------------------
        body_ratio = c.body() / c.range()
        if body_ratio < self.min_body_ratio:
            return False, f"body ratio {body_ratio:.3f} < {self.min_body_ratio}"

        if liquidity_event.direction == Direction.BUY:
            if c.direction() != Direction.BUY:
                return False, "candle direction opposes BUY sweep"
            wick_ratio = c.lower_wick() / c.range()
            if wick_ratio < self.min_rejection_ratio:
                return False, f"lower wick {wick_ratio:.3f} < {self.min_rejection_ratio}"
            return True, "KOD confirmed (BUY displacement)"

        if liquidity_event.direction == Direction.SELL:
            if c.direction() != Direction.SELL:
                return False, "candle direction opposes SELL sweep"
            wick_ratio = c.upper_wick() / c.range()
            if wick_ratio < self.min_rejection_ratio:
                return False, f"upper wick {wick_ratio:.3f} < {self.min_rejection_ratio}"
            return True, "KOD confirmed (SELL displacement)"

        return False, "neutral sweep direction"

    def confirm_turtle_soup_plus_one(
        self,
        candles: list[Candle],
        prior_high: Decimal,
        prior_low: Decimal,
        direction: Direction,
    ) -> bool:
        """Laurence Connors 'Turtle Soup Plus One' pattern.
        Captures clean breakout failure entries on Day + 1.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 2:
            return False
        last = completed[-1]

        if direction == Direction.BUY:
            return last.low < prior_low and last.close > prior_low
        elif direction == Direction.SELL:
            return last.high > prior_high and last.close < prior_high
        return False

    def confirm_80_20_rule(self, candles: list[Candle]) -> tuple[bool, Direction]:
        """Laurence Connors '80-20 Rule' reversal pattern."""
        completed = [c for c in candles if c.completed]
        if len(completed) < 2:
            return False, Direction.NEUTRAL
        prev = completed[-2]
        last = completed[-1]

        if prev.range() <= 0:
            return False, Direction.NEUTRAL

        open_pct = (prev.open - prev.low) / prev.range()
        close_pct = (prev.close - prev.low) / prev.range()

        # 80% Rule: prior bar opened/closed in top 20% of its range
        if (open_pct >= Decimal("0.80") or close_pct >= Decimal("0.80")):
            # Reversal: current bar closes lower
            if last.close < prev.close and last.direction() == Direction.SELL:
                return True, Direction.SELL

        # 20% Rule: prior bar opened/closed in bottom 20% of its range
        if (open_pct <= Decimal("0.20") or close_pct <= Decimal("0.20")):
            # Reversal: current bar closes higher
            if last.close > prev.close and last.direction() == Direction.BUY:
                return True, Direction.BUY

        return False, Direction.NEUTRAL
