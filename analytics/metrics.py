from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class TradeMetric: profit:Decimal; risk:Decimal; hold_minutes:Decimal
class PerformanceCalculator:
    def summarize(self,trades:list[TradeMetric])->dict[str,Decimal]:
        if not trades: return {"win_rate":Decimal(0),"loss_rate":Decimal(0),"profit_factor":Decimal(0),"expectancy":Decimal(0),"average_rr":Decimal(0),"average_hold_minutes":Decimal(0)}
        wins=[t for t in trades if t.profit>0]; losses=[t for t in trades if t.profit<0]; gross_win=sum((t.profit for t in wins),Decimal(0)); gross_loss=abs(sum((t.profit for t in losses),Decimal(0))); rr=[t.profit/t.risk for t in trades if t.risk]
        return {"win_rate":Decimal(len(wins)*100)/Decimal(len(trades)),"loss_rate":Decimal(len(losses)*100)/Decimal(len(trades)),"profit_factor":gross_win/gross_loss if gross_loss else Decimal(0),"expectancy":sum((t.profit for t in trades),Decimal(0))/Decimal(len(trades)),"average_rr":sum(rr,Decimal(0))/Decimal(len(rr)) if rr else Decimal(0),"average_hold_minutes":sum((t.hold_minutes for t in trades),Decimal(0))/Decimal(len(trades))}
