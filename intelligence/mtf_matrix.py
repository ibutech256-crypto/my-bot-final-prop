from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.fvg import FairValueGapEngine
from trading_engine.market_structure import MarketStructureEngine
from trading_engine.order_block import OrderBlockEngine
from trading_engine.premium_discount import PremiumDiscountEngine
from trading_engine.trend import TrendEngine
from trading_engine.types import Candle, Direction, Timeframe, Zone
from intelligence.resampling import CustomTimeframeEngine

HIERARCHY=(Timeframe.MN1,Timeframe.W1,Timeframe.D1,Timeframe.H4,Timeframe.H1,Timeframe.M15,Timeframe.M5,Timeframe.M1)

@dataclass(frozen=True)
class TimeframeContext:
    timeframe: str
    bias: Direction
    structure_event: str
    order_blocks: tuple[Zone,...]
    fair_value_gaps: tuple[Zone,...]
    premium_discount: str
    expansion: bool
    compression: bool

@dataclass(frozen=True)
class MatrixContext:
    macro_direction: Direction
    macro_liquidity: str
    macro_order_blocks: tuple[Zone,...]
    macro_fair_value_gaps: tuple[Zone,...]
    weekly_bias: Direction
    daily_bias: Direction
    current_expansion: bool
    current_compression: bool
    institutional_premium: bool
    institutional_discount: bool
    execution_context: str
    contexts: dict[str, TimeframeContext]
    custom_69m: dict

class MultiTimeframeMatrixEngine:
    def __init__(self):
        self.trend=TrendEngine(); self.structure=MarketStructureEngine(); self.ob=OrderBlockEngine(); self.fvg=FairValueGapEngine(); self.resampler=CustomTimeframeEngine(); self.pd=PremiumDiscountEngine()
    def analyse(self, data:dict[Timeframe,list[Candle]], execution_tf:Timeframe=Timeframe.M5)->MatrixContext:
        contexts={}
        for tf,candles in data.items():
            if not candles: continue
            st=self.structure.analyse(candles); obs=self.ob.detect(candles); fvgs=self.fvg.detect(candles)
            zone="EQUILIBRIUM"
            if candles and obs:
                high=max(c.high for c in candles if c.completed); low=min(c.low for c in candles if c.completed); mid=(high+low)/Decimal("2"); zone="PREMIUM" if candles[-1].close>mid else "DISCOUNT" if candles[-1].close<mid else "EQUILIBRIUM"
            contexts[tf.value]=TimeframeContext(tf.value,self.trend.bias(candles),st.last_event,obs,fvgs,zone,st.expansion,st.compression)
        base=data.get(Timeframe.M1) or data.get(Timeframe.M5) or []
        c69=self.resampler.institutional_69m_context(base)
        macro_biases=[contexts[t.value].bias for t in (Timeframe.MN1,Timeframe.W1,Timeframe.D1) if t.value in contexts]
        macro=Direction.NEUTRAL
        if macro_biases and all(b==Direction.BUY for b in macro_biases if b!=Direction.NEUTRAL): macro=Direction.BUY
        elif macro_biases and all(b==Direction.SELL for b in macro_biases if b!=Direction.NEUTRAL): macro=Direction.SELL
        weekly=contexts.get(Timeframe.W1.value, TimeframeContext('W1',Direction.NEUTRAL,'',(),(),'EQUILIBRIUM',False,False)).bias
        daily=contexts.get(Timeframe.D1.value, TimeframeContext('D1',Direction.NEUTRAL,'',(),(),'EQUILIBRIUM',False,False)).bias
        exec_ctx=contexts.get(execution_tf.value)
        macro_obs=tuple(z for tf in (Timeframe.MN1.value,Timeframe.W1.value,Timeframe.D1.value) for z in contexts.get(tf,TimeframeContext(tf,Direction.NEUTRAL,'',(),(),'EQ',False,False)).order_blocks)
        macro_fvgs=tuple(z for tf in (Timeframe.MN1.value,Timeframe.W1.value,Timeframe.D1.value) for z in contexts.get(tf,TimeframeContext(tf,Direction.NEUTRAL,'',(),(),'EQ',False,False)).fair_value_gaps)
        return MatrixContext(macro, "HTF liquidity mapped from monthly/weekly/daily extremes", macro_obs, macro_fvgs, weekly, daily, bool(exec_ctx and exec_ctx.expansion), bool(exec_ctx and exec_ctx.compression), bool(exec_ctx and exec_ctx.premium_discount=="PREMIUM"), bool(exec_ctx and exec_ctx.premium_discount=="DISCOUNT"), exec_ctx.structure_event if exec_ctx else "NO_CONTEXT", contexts, c69)
