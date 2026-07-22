from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
@dataclass(frozen=True)
class SymbolTradeObservation:
    symbol:str; session:str; timeframe:str; profit:Decimal; rr:Decimal; holding_seconds:int; volatility:Decimal; spread:Decimal; slippage:Decimal
@dataclass(frozen=True)
class SymbolProfile:
    symbol:str; win_rate:Decimal; average_rr:Decimal; best_session:str; worst_session:str; average_holding_time:timedelta; average_volatility:Decimal; best_timeframe:str; average_spread:Decimal; average_slippage:Decimal; confidence_score:Decimal
class SymbolIntelligenceEngine:
    def profile(self,symbol:str,observations:list[SymbolTradeObservation])->SymbolProfile:
        obs=[o for o in observations if o.symbol==symbol]
        if not obs: return SymbolProfile(symbol,Decimal("50"),Decimal("0"),"UNKNOWN","UNKNOWN",timedelta(),Decimal("0"),"UNKNOWN",Decimal("0"),Decimal("0"),Decimal("50"))
        wins=[o for o in obs if o.profit>0]; win_rate=Decimal(len(wins)*100)/Decimal(len(obs)); avg_rr=sum((o.rr for o in obs),Decimal("0"))/Decimal(len(obs))
        session_profit={}; tf_profit={}
        for o in obs: session_profit[o.session]=session_profit.get(o.session,Decimal("0"))+o.profit; tf_profit[o.timeframe]=tf_profit.get(o.timeframe,Decimal("0"))+o.profit
        confidence=max(Decimal("0"),min(Decimal("100"),win_rate+avg_rr*Decimal("10")-sum((o.slippage for o in obs),Decimal("0"))/Decimal(len(obs))))
        return SymbolProfile(symbol,win_rate,avg_rr,max(session_profit,key=session_profit.get),min(session_profit,key=session_profit.get),timedelta(seconds=sum(o.holding_seconds for o in obs)/len(obs)),sum((o.volatility for o in obs),Decimal("0"))/Decimal(len(obs)),max(tf_profit,key=tf_profit.get),sum((o.spread for o in obs),Decimal("0"))/Decimal(len(obs)),sum((o.slippage for o in obs),Decimal("0"))/Decimal(len(obs)),confidence)
