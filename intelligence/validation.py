from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import Direction, ScoreBreakdown, TradeSetup
from intelligence.config import ValidationPolicy
from intelligence.mtf_matrix import MatrixContext

@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    adjusted_score: ScoreBreakdown
    reasons: tuple[str,...]

class MultiTimeframeValidationEngine:
    def validate(self, setup:TradeSetup, matrix:MatrixContext, policy:ValidationPolicy=ValidationPolicy())->ValidationResult:
        reasons=[]; penalty=Decimal("0")
        if matrix.weekly_bias not in {Direction.NEUTRAL, setup.direction}: reasons.append("Weekly bias conflicts with execution direction"); penalty += policy.htf_bias_penalty
        if matrix.daily_bias not in {Direction.NEUTRAL, setup.direction}: reasons.append("Daily bias conflicts with execution direction"); penalty += policy.htf_bias_penalty
        for ob in matrix.macro_order_blocks:
            inside=ob.low <= setup.entry <= ob.high
            if inside and ob.direction != setup.direction:
                reasons.append(f"Entry is inside opposing {ob.kind} on macro timeframe"); penalty += policy.daily_order_block_penalty
        if policy.conflict_mode == "HARD_BLOCK" and reasons:
            return ValidationResult(False, ScoreBreakdown(Decimal("0"), setup.score.components|{"MTF Penalty":-penalty}, False), tuple(reasons))
        adjusted=max(Decimal("0"), setup.score.total-penalty)
        components=dict(setup.score.components); components["MTF Penalty"]=-penalty
        return ValidationResult(adjusted>=policy.minimum_post_penalty_score, ScoreBreakdown(adjusted,components,adjusted>=policy.minimum_post_penalty_score), tuple(reasons) or ("Multi-timeframe validation passed",))
