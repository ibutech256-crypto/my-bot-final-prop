from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Direction, LiquidityEvent, NewsState, ScoreBreakdown, SessionState, StructureState, Zone
class ScoringEngine:
    weights={"CRT":Decimal("12"),"Liquidity":Decimal("15"),"KOD":Decimal("12"),"CISD":Decimal("12"),"HTF Alignment":Decimal("15"),"Session":Decimal("8"),"Structure":Decimal("10"),"Risk":Decimal("8"),"Volatility":Decimal("4"),"News":Decimal("4")}
    def score(self, direction:Direction, liquidity:LiquidityEvent|None, kod:bool, cisd:bool, htf:bool, session:SessionState, structure:StructureState, risk_ok:bool, volatility_ok:bool, news:NewsState, minimum:Decimal=Decimal("75")) -> ScoreBreakdown:
        c={"CRT":self.weights["CRT"],"Liquidity":self.weights["Liquidity"] if liquidity and not liquidity.failed else Decimal("0"),"KOD":self.weights["KOD"] if kod else Decimal("0"),"CISD":self.weights["CISD"] if cisd else Decimal("0"),"HTF Alignment":self.weights["HTF Alignment"] if htf else Decimal("0"),"Session":self.weights["Session"] if session.liquid else Decimal("0"),"Structure":self.weights["Structure"] if structure.bias in {direction,Direction.NEUTRAL} else Decimal("0"),"Risk":self.weights["Risk"] if risk_ok else Decimal("0"),"Volatility":self.weights["Volatility"] if volatility_ok else Decimal("0"),"News":self.weights["News"] if news.trading_allowed else Decimal("0")}
        total=sum(c.values(),Decimal("0"))
        
        # Tiered Execution Threshold Gate (v1.9.0)
        passed = total >= minimum
        if not passed:
            if total >= Decimal("70") and htf: # Tier 2 (Confluence Execution)
                passed = True
            elif total >= Decimal("55") and (liquidity and not liquidity.failed) and kod: # Tier 1 (Aggressive KOD Sweep)
                passed = True
                
        return ScoreBreakdown(total,c,passed)
