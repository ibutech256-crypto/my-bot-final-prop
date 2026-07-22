from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import Direction, ScoreBreakdown, TradeSetup
from intelligence.config import CorrelationRule
@dataclass(frozen=True)
class ReferenceState:
    symbol: str; bias: Direction; strength: Decimal
@dataclass(frozen=True)
class CorrelationDecision:
    allowed: bool; adjusted_score: ScoreBreakdown; reasons: tuple[str,...]
class CorrelationShieldService:
    def __init__(self, rules:tuple[CorrelationRule,...]=()): self.rules=rules
    def evaluate(self, setup:TradeSetup, references:dict[str,ReferenceState])->CorrelationDecision:
        score=setup.score.total; components=dict(setup.score.components); reasons=[]; allowed=True
        for rule in self.rules:
            if not rule.enabled or rule.mode=="DISABLED": continue
            if not any(asset.upper() in setup.symbol.upper() for asset in rule.affected_assets): continue
            ref=references.get(rule.reference_symbol)
            if not ref: continue
            conflict=(setup.direction==Direction.BUY and setup.symbol.upper().startswith(tuple(rule.bearish_blocks)) and ref.bias==Direction.BUY) or (setup.direction==Direction.BUY and any(x in setup.symbol.upper() for x in rule.bullish_blocks) and ref.bias==Direction.SELL)
            if conflict:
                reasons.append(f"{rule.reference_symbol} {ref.bias.value} conflicts with {setup.symbol} {setup.direction.value}")
                if rule.mode=="HARD_BLOCK": allowed=False; score=Decimal("0")
                else: score=max(Decimal("0"), score-rule.penalty*ref.strength); components[f"Correlation {rule.reference_symbol}"]=-(rule.penalty*ref.strength)
        return CorrelationDecision(allowed and score>0, ScoreBreakdown(score,components,score>0), tuple(reasons) or ("Correlation shield passed",))
