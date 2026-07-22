from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean
@dataclass(frozen=True)
class Candle: time:str; open:Decimal; high:Decimal; low:Decimal; close:Decimal; volume:Decimal
@dataclass(frozen=True)
class GeneratedSignal: direction:str; entry:Decimal; stop_loss:Decimal; take_profit:Decimal; confidence:Decimal; rationale:str
class MovingAverageMomentumStrategy:
    def __init__(self,fast_period:int=20,slow_period:int=50,reward_risk:Decimal=Decimal("2")):
        if fast_period>=slow_period: raise ValueError("fast_period must be less than slow_period")
        self.fast_period=fast_period; self.slow_period=slow_period; self.reward_risk=reward_risk
    def evaluate(self,candles:list[Candle])->GeneratedSignal|None:
        if len(candles)<self.slow_period: return None
        closes=[float(c.close) for c in candles]; fast=Decimal(str(fmean(closes[-self.fast_period:]))); slow=Decimal(str(fmean(closes[-self.slow_period:])))
        last=candles[-1]; atr=sum((c.high-c.low for c in candles[-14:]),Decimal("0"))/Decimal("14")
        if fast>slow and last.close>fast:
            sl=last.close-atr; return GeneratedSignal("BUY",last.close,sl,last.close+(last.close-sl)*self.reward_risk,Decimal("72.50"),"Bullish moving-average momentum confirmation.")
        if fast<slow and last.close<fast:
            sl=last.close+atr; return GeneratedSignal("SELL",last.close,sl,last.close-(sl-last.close)*self.reward_risk,Decimal("72.50"),"Bearish moving-average momentum confirmation.")
        return None
