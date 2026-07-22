from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from intelligence.symbol_intelligence import SymbolTradeObservation, SymbolIntelligenceEngine
@dataclass(frozen=True)
class OptimisationRecommendation:
    category:str; recommendation:str; expected_impact:str; requires_admin_approval:bool=True
class AIOptimisationEngine:
    def recommend(self, observations:list[SymbolTradeObservation])->tuple[OptimisationRecommendation,...]:
        recs=[]; symbols=sorted(set(o.symbol for o in observations)); profiler=SymbolIntelligenceEngine()
        for s in symbols:
            p=profiler.profile(s,observations)
            if p.win_rate < Decimal("45"): recs.append(OptimisationRecommendation("Symbol",f"Reduce score weighting or pause weak {s} setups until profile improves.","Lower drawdown from underperforming symbol"))
            if p.average_slippage > p.average_spread*Decimal("2") and p.average_spread>0: recs.append(OptimisationRecommendation("Execution",f"Avoid market execution for {s} during high slippage windows; require tighter spread gate.","Improved execution quality"))
            if p.best_session != "UNKNOWN": recs.append(OptimisationRecommendation("Session",f"Prefer {s} setups during {p.best_session}; penalise {p.worst_session}.","Improved trade selection"))
        return tuple(recs)
