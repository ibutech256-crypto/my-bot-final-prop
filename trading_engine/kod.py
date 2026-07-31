from __future__ import annotations

import logging
import os
from decimal import Decimal

from trading_engine.strategy_config import CONFIG, env_decimal as _env_decimal
from trading_engine.types import Candle, Direction, LiquidityEvent

logger = logging.getLogger("trading")

#: Names of the five independent KOD sub-checks, in evaluation order. The
#: funnel reports a pass rate for each one so the effect of tuning any single
#: threshold is measurable instead of guessed.
KOD_SUBCHECKS: tuple[str, ...] = (
    "sweep_rejection_wick",
    "displacement_direction",
    "displacement_atr",
    "displacement_volume",
    "displacement_body_ratio",
)


class KODEngine:
    """Killzone Opposing Displacement confirmation (v2.4).

    The pattern is a **two-candle sequence**, and v2.4 corrects the fact that
    the previous implementation tried to find it in a single candle:

        candle N   -- the sweep: pierces the liquidity pool and closes back
                      inside it. Wick-dominant by definition.
        candle N+1 -- the displacement: drives away from the pool with
                      conviction. Body-dominant by definition.

    v2.3 evaluated every filter against ``completed[-1]`` and demanded that one
    candle be *both* body-dominant (``body/range >= 0.55``) and wick-dominant
    (``rejection_wick/range >= 0.30``). Because
    ``body + upper_wick + lower_wick == range``, satisfying both forces the
    opposite wick below 0.15 -- and when the sweep landed on the last candle,
    ``completed[-1]`` *was* the wick-dominant sweep candle, so the body test
    could essentially never pass. KOD confirmed on 0.35% of evaluations and
    Tier 1 / Tier 3 never fired once in production.

    v2.4 measures the rejection wick on the sweep candle and the body,
    displacement and velocity on the following candle, so the thresholds are no
    longer mutually exclusive. The threshold *values* are unchanged: this is a
    correctness fix, not a loosening of the quality bar.

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
        min_body_ratio: Decimal | None = None,
        min_rejection_ratio: Decimal | None = None,
        atr_multiplier: Decimal | None = None,
        volume_multiplier: Decimal | None = None,
    ):
        cfg = CONFIG.kod
        self.min_body_ratio = min_body_ratio if min_body_ratio is not None else cfg.min_body_ratio
        self.min_rejection_ratio = (
            min_rejection_ratio if min_rejection_ratio is not None else cfg.min_rejection_ratio
        )
        self.atr_multiplier = atr_multiplier if atr_multiplier is not None else cfg.atr_multiplier
        self.volume_multiplier = (
            volume_multiplier if volume_multiplier is not None else cfg.volume_multiplier
        )

    # ------------------------------------------------------------------ #
    # Telemetry
    # ------------------------------------------------------------------ #

    def subcheck_results(
        self,
        candles: list[Candle],
        liquidity_event: LiquidityEvent | None,
        atr_14: Decimal = Decimal("0"),
    ) -> dict[str, bool] | None:
        """Evaluate all five sub-checks independently, for funnel telemetry.

        ``confirmed_with_reason`` short-circuits on the first failure, which is
        correct for execution but useless for diagnosis: it can only ever tell
        you about the earliest failing check. This method evaluates every check
        so the funnel can report a true pass rate per threshold.

        Returns ``None`` when the pattern cannot be evaluated at all (no sweep,
        insufficient history, or the displacement candle has not formed).
        """
        if liquidity_event is None:
            return None
        completed = [c for c in candles if c.completed]
        if len(completed) < 21:
            return None
        sweep_idx = int(liquidity_event.candle_index)
        if not 0 <= sweep_idx < len(completed) - 1:
            return None

        sweep_candle = completed[sweep_idx]
        displacement = completed[sweep_idx + 1]
        if sweep_candle.range() <= 0 or displacement.range() <= 0:
            return None
        if liquidity_event.direction == Direction.NEUTRAL:
            return None

        wick = (
            sweep_candle.lower_wick()
            if liquidity_event.direction == Direction.BUY
            else sweep_candle.upper_wick()
        )
        window = completed[max(0, sweep_idx + 1 - 20):sweep_idx + 1]
        avg_volume = (
            sum(x.volume for x in window) / Decimal(str(len(window))) if window else Decimal("0")
        )

        return {
            "sweep_rejection_wick": (wick / sweep_candle.range()) >= self.min_rejection_ratio,
            "displacement_direction": displacement.direction() == liquidity_event.direction,
            "displacement_atr": (
                atr_14 <= 0 or displacement.body() >= self.atr_multiplier * atr_14
            ),
            "displacement_volume": (
                avg_volume <= 0 or displacement.volume >= self.volume_multiplier * avg_volume
            ),
            "displacement_body_ratio": (
                displacement.body() / displacement.range()
            ) >= self.min_body_ratio,
        }

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

        # --- Locate the two candles this pattern is actually made of ----------
        # The sweep candle rejects the liquidity pool (long wick, small body).
        # The *displacement* candle is the one that follows it and drives away
        # from the pool (long body, small wicks). Those are opposite shapes, so
        # they must be measured on different candles.
        sweep_idx = int(liquidity_event.candle_index)
        if not 0 <= sweep_idx < len(completed):
            return False, f"sweep index {sweep_idx} outside candle window"

        sweep_candle = completed[sweep_idx]
        if sweep_idx >= len(completed) - 1:
            # detect_sweep looks back three candles, so this resolves by itself
            # on the next cycle once the following candle completes.
            return False, "awaiting displacement candle after sweep"

        c = completed[sweep_idx + 1]
        if c.range() <= 0:
            return False, "zero-range candle"
        if sweep_candle.range() <= 0:
            return False, "zero-range sweep candle"

        # --- Rejection wick: measured on the SWEEP candle ---------------------
        # This is where the rejection physically happens. Requiring it on the
        # displacement candle (the previous behaviour) was self-defeating: a
        # candle cannot simultaneously satisfy body/range >= 0.55 and
        # wick/range >= 0.30 without squeezing the opposite wick under 0.15,
        # and the sweep candle it was often applied to is by definition
        # wick-dominant. That contradiction is why KOD confirmed on 0.35% of
        # evaluations and Tier 1 / Tier 3 never fired even once.
        if liquidity_event.direction == Direction.BUY:
            sweep_wick_ratio = sweep_candle.lower_wick() / sweep_candle.range()
        elif liquidity_event.direction == Direction.SELL:
            sweep_wick_ratio = sweep_candle.upper_wick() / sweep_candle.range()
        else:
            return False, "neutral sweep direction"

        if sweep_wick_ratio < self.min_rejection_ratio:
            return False, (
                f"sweep rejection wick {sweep_wick_ratio:.3f} < {self.min_rejection_ratio}"
            )

        # --- Displacement candle must travel with the trade -------------------
        if c.direction() != liquidity_event.direction:
            return False, (
                f"displacement candle direction opposes "
                f"{liquidity_event.direction.value} sweep"
            )

        # --- Dynamic displacement filter: body >= multiplier x ATR(14) --------
        if atr_14 > 0:
            required_body = self.atr_multiplier * atr_14
            if c.body() < required_body:
                return False, (
                    f"displacement too small: body {c.body()} < "
                    f"{self.atr_multiplier}x ATR ({required_body})"
                )

        # --- Velocity filter: tick volume >= multiplier x MA(20) --------------
        # Averaged over the 20 candles preceding the displacement candle.
        window = completed[max(0, sweep_idx + 1 - 20):sweep_idx + 1]
        if window:
            avg_vol_20 = sum(x.volume for x in window) / Decimal(str(len(window)))
            if avg_vol_20 > 0:
                required_vol = self.volume_multiplier * avg_vol_20
                if c.volume < required_vol:
                    return False, (
                        f"velocity too low: volume {c.volume} < "
                        f"{self.volume_multiplier}x MA20 ({required_vol})"
                    )

        # --- Conviction: displacement candle must be body-dominant ------------
        body_ratio = c.body() / c.range()
        if body_ratio < self.min_body_ratio:
            return False, f"body ratio {body_ratio:.3f} < {self.min_body_ratio}"

        return True, (
            f"KOD confirmed ({liquidity_event.direction.value} displacement; "
            f"sweep wick {sweep_wick_ratio:.2f}, body ratio {body_ratio:.2f})"
        )

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
