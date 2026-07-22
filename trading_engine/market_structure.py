from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Candle, Direction, StructureState, SwingPoint

class MarketStructureEngine:
    def __init__(self, left_right: int = 2):
        if left_right < 1: raise ValueError("left_right must be positive")
        self.left_right = left_right
    def swings(self, candles: list[Candle]) -> tuple[SwingPoint, ...]:
        completed=[c for c in candles if c.completed]; out=[]; n=self.left_right
        for i in range(n, len(completed)-n):
            window=completed[i-n:i+n+1]; c=completed[i]
            if c.high == max(x.high for x in window): out.append(SwingPoint(i,c.time,c.high,"HIGH"))
            if c.low == min(x.low for x in window): out.append(SwingPoint(i,c.time,c.low,"LOW"))
        return tuple(out)
    def analyse(self, candles: list[Candle]) -> StructureState:
        completed=[c for c in candles if c.completed]; sw=self.swings(completed)
        highs=[s for s in sw if s.kind=="HIGH"][-3:]; lows=[s for s in sw if s.kind=="LOW"][-3:]
        bias=Direction.NEUTRAL; event="RANGE"
        if len(highs)>=2 and len(lows)>=2:
            hh=highs[-1].price>highs[-2].price; hl=lows[-1].price>lows[-2].price; lh=highs[-1].price<highs[-2].price; ll=lows[-1].price<lows[-2].price
            if hh and hl: bias=Direction.BUY; event="BOS_UP"
            elif lh and ll: bias=Direction.SELL; event="BOS_DOWN"
            elif hh and ll: event="EXPANSION"
            else: event="CHOCH"
        ranges=[c.range() for c in completed[-10:]] or [Decimal("0")]
        avg=sum(ranges,Decimal("0"))/Decimal(len(ranges)); recent=completed[-1].range() if completed else Decimal("0")
        expansion=recent>avg*Decimal("1.5"); compression=recent<avg*Decimal("0.6")
        accumulation=bias==Direction.NEUTRAL and compression; distribution=bias==Direction.NEUTRAL and expansion
        return StructureState(bias,event,sw,expansion,compression,accumulation,distribution)
