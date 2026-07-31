"""Scoring engine with tiered dynamic execution gating.

v2.3 — Module 2
---------------
The previous revision gated *all three* execution tiers behind ``kod``:

    if total >= 55 and liquidity and not liquidity.failed and kod: passed = True
    if total >= 70 and htf and kod:                                passed = True
    if total >= minimum and kod:                                   passed = True

Live telemetry showed KOD confirming on only 7 of 4000 evaluations (0.35%), so
``passed`` was effectively always False and the engine executed nothing for
days — every signal landed in WATCHLIST at score 59-62.

The specification defines the two tiers as:

    Tier 1 (>= 55): BSL/SSL liquidity sweep + KOD displacement confirmed
    Tier 2 (>= 70): HTF alignment + FVG / CE mitigation confirmed

Note that Tier 2 does **not** require KOD. That is the corrected behaviour
implemented here: Tier 2 is now an independent path to execution driven by
higher-timeframe alignment and fair-value-gap mitigation.

The ``if not kod: total = min(total, 70)`` cap is retained deliberately — a
non-KOD setup can still reach the Tier 2 threshold, but never outranks a
KOD-confirmed one.
"""

from __future__ import annotations

from decimal import Decimal

from trading_engine.types import (
    Direction,
    LiquidityEvent,
    NewsState,
    ScoreBreakdown,
    SessionState,
    StructureState,
)

# Execution tier thresholds.
TIER_1_THRESHOLD = Decimal("55")
TIER_2_THRESHOLD = Decimal("70")

# Ceiling applied when the KOD displacement candle is absent.
NON_KOD_SCORE_CAP = Decimal("70")


class ScoringEngine:
    weights = {
        "CRT": Decimal("12"),
        "Liquidity": Decimal("15"),
        "KOD": Decimal("18"),
        "CISD": Decimal("12"),
        "HTF Alignment": Decimal("15"),
        "Session": Decimal("8"),
        "Structure": Decimal("10"),
        "Risk": Decimal("5"),
        "Volatility": Decimal("3"),
        "News": Decimal("2"),
    }

    def score(
        self,
        direction,
        liquidity,
        kod,
        cisd,
        htf,
        session,
        structure,
        risk_ok,
        volatility_ok,
        news,
        minimum=Decimal("75"),
        fvg_mitigated: bool = False,
    ) -> ScoreBreakdown:
        """Compute the weighted score and resolve the execution tier.

        Args:
            fvg_mitigated: True when price has traded into the 50% consequent
                encroachment of a valid fair value gap aligned with ``direction``.
                Required for Tier 2 execution.
            minimum: Retained for backward compatibility. It no longer acts as a
                hard execution gate; it only widens Tier 2 if a caller passes a
                threshold below 70.
        """
        c = {
            "CRT": self.weights["CRT"],
            "Liquidity": self.weights["Liquidity"] if liquidity and not liquidity.failed else Decimal("0"),
            "KOD": self.weights["KOD"] if kod else Decimal("0"),
            "CISD": self.weights["CISD"] if cisd else Decimal("0"),
            "HTF Alignment": self.weights["HTF Alignment"] if htf else Decimal("0"),
            "Session": self.weights["Session"] if session.liquid else Decimal("0"),
            "Structure": self.weights["Structure"] if structure.bias in {direction, Direction.NEUTRAL} else Decimal("0"),
            "Risk": self.weights["Risk"] if risk_ok else Decimal("0"),
            "Volatility": self.weights["Volatility"] if volatility_ok else Decimal("0"),
            "News": self.weights["News"] if news.trading_allowed else Decimal("0"),
        }

        total = sum(c.values(), Decimal("0"))
        if not kod:
            total = min(total, NON_KOD_SCORE_CAP)

        sweep_ok = bool(liquidity) and not liquidity.failed

        # --- Tier 1: liquidity sweep + KOD displacement -----------------------
        if total >= TIER_1_THRESHOLD and sweep_ok and kod:
            return ScoreBreakdown(
                total, c, True, "TIER_1",
                f"TIER_1: score {total} >= {TIER_1_THRESHOLD}, sweep + KOD confirmed",
            )

        # --- Tier 2: HTF alignment + FVG/CE mitigation (KOD not required) -----
        # Fixed at 70 by specification. ``minimum`` is intentionally ignored
        # here: existing callers pass 50, which would otherwise silently drop
        # the Tier 2 bar well below the intended threshold.
        tier_2_threshold = TIER_2_THRESHOLD
        if total >= tier_2_threshold and htf and fvg_mitigated:
            return ScoreBreakdown(
                total, c, True, "TIER_2",
                f"TIER_2: score {total} >= {tier_2_threshold}, HTF aligned + FVG/CE mitigated",
            )

        # --- Not eligible: report the closest miss so the audit log is useful --
        if total < TIER_1_THRESHOLD:
            reason = f"score {total} below Tier 1 minimum {TIER_1_THRESHOLD}"
        elif not sweep_ok:
            reason = f"score {total} but no valid liquidity sweep"
        elif not kod and total < tier_2_threshold:
            reason = (
                f"score {total} capped at {NON_KOD_SCORE_CAP} (KOD absent) and "
                f"below Tier 2 threshold {tier_2_threshold}"
            )
        elif not kod and not htf:
            reason = f"score {total} qualifies for Tier 2 but HTF not aligned"
        elif not kod and not fvg_mitigated:
            reason = f"score {total} qualifies for Tier 2 but FVG/CE not mitigated"
        else:
            reason = f"score {total} did not satisfy any execution tier"

        return ScoreBreakdown(total, c, False, "", reason)
