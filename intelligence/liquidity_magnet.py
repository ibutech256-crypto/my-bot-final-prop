from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import Candle, Direction
@dataclass(frozen=True)
class LiquidityMagnet:
    level: Decimal; kind: str; strength: Decimal; coordinate: str
class LiquidityMagnetEngine:
    def _extremes(self,candles:list[Candle],label:str)->list[LiquidityMagnet]:
        if not candles: return []
        high=max(c.high for c in candles if c.completed); low=min(c.low for c in candles if c.completed)
        return [LiquidityMagnet(high,f"{label}_HIGH",Decimal("90"),str(high)),LiquidityMagnet(low,f"{label}_LOW",Decimal("90"),str(low))]
    def equal_levels(self,candles:list[Candle], tolerance:Decimal)->list[LiquidityMagnet]:
        levels=[]; completed=[c for c in candles if c.completed]
        for attr,kind in [("high","EQUAL_HIGHS"),("low","EQUAL_LOWS")]:
            vals=[getattr(c,attr) for c in completed]
            for v in vals:
                count=sum(1 for x in vals if abs(x-v)<=tolerance)
                if count>=2: levels.append(LiquidityMagnet(v,kind,Decimal(60+min(count,5)*5),str(v)))
        return sorted(set(levels), key=lambda x:(x.kind,x.level))
    def magnets(self, weekly:list[Candle], monthly:list[Candle], quarterly:list[Candle], execution:list[Candle], tick_size:Decimal)->tuple[LiquidityMagnet,...]:
        mags=self._extremes(weekly,"WEEKLY")+self._extremes(monthly,"MONTHLY")+self._extremes(quarterly,"QUARTERLY")+self.equal_levels(execution,tick_size*Decimal("3"))
        return tuple(sorted(mags, key=lambda m:m.strength, reverse=True))
    def target_for(self,direction:Direction, entry:Decimal, magnets:tuple[LiquidityMagnet,...], tick_size:Decimal)->Decimal|None:
        candidates=[m for m in magnets if (m.level>entry if direction==Direction.BUY else m.level<entry)]
        if not candidates: return None
        nearest=min(candidates, key=lambda m:abs(m.level-entry))
        return nearest.level - tick_size*Decimal("5") if direction==Direction.BUY else nearest.level + tick_size*Decimal("5")
