from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean
from trading_engine.types import Candle, Direction
@dataclass(frozen=True)
class MarketRegime:
    trend:str; volatility:str; phase:str; risk_mode:str; confidence:Decimal
class MarketRegimeEngine:
    def classify(self,candles:list[Candle], reference_risk_on:Direction=Direction.NEUTRAL)->MarketRegime:
        completed=[c for c in candles if c.completed]
        if len(completed)<30: return MarketRegime("UNKNOWN","UNKNOWN","UNKNOWN","NEUTRAL",Decimal("0"))
        closes=[float(c.close) for c in completed]; fast=Decimal(str(fmean(closes[-10:]))); slow=Decimal(str(fmean(closes[-30:])))
        ranges=[c.range() for c in completed[-30:]]; avg=sum(ranges,Decimal("0"))/Decimal(len(ranges)); recent=sum(ranges[-5:],Decimal("0"))/Decimal("5")
        trend="TRENDING_UP" if fast>slow else "TRENDING_DOWN" if fast<slow else "RANGING"
        vol="HIGH_VOLATILITY" if recent>avg*Decimal("1.4") else "LOW_VOLATILITY" if recent<avg*Decimal("0.7") else "NORMAL_VOLATILITY"
        phase="EXPANDING" if recent>avg*Decimal("1.2") else "COMPRESSING" if recent<avg*Decimal("0.8") else "BALANCED"
        risk="RISK_ON" if reference_risk_on==Direction.BUY else "RISK_OFF" if reference_risk_on==Direction.SELL else "NEUTRAL"
        return MarketRegime(trend,vol,phase,risk,Decimal("80"))
