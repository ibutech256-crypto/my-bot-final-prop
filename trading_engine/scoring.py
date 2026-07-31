"""Scoring engine with tiered dynamic execution gating.

v2.4 — Module 2 / Module 6
--------------------------
Three execution tiers are defined by the specification, and all three are
executable:

    Tier 1 (>= 55): BSL/SSL liquidity sweep + KOD displacement confirmed
    Tier 2 (>= 70): HTF alignment + FVG / consequent-encroachment mitigation
    Tier 3 (>= 85): full confluence — sweep + KOD + HTF alignment

Tier 2 deliberately does **not** require KOD; it is an independent path to
execution driven by higher-timeframe alignment and fair-value-gap mitigation.
Live telemetry had shown KOD confirming on only 7 of 4000 evaluations (0.35%),
so gating every tier behind KOD (the pre-v2.3 behaviour) meant ``passed`` was
effectively always False and the engine executed nothing for days.

Tier selection picks the **highest** tier the setup qualifies for
-----------------------------------------------------------------
Earlier revisions returned on the first matching tier, testing Tier 1 before
Tier 2. A score of 75 with sweep + KOD + HTF + FVG therefore returned
``TIER_1`` — the *lowest* tier and, with position sizing now keyed to tier, the
smallest size — even though it also satisfied Tier 2. Qualification is now
evaluated for all tiers and the best one wins.

Risk multipliers
----------------
Position size scales with conviction: Tier 1 risks half the base unit, Tier 2
the full unit, Tier 3 one and a half. ``ScoreBreakdown.risk_multiplier``
carries the factor to the execution layer.

The ``if not kod: total = min(total, 70)`` cap is retained deliberately — a
non-KOD setup can still reach the Tier 2 threshold, but never outranks a
KOD-confirmed one, and can never reach Tier 3.
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
TIER_3_THRESHOLD = Decimal("85")

# Ceiling applied when the KOD displacement candle is absent. Note this sits
# below TIER_3_THRESHOLD, so Tier 3 structurally requires KOD.
NON_KOD_SCORE_CAP = Decimal("70")

# Position-size multiplier applied to the base risk unit, keyed by tier.
TIER_RISK_MULTIPLIERS: dict[str, Decimal] = {
    "TIER_1": Decimal("0.5"),
    "TIER_2": Decimal("1.0"),
    "TIER_3": Decimal("1.5"),
}

# Ranking used to resolve the best tier when a setup qualifies for several.
_TIER_RANK: dict[str, int] = {"TIER_1": 1, "TIER_2": 2, "TIER_3": 3}


def tier_risk_multiplier(tier: str | None) -> Decimal:
    """Risk multiplier for ``tier``; ``1.0`` for unknown/absent tiers."""
    return TIER_RISK_MULTIPLIERS.get(tier or "", Decimal("1.0"))


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
            minimum: **Deprecated and ignored.** Retained only so existing
                callers (which pass 50) keep working. It has not acted as an
                execution gate since v2.3; tier thresholds are the sole gate.
                No hidden ">= 75" cutoff exists anywhere in this module.
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

        # --- Qualification: evaluate every tier, then take the highest -------
        qualified: list[tuple[str, str]] = []

        if total >= TIER_1_THRESHOLD and sweep_ok and kod:
            qualified.append((
                "TIER_1",
                f"score {total} >= {TIER_1_THRESHOLD}, sweep + KOD confirmed",
            ))

        if total >= TIER_2_THRESHOLD and htf and fvg_mitigated:
            qualified.append((
                "TIER_2",
                f"score {total} >= {TIER_2_THRESHOLD}, HTF aligned + FVG/CE mitigated",
            ))

        if total >= TIER_3_THRESHOLD and sweep_ok and kod and htf:
            qualified.append((
                "TIER_3",
                f"score {total} >= {TIER_3_THRESHOLD}, full confluence "
                f"(sweep + KOD + HTF alignment)",
            ))

        if qualified:
            tier, detail = max(qualified, key=lambda item: _TIER_RANK[item[0]])
            mult = tier_risk_multiplier(tier)
            return ScoreBreakdown(
                total,
                c,
                True,
                tier,
                f"{tier}: {detail} [risk x{mult}]",
                mult,
            )

        # --- Not eligible: report the closest miss so the audit log is useful --
        if total < TIER_1_THRESHOLD:
            reason = f"score {total} below Tier 1 minimum {TIER_1_THRESHOLD}"
        elif not sweep_ok:
            reason = f"score {total} but no valid liquidity sweep"
        elif not kod and total < TIER_2_THRESHOLD:
            reason = (
                f"score {total} capped at {NON_KOD_SCORE_CAP} (KOD absent) and "
                f"below Tier 2 threshold {TIER_2_THRESHOLD}"
            )
        elif not kod and not htf:
            reason = f"score {total} qualifies for Tier 2 but HTF not aligned"
        elif not kod and not fvg_mitigated:
            reason = f"score {total} qualifies for Tier 2 but FVG/CE not mitigated"
        else:
            reason = f"score {total} did not satisfy any execution tier"

        return ScoreBreakdown(total, c, False, "", reason, Decimal("0"))
