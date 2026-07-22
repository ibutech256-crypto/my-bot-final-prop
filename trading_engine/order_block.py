from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Candle, Direction, Zone

class OrderBlockEngine:
    def detect(self, candles: list[Candle]) -> tuple[Zone, ...]:
        completed=[c for c in candles if c.completed]; zones=[]
        if len(completed)<5: return ()
        avg=sum((c.range() for c in completed[-20:]), Decimal("0"))/Decimal(min(len(completed),20))
        for i in range(2,len(completed)-1):
            c=completed[i]; nxt=completed[i+1]
            if c.direction()==Direction.SELL and nxt.direction()==Direction.BUY and nxt.range()>avg*Decimal("1.2") and nxt.close>c.high:
                zones.append(Zone(Direction.BUY,c.low,c.high,i,i,"VALID",nxt.range()/avg if avg else Decimal("1"),"BULLISH_ORDER_BLOCK"))
            if c.direction()==Direction.BUY and nxt.direction()==Direction.SELL and nxt.range()>avg*Decimal("1.2") and nxt.close<c.low:
                zones.append(Zone(Direction.SELL,c.low,c.high,i,i,"VALID",nxt.range()/avg if avg else Decimal("1"),"BEARISH_ORDER_BLOCK"))
        latest=completed[-1]
        final=[]
        for z in zones[-10:]:
            mitigated = latest.low <= z.high and latest.high >= z.low
            invalid = latest.close < z.low if z.direction==Direction.BUY else latest.close > z.high
            state = "INVALID" if invalid else "MITIGATED" if mitigated else "VALID"
            kind = "BREAKER_BLOCK" if invalid else z.kind
            final.append(Zone(z.direction,z.low,z.high,z.start_index,z.end_index,state,z.strength,kind))
        return tuple(final)
