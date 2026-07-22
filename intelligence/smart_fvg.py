from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from trading_engine.types import Candle, Direction
@dataclass(frozen=True)
class SmartFVG:
    created_at: datetime; direction: Direction; low: Decimal; high: Decimal; width: Decimal; strength: Decimal; age_bars: int; fill_pct: Decimal; midpoint: Decimal; mitigated: bool; invalidated: bool; state: str
class SmartFairValueGapEngine:
    def detect(self,candles:list[Candle])->tuple[SmartFVG,...]:
        completed=[c for c in candles if c.completed]; out=[]
        for i in range(2,len(completed)):
            a,b,c=completed[i-2],completed[i-1],completed[i]
            items=[]
            if a.high < c.low: items.append((Direction.BUY,a.high,c.low))
            if a.low > c.high: items.append((Direction.SELL,c.high,a.low))
            for direction,low,high in items:
                midpoint=(high+low)/Decimal("2"); width=high-low; future=completed[i+1:]; invalid=False; fill=Decimal("0"); mitigated=False
                for f in future:
                    body_low=min(f.open,f.close); body_high=max(f.open,f.close)
                    if direction==Direction.BUY and body_low < midpoint and f.close < midpoint: invalid=True
                    if direction==Direction.SELL and body_high > midpoint and f.close > midpoint: invalid=True
                    overlap=max(Decimal("0"), min(high,f.high)-max(low,f.low)); fill=max(fill, min(Decimal("100"), overlap/width*Decimal("100"))) if width else Decimal("0")
                    if f.low<=midpoint<=f.high: mitigated=True
                state="INVALID" if invalid else "FILLED" if fill>=Decimal("99") else "MITIGATED" if mitigated else "VALID"
                out.append(SmartFVG(b.time,direction,low,high,width,width/(b.range() or Decimal("1")),len(future),fill,midpoint,mitigated,invalid,state))
        return tuple(out[-20:])
    def confluence_score(self,gap:SmartFVG)->Decimal:
        if gap.invalidated: return Decimal("0")
        age_penalty=min(Decimal(gap.age_bars),Decimal("50"))*Decimal("0.5")
        fill_penalty=gap.fill_pct*Decimal("0.3")
        return max(Decimal("0"), Decimal("100") + gap.strength*Decimal("10") - age_penalty - fill_penalty)
