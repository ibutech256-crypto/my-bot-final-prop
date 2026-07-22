from __future__ import annotations
from decimal import Decimal
from statistics import fmean
from trading_engine.types import Candle, Direction
class TrendEngine:
    def bias(self, candles: list[Candle], fast:int=20, slow:int=50) -> Direction:
        completed=[c for c in candles if c.completed]
        if len(completed)<slow: return Direction.NEUTRAL
        closes=[float(c.close) for c in completed]
        f=Decimal(str(fmean(closes[-fast:]))); s=Decimal(str(fmean(closes[-slow:])))
        if f>s and completed[-1].close>f: return Direction.BUY
        if f<s and completed[-1].close<f: return Direction.SELL
        return Direction.NEUTRAL
