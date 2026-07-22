from __future__ import annotations
from decimal import Decimal
from trading_engine.types import CRTRange, Candle, Direction, LiquidityEvent

class LiquiditySweepEngine:
    def __init__(self, equal_tolerance_ticks: int = 3): self.equal_tolerance_ticks = equal_tolerance_ticks
    def equal_highs(self, candles: list[Candle], tick_size: Decimal) -> tuple[Decimal, ...]:
        tol = tick_size * self.equal_tolerance_ticks; levels=[]
        highs=[c.high for c in candles if c.completed]
        for i,h in enumerate(highs):
            if sum(1 for x in highs[max(0,i-10):i+11] if abs(x-h)<=tol) >= 2: levels.append(h)
        return tuple(sorted(set(levels)))
    def equal_lows(self, candles: list[Candle], tick_size: Decimal) -> tuple[Decimal, ...]:
        tol = tick_size * self.equal_tolerance_ticks; levels=[]; lows=[c.low for c in candles if c.completed]
        for i,l in enumerate(lows):
            if sum(1 for x in lows[max(0,i-10):i+11] if abs(x-l)<=tol) >= 2: levels.append(l)
        return tuple(sorted(set(levels)))
    def detect_sweep(self, candles: list[Candle], crt: CRTRange, tick_size: Decimal) -> LiquidityEvent | None:
        completed=[c for c in candles if c.completed]
        if len(completed)<2: return None
        tol=tick_size*self.equal_tolerance_ticks
        eq_h = self.equal_highs(completed[:-1], tick_size)
        eq_l = self.equal_lows(completed[:-1], tick_size)
        
        for idx_offset in [-1, -2, -3]:
            if abs(idx_offset) > len(completed): continue
            c = completed[idx_offset]
            idx = len(completed) + idx_offset
            
            # Check BSL or EQH sweep
            if (c.high > crt.high + tol and c.close < crt.high) or any(c.high > h + tol and c.close < h for h in eq_h):
                failed = c.close <= crt.internal_high
                swept = crt.high if c.high > crt.high + tol else max([h for h in eq_h if c.high > h + tol], default=crt.high)
                return LiquidityEvent(Direction.SELL, swept, "BUY_SIDE_LIQUIDITY_SWEEP", idx, failed, f"Buy-side/Equal-high liquidity ({swept}) swept and closed back inside range.")
                
            # Check SSL or EQL sweep
            if (c.low < crt.low - tol and c.close > crt.low) or any(c.low < l - tol and c.close > l for l in eq_l):
                failed = c.close >= crt.internal_low
                swept = crt.low if c.low < crt.low - tol else min([l for l in eq_l if c.low < l - tol], default=crt.low)
                return LiquidityEvent(Direction.BUY, swept, "SELL_SIDE_LIQUIDITY_SWEEP", idx, failed, f"Sell-side/Equal-low liquidity ({swept}) swept and closed back inside range.")
        return None