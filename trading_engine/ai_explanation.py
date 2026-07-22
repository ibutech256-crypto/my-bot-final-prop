from __future__ import annotations
from trading_engine.types import Direction, LiquidityEvent, ScoreBreakdown, SessionState, StructureState
class AITradeExplanationEngine:
    def explain(self, direction: Direction, liquidity: LiquidityEvent, score: ScoreBreakdown, structure: StructureState, session: SessionState, rr: str, target: str, risk_level: str) -> str:
        parts=[f"{direction.value} setup qualified after {liquidity.kind.replace('_',' ').lower()} at {liquidity.swept_level}.", f"Structure state is {structure.last_event} with {structure.bias.value} bias.", f"Session filter: {session.name}; {session.reason}", f"Score {score.total}/100 from confluences: " + ", ".join(k for k,v in score.components.items() if v>0) + ".", f"Expected liquidity target: {target}. Expected RR: {rr}. Risk level: {risk_level}."]
        return " ".join(parts)
