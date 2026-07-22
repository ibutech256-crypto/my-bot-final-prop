from __future__ import annotations
from dataclasses import dataclass
from trading_engine.crt import CRTEngine
from trading_engine.fvg import FairValueGapEngine
from trading_engine.liquidity import LiquiditySweepEngine
from trading_engine.market_structure import MarketStructureEngine
from trading_engine.order_block import OrderBlockEngine
from trading_engine.types import Candle
@dataclass(frozen=True)
class ReplayFrame:
    index:int; candle:Candle; structure:str; crt:object; fvg_count:int; order_block_count:int; decision:str
class TradeReplayEngine:
    def __init__(self): self.crt=CRTEngine(); self.liq=LiquiditySweepEngine(); self.st=MarketStructureEngine(); self.fvg=FairValueGapEngine(); self.ob=OrderBlockEngine()
    def replay(self,candles:list[Candle])->list[ReplayFrame]:
        frames=[]
        for i in range(5,len(candles)+1):
            subset=candles[:i]; crt=self.crt.detect(subset); structure=self.st.analyse(subset); sweep=self.liq.detect_sweep(subset,crt,subset[-1].range()/100) if crt else None
            decision="LIQUIDITY_SWEEP_DETECTED" if sweep else "OBSERVE"
            frames.append(ReplayFrame(i-1,subset[-1],structure.last_event,crt,len(self.fvg.detect(subset)),len(self.ob.detect(subset)),decision))
        return frames
