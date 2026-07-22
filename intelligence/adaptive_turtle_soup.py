from __future__ import annotations
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import AsyncIterator, Callable
from datetime import datetime, timezone
from intelligence.data_freshness import TimestampValidationEngine
from trading_engine.cisd import CISDEngine
from trading_engine.kod import KODEngine
from trading_engine.liquidity import LiquiditySweepEngine
from trading_engine.market_structure import MarketStructureEngine
from trading_engine.types import CRTRange, Candle, LiquidityEvent

@dataclass(frozen=True)
class PriceEvent:
    symbol: str
    bid: Decimal
    ask: Decimal
    time_msc: int

@dataclass(frozen=True)
class MicrostructureConfirmation:
    liquidity_event: LiquidityEvent
    m2_confirmed: bool
    m1_confirmed: bool
    reason: str

class AdaptiveTurtleSoupEngine:
    """Activates immediately on sweep, then switches confirmation monitoring to M2/M1 completed candles."""
    def __init__(self):
        self.freshness=TimestampValidationEngine(); self.liquidity=LiquiditySweepEngine(); self.structure=MarketStructureEngine(); self.kod=KODEngine(); self.cisd=CISDEngine()
    async def observe(self, price_events:AsyncIterator[PriceEvent], on_event:Callable[[PriceEvent],None], stop_after:int=500)->None:
        count=0
        async for event in price_events:
            event_time = datetime.fromtimestamp(event.time_msc / 1000, tz=timezone.utc)
            self.freshness.assert_fresh(event_time)
            on_event(event); count+=1
            if count>=stop_after: break
            await asyncio.sleep(0)
            
    def detect_20_bar_breach(self, candles: list[Candle], current_price: Decimal) -> bool:
        """
        Detects if current price breaches a 20-bar high/low (BSL/SSL sweep) asynchronously 
        without waiting for the M15/H1 bar close.
        """
        completed = [c for c in candles if c.completed]
        if len(completed) < 20:
            return False
        recent = completed[-20:]
        highest = max(c.high for c in recent)
        lowest = min(c.low for c in recent)
        return current_price > highest or current_price < lowest

    def calculate_ict_entries(self, sweep_price: Decimal, kod_candle: Candle, fvg_gap_ce: Optional[Decimal] = None) -> dict[str, Decimal]:
        """
        Calculates all 3 ICT Entry Types:
        - Entry Type 1: Direct Limit Order at Liquidity Level / Sweep point.
        - Entry Type 2: Market entry on the immediate KOD displacement candle close.
        - Entry Type 3: Limit order at the FVG Consequent Encroachment (CE / 50% midpoint).
        """
        entry_type_1 = sweep_price
        entry_type_2 = kod_candle.close
        
        # Entry Type 3: Consequent Encroachment (CE) of FVG (default fallback to 50% body of KOD candle)
        if fvg_gap_ce is not None:
            entry_type_3 = fvg_gap_ce
        else:
            entry_type_3 = (kod_candle.open + kod_candle.close) / Decimal("2.0")
            
        return {
            "Type_1_Limit": entry_type_1,
            "Type_2_Market": entry_type_2,
            "Type_3_CE_Limit": entry_type_3
        }

    def confirm_after_sweep(self, m5:list[Candle], m2:list[Candle], m1:list[Candle], crt:CRTRange, tick_size:Decimal)->MicrostructureConfirmation|None:
        sweep=self.liquidity.detect_sweep(m5,crt,tick_size)
        if sweep is None: return None
        st2=self.structure.analyse(m2); st1=self.structure.analyse(m1)
        m2_ok=self.kod.confirmed(m2,sweep) and self.cisd.confirmed(m2,sweep.direction,st2)
        m1_ok=self.kod.confirmed(m1,sweep) and self.cisd.confirmed(m1,sweep.direction,st1)
        if m2_ok or m1_ok: return MicrostructureConfirmation(sweep,m2_ok,m1_ok,"Lower-timeframe structural shift confirmed after HTF sweep")
        return MicrostructureConfirmation(sweep,False,False,"Sweep active; awaiting M2/M1 structural confirmation")
