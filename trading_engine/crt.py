from __future__ import annotations
from decimal import Decimal
from trading_engine.types import CRTRange, Candle

class CRTEngine:
    """Candle Range Theory range detector using only completed candles."""
    def __init__(self, lookback: int = 20, internal_ratio: Decimal = Decimal("0.50")):
        if lookback < 5: raise ValueError("CRT lookback must be at least 5")
        self.lookback = lookback; self.internal_ratio = internal_ratio
    def detect(self, candles: list[Candle]) -> CRTRange | None:
        completed = [c for c in candles if c.completed]
        if len(completed) < self.lookback: return None
        window = completed[-self.lookback:]
        high = max(c.high for c in window); low = min(c.low for c in window); width = high - low
        if width <= 0: return None
        midpoint = low + width * Decimal("0.5")
        internal_width = width * self.internal_ratio
        internal_low = midpoint - internal_width / Decimal("2"); internal_high = midpoint + internal_width / Decimal("2")
        prior = completed[-self.lookback*2:-self.lookback] if len(completed) >= self.lookback*2 else completed[:-self.lookback]
        prior_width = (max((c.high for c in prior), default=high) - min((c.low for c in prior), default=low)) if prior else width
        state = "EXPANSION" if width > prior_width * Decimal("1.25") else "COMPRESSION" if width < prior_width * Decimal("0.75") else "BALANCED"
        return CRTRange(high=high, low=low, start_index=len(completed)-self.lookback, end_index=len(completed)-1, internal_high=internal_high, internal_low=internal_low, external_high=high+width, external_low=low-width, state=state, target_high=high+width*Decimal("0.5"), target_low=low-width*Decimal("0.5"))
