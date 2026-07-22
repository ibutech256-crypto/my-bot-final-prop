from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
@dataclass(frozen=True)
class ClosedTradeMetric:
    symbol: str; session: str; opened_at: datetime; closed_at: datetime; profit: Decimal; risk: Decimal
class AnalyticsEngine:
    def calculate(self, trades:list[ClosedTradeMetric]) -> dict:
        if not trades: return {"win_rate":0,"loss_rate":0,"profit_factor":0,"average_rr":0,"expectancy":0,"average_trade_duration":0,"drawdown":0,"equity_curve":[]}
        wins=[t for t in trades if t.profit>0]; losses=[t for t in trades if t.profit<0]
        gross_win=sum((t.profit for t in wins),Decimal(0)); gross_loss=abs(sum((t.profit for t in losses),Decimal(0)))
        rr=[t.profit/t.risk for t in trades if t.risk]; equity=[]; bal=Decimal(0); peak=Decimal(0); dd=Decimal(0)
        for t in trades:
            bal+=t.profit; peak=max(peak,bal); dd=max(dd,peak-bal); equity.append({"time":t.closed_at.isoformat(),"equity":str(bal)})
        duration=sum(((t.closed_at-t.opened_at).total_seconds()/60 for t in trades),0)/len(trades)
        return {"win_rate":float(Decimal(len(wins)*100)/Decimal(len(trades))),"loss_rate":float(Decimal(len(losses)*100)/Decimal(len(trades))),"profit_factor":float(gross_win/gross_loss) if gross_loss else 0,"average_rr":float(sum(rr,Decimal(0))/Decimal(len(rr))) if rr else 0,"expectancy":float(sum((t.profit for t in trades),Decimal(0))/Decimal(len(trades))),"average_trade_duration":duration,"drawdown":float(dd),"equity_curve":equity,"session_performance":self._group(trades,"session"),"pair_performance":self._group(trades,"symbol")}
    def _group(self,trades:list[ClosedTradeMetric],attr:str)->dict[str,float]:
        out={}
        for t in trades: out[getattr(t,attr)]=out.get(getattr(t,attr),0.0)+float(t.profit)
        return out
