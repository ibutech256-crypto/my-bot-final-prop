from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class ExecutionObservation:
    latency_ms:int; slippage_points:Decimal; broker_delay_ms:int; spread_points:Decimal; success:bool; partial_fill:bool; rejected:bool; modification_ms:int; close_ms:int
class ExecutionQualityEngine:
    def score(self, observations:list[ExecutionObservation])->dict:
        if not observations: return {"execution_score":Decimal("50"),"sample":0}
        n=Decimal(len(observations)); avg_latency=sum(Decimal(o.latency_ms) for o in observations)/n; avg_slip=sum(o.slippage_points for o in observations)/n; reject_rate=Decimal(sum(1 for o in observations if o.rejected)*100)/n; success_rate=Decimal(sum(1 for o in observations if o.success)*100)/n
        score=max(Decimal("0"),min(Decimal("100"),success_rate - reject_rate - avg_slip*Decimal("2") - avg_latency/Decimal("100")))
        return {"execution_score":score,"average_latency_ms":avg_latency,"average_slippage_points":avg_slip,"rejection_rate":reject_rate,"success_rate":success_rate,"sample":len(observations)}
