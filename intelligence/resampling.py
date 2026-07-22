from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from trading_engine.crt import CRTEngine
from trading_engine.liquidity import LiquiditySweepEngine
from trading_engine.market_structure import MarketStructureEngine
from trading_engine.types import Candle
from intelligence.resampling_cache import GLOBAL_RESAMPLER_CACHE

class CustomTimeframeEngine:
    """Aggregates MT5 lower-timeframe candles into institutional custom candles, including 69-minute bars."""
    def __init__(self):
        self.crt=CRTEngine(lookback=10); self.structure=MarketStructureEngine(); self.liquidity=LiquiditySweepEngine()
    def resample_minutes(self, candles:list[Candle], minutes:int=69, anchor:datetime|None=None, cache_key:str|None=None)->list[Candle]:
        if cache_key:
            cached = GLOBAL_RESAMPLER_CACHE.get(f"{cache_key}:{minutes}")
            if cached is not None:
                return cached
        completed=sorted([c for c in candles if c.completed], key=lambda c:c.time)
        if not completed: return []
        anchor=(anchor or completed[0].time).astimezone(timezone.utc).replace(second=0,microsecond=0)
        buckets: dict[int,list[Candle]] = defaultdict(list)
        for c in completed:
            delta=int((c.time.astimezone(timezone.utc)-anchor).total_seconds()//60)
            buckets[delta//minutes].append(c)
        out=[]
        for key in sorted(buckets):
            group=buckets[key]
            out.append(Candle(time=anchor+timedelta(minutes=key*minutes), open=group[0].open, high=max(x.high for x in group), low=min(x.low for x in group), close=group[-1].close, volume=sum((x.volume for x in group), Decimal("0")), completed=all(x.completed for x in group)))
        if cache_key:
            GLOBAL_RESAMPLER_CACHE.set(f"{cache_key}:{minutes}", out)
        return out
    def institutional_69m_context(self, candles:list[Candle])->dict:
        bars=self.resample_minutes(candles,69)
        crt=self.crt.detect(bars)
        structure=self.structure.analyse(bars) if len(bars)>=5 else None
        sweep=self.liquidity.detect_sweep(bars,crt,Decimal("0.00001")) if crt else None
        return {"candles":bars,"latest":bars[-1] if bars else None,"crt":crt,"structure":structure,"liquidity":sweep,"range":bars[-1].range() if bars else Decimal("0")}
