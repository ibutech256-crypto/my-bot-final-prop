from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Candle, Direction, LiquidityEvent

class KODEngine:
    """Killzone Opposing Displacement confirmation; evaluates completed candles only."""
    def __init__(self, min_body_ratio: Decimal = Decimal("0.55"), min_rejection_ratio: Decimal = Decimal("0.30")):
        self.min_body_ratio=min_body_ratio; self.min_rejection_ratio=min_rejection_ratio
    def confirmed(self, candles: list[Candle], liquidity_event: LiquidityEvent, atr_14: Decimal = Decimal("0")) -> bool:
        completed=[c for c in candles if c.completed]
        if len(completed) < 21: return False
        c=completed[-1]
        if c.range() <= 0: return False
        
        # 1. Displacement Ratio: Displacement body must be >= 1.8x the 14-period ATR
        if atr_14 > 0 and c.body() < Decimal("1.8") * atr_14:
            return False
            
        # 2. Velocity Verification: Last candle tick volume >= 1.5x the 20-candle average
        avg_vol_20 = sum(x.volume for x in completed[-21:-1]) / Decimal("20")
        if avg_vol_20 > 0 and c.volume < Decimal("1.5") * avg_vol_20:
            return False

        body_ratio=c.body()/c.range()
        if liquidity_event.direction == Direction.BUY:
            return c.direction()==Direction.BUY and body_ratio>=self.min_body_ratio and c.lower_wick()/c.range()>=self.min_rejection_ratio
        if liquidity_event.direction == Direction.SELL:
            return c.direction()==Direction.SELL and body_ratio>=self.min_body_ratio and c.upper_wick()/c.range()>=self.min_rejection_ratio
        return False

    def confirm_turtle_soup_plus_one(self, candles: list[Candle], prior_high: Decimal, prior_low: Decimal, direction: Direction) -> bool:
        """
        Laurence Connors 'Turtle Soup Plus One' pattern.
        Captures clean breakout failure entries on Day + 1.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 2: 
            return False
        last = completed[-1]
        
        if direction == Direction.BUY:
            return last.low < prior_low and last.close > prior_low
        elif direction == Direction.SELL:
            return last.high > prior_high and last.close < prior_high
        return False

    def confirm_80_20_rule(self, candles: list[Candle]) -> tuple[bool, Direction]:
        """
        Laurence Connors '80-20 Rule' reversal pattern.
        Identifies when prior bar opened/closed in top/bottom 20% of range and reverses.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 2: 
            return False, Direction.NEUTRAL
        prev = completed[-2]
        last = completed[-1]
        
        if prev.range() <= 0: 
            return False, Direction.NEUTRAL
        
        open_pct = (prev.open - prev.low) / prev.range()
        close_pct = (prev.close - prev.low) / prev.range()
        
        # Bearish 80-20
        if open_pct <= Decimal("0.20") and close_pct <= Decimal("0.20"):
            if last.high > prev.high and last.close < prev.close:
                return True, Direction.SELL
                
        # Bullish 80-20
        if open_pct >= Decimal("0.80") and close_pct >= Decimal("0.80"):
            if last.low < prev.low and last.close > prev.close:
                return True, Direction.BUY
                
        return False, Direction.NEUTRAL
