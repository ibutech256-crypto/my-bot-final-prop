from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Candle, Direction, Zone

class FairValueGapEngine:
    def detect(self, candles: list[Candle]) -> tuple[Zone, ...]:
        completed=[c for c in candles if c.completed]; gaps=[]
        for i in range(2,len(completed)):
            a,b,c=completed[i-2],completed[i-1],completed[i]
            if a.high < c.low:
                strength=(c.low-a.high)/(b.range() or Decimal("1")); gaps.append(Zone(Direction.BUY,a.high,c.low,i-2,i,"VALID",strength,"BULLISH_FVG"))
            if a.low > c.high:
                strength=(a.low-c.high)/(b.range() or Decimal("1")); gaps.append(Zone(Direction.SELL,c.high,a.low,i-2,i,"VALID",strength,"BEARISH_FVG"))
        latest=completed[-1] if completed else None; out=[]
        for g in gaps[-10:]:
            ce=(g.low+g.high)/Decimal("2")
            filled = latest is not None and latest.low <= g.low and latest.high >= g.high
            mitigated = latest is not None and latest.low <= ce <= latest.high
            invalid = latest is not None and ((g.direction==Direction.BUY and latest.close<g.low) or (g.direction==Direction.SELL and latest.close>g.high))
            state="INVALID" if invalid else "FILLED" if filled else "MITIGATED" if mitigated else "VALID"
            out.append(Zone(g.direction,g.low,g.high,g.start_index,g.end_index,state,g.strength,g.kind))
        return tuple(out)
    def permits(self, direction: Direction, price: Decimal, gaps: tuple[Zone, ...]) -> bool:
        relevant=[g for g in gaps if g.direction==direction and g.state in {"VALID","MITIGATED"}]
        if not relevant: return True
        nearest=relevant[-1]
        return nearest.low <= price <= nearest.high or nearest.state == "MITIGATED"
