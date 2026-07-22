from __future__ import annotations
from decimal import Decimal
import logging
from trading_engine.types import Candle, Direction

logger = logging.getLogger("trading")


class StreetSmartsEngine:
    """
    Laurence Connors' 'Street Smarts' Classic Reversal Strategy Module.
    Implements:
    1. 'Turtle Soup Plus One': Captures failed breakout entry on Day + 1.
    2. '80-20 Rule': Captures extreme close exhaustion reversals.
    """
    @staticmethod
    def evaluate_turtle_soup_plus_one(
        candles: list[Candle], 
        prior_high: Decimal, 
        prior_low: Decimal, 
        direction: Direction
    ) -> bool:
        """
        Turtle Soup Plus One:
        - Day 0: Price sweeps a 20-period high/low, but closes back inside the range.
        - Day + 1 (today): Price sweeps the Day 0 low/high again, then fails and reverses.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 2:
            return False
        
        last = completed[-1]
        if direction == Direction.BUY:
            # Low sweeps below the prior support, but closes back above
            return last.low < prior_low and last.close > prior_low
        elif direction == Direction.SELL:
            # High sweeps above the prior resistance, but closes back below
            return last.high > prior_high and last.close < prior_high
            
        return False

    @staticmethod
    def evaluate_80_20_pattern(candles: list[Candle]) -> tuple[bool, Direction]:
        """
        80-20 Rule:
        - Prior bar: Open and close are both in the top or bottom 20% of the bar's range.
        - Today's bar: Price breaks out beyond the prior bar's extreme, then fails and reverses back.
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
        
        # Bullish Reversal: Prior bar opened and closed in bottom 20%
        if open_pct <= Decimal("0.20") and close_pct <= Decimal("0.20"):
            # Today sweeps below yesterday's low and closes back above it (or yesterday's close)
            if last.low < prev.low and last.close > prev.close:
                return True, Direction.BUY
                
        # Bearish Reversal: Prior bar opened and closed in top 20%
        if open_pct >= Decimal("0.80") and close_pct >= Decimal("0.80"):
            # Today sweeps above yesterday's high and closes back below it (or yesterday's close)
            if last.high > prev.high and last.close < prev.close:
                return True, Direction.SELL
                
        return False, Direction.NEUTRAL
