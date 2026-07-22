from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class CompletedTradeReviewInput:
    symbol:str; direction:str; trigger_reason:str; confluences:tuple[str,...]; regime:str; liquidity_target:str; entry_score:Decimal; exit_rr:Decimal; execution_score:Decimal; risk_score:Decimal; profit:Decimal
class AITradeReviewEngine:
    def review(self, data:CompletedTradeReviewInput)->dict:
        entry_quality="EXCELLENT" if data.entry_score>=85 else "GOOD" if data.entry_score>=70 else "WEAK"
        exit_quality="EXCELLENT" if data.exit_rr>=2 else "GOOD" if data.exit_rr>=1 else "POOR"
        risk_quality="CONTROLLED" if data.risk_score>=75 else "NEEDS_REVIEW"
        lesson = "Replicate this confluence profile." if data.profit>0 and entry_quality in {"EXCELLENT","GOOD"} else "Review entry timing, execution friction and HTF context before repeating."
        return {"summary":f"{data.symbol} {data.direction} triggered because {data.trigger_reason}.","confluences":list(data.confluences),"market_regime":data.regime,"liquidity_target":data.liquidity_target,"entry_quality":entry_quality,"exit_quality":exit_quality,"execution_quality":"GOOD" if data.execution_score>=75 else "POOR","risk_quality":risk_quality,"lessons_learned":lesson,"permanent":True}
