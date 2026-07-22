from __future__ import annotations
from trading_engine.types import Candle, Direction, StructureState

class CISDEngine:
    """Change in State of Delivery confirmation from internal structure and momentum shift."""
    def confirmed(self, candles: list[Candle], intended: Direction, structure: StructureState) -> bool:
        completed=[c for c in candles if c.completed]
        if len(completed)<3: return False
        last=completed[-1]; prev=completed[-2]
        if intended == Direction.BUY:
            return last.close > prev.high and last.direction()==Direction.BUY and structure.last_event in {"BOS_UP","CHOCH","EXPANSION"}
        if intended == Direction.SELL:
            return last.close < prev.low and last.direction()==Direction.SELL and structure.last_event in {"BOS_DOWN","CHOCH","EXPANSION"}
        return False
