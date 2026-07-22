from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class StrategyTrade: module:str; profit:Decimal; risk:Decimal; drawdown:Decimal
@dataclass(frozen=True)
class StrategyHealth: module:str; health_score:Decimal; weight_multiplier:Decimal; alert:bool; metrics:dict
class AdaptiveStrategyHealthEngine:
    def health(self,module:str,trades:list[StrategyTrade],window:int=100)->StrategyHealth:
        sample=[t for t in trades if t.module==module][-window:]
        if not sample: return StrategyHealth(module,Decimal("50"),Decimal("1"),False,{})
        wins=[t for t in sample if t.profit>0]; losses=[t for t in sample if t.profit<0]; gross_win=sum((t.profit for t in wins),Decimal("0")); gross_loss=abs(sum((t.profit for t in losses),Decimal("0")))
        win_rate=Decimal(len(wins)*100)/Decimal(len(sample)); expectancy=sum((t.profit for t in sample),Decimal("0"))/Decimal(len(sample)); pf=gross_win/gross_loss if gross_loss else Decimal("3")
        avg_rr=sum((t.profit/t.risk for t in sample if t.risk),Decimal("0"))/Decimal(max(1,len([t for t in sample if t.risk])))
        dd=max((t.drawdown for t in sample),default=Decimal("0")); score=max(Decimal("0"),min(Decimal("100"),win_rate+pf*Decimal("10")+avg_rr*Decimal("10")-dd))
        multiplier=max(Decimal("0.25"),min(Decimal("1.25"),score/Decimal("75")))
        return StrategyHealth(module,score,multiplier,score<Decimal("55"),{"win_rate":win_rate,"expectancy":expectancy,"profit_factor":pf,"average_rr":avg_rr,"drawdown":dd,"sample":len(sample)})
