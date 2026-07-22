from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from intelligence.data_freshness import TimestampValidationEngine
from trading_engine.ai_explanation import AITradeExplanationEngine
from trading_engine.cisd import CISDEngine
from trading_engine.crt import CRTEngine
from trading_engine.fvg import FairValueGapEngine
from trading_engine.kod import KODEngine
from trading_engine.liquidity import LiquiditySweepEngine
from trading_engine.market_structure import MarketStructureEngine
from trading_engine.news_filter import EconomicEvent, NewsFilterEngine
from trading_engine.order_block import OrderBlockEngine
from trading_engine.portfolio import Exposure, PortfolioEngine
from trading_engine.premium_discount import PremiumDiscountEngine
from trading_engine.risk import PositionSizingEngine, RiskEngine, RiskLimits, RiskState
from trading_engine.scoring import ScoringEngine
from trading_engine.session import SessionEngine
from trading_engine.trade_management import TradeManagementEngine
from trading_engine.trend import TrendEngine
from trading_engine.types import AccountSnapshot, Candle, Direction, SymbolSpec, Timeframe, TradeSetup

@dataclass(frozen=True)
class EngineConfig:
    minimum_score: Decimal = Decimal("75")
    risk_limits: RiskLimits = RiskLimits()
    mode: str = "SIGNAL_ONLY"

class RomeoTPTOrchestrator:
    """Deterministic Romeo TPT execution sequence. It never evaluates unfinished candles for entries."""
    def __init__(self, config: EngineConfig = EngineConfig()):
        self.config=config; self.freshness=TimestampValidationEngine(); self.crt=CRTEngine(); self.liquidity=LiquiditySweepEngine(); self.structure=MarketStructureEngine(); self.kod=KODEngine(); self.cisd=CISDEngine(); self.ob=OrderBlockEngine(); self.fvg=FairValueGapEngine(); self.pd=PremiumDiscountEngine(); self.session=SessionEngine(); self.news=NewsFilterEngine(); self.trend=TrendEngine(); self.sizer=PositionSizingEngine(); self.risk=RiskEngine(); self.portfolio=PortfolioEngine(); self.scoring=ScoringEngine(); self.tm=TradeManagementEngine(); self.explainer=AITradeExplanationEngine()
    def evaluate(self, symbol: str, timeframe: Timeframe, candles: list[Candle], htf_candles: dict[Timeframe,list[Candle]], account: AccountSnapshot, spec: SymbolSpec, risk_state: RiskState, exposures: list[Exposure], events: list[EconomicEvent], now: datetime) -> TradeSetup | None:
        completed=[c for c in candles if c.completed]
        if len(completed)<60: return None
        # Hard abort: never calculate or execute a setup from stale price data.
        self.freshness.assert_fresh(completed[-1].time)
        crt_range=self.crt.detect(completed)
        if crt_range is None: return None
        sweep=self.liquidity.detect_sweep(completed,crt_range,spec.tick_size)
        if sweep is None or sweep.failed: return None
        direction=sweep.direction
        last=completed[-1]

        # Evaluate Classic Patterns & Street Smarts (v1.9.0)
        kod_ok = self.kod.confirmed(completed, sweep)
        
        from trading_engine.street_smarts import StreetSmartsEngine
        ts_plus_one_ok = StreetSmartsEngine.evaluate_turtle_soup_plus_one(
            completed, crt_range.high, crt_range.low, direction
        )
        
        pattern_80_20_ok, r_dir = StreetSmartsEngine.evaluate_80_20_pattern(completed)
        is_80_20_ok = pattern_80_20_ok and (r_dir == direction)

        if not (kod_ok or ts_plus_one_ok or is_80_20_ok):
            return None

        # Calculate Three-Way Entry Engine recommendations
        from intelligence.adaptive_turtle_soup import AdaptiveTurtleSoupEngine
        ats_engine = AdaptiveTurtleSoupEngine()
        fvg_ce = (last.open + last.close) / Decimal("2.0")
        entry_options = ats_engine.calculate_ict_entries(sweep.swept_level, last, fvg_ce)
        
        structure=self.structure.analyse(completed)
        if not self.cisd.confirmed(completed,direction,structure): return None
        if structure.bias not in {direction,Direction.NEUTRAL}: return None
        htf_biases=[self.trend.bias(v) for k,v in htf_candles.items() if k in {Timeframe.MN1,Timeframe.W1,Timeframe.D1,Timeframe.H4,Timeframe.H1}]
        htf_ok=all(b in {direction,Direction.NEUTRAL} for b in htf_biases) if htf_biases else True
        if not htf_ok: return None
        session_state=self.session.evaluate(now)
        if not session_state.liquid: return None
        news_state=self.news.evaluate(now,symbol,events)
        if not news_state.trading_allowed: return None
        if not self.pd.permits(direction,last.close,crt_range): return None
        gaps=self.fvg.detect(completed)
        if not self.fvg.permits(direction,last.close,gaps): return None
        risk_ok,risk_reason=self.risk.validate(self.config.risk_limits,risk_state)
        if not risk_ok: return None
        # Calculate 14-period ATR buffer (v1.9.0)
        atr = Decimal("0")
        if len(completed) >= 15:
            tr_list = []
            for i in range(1, len(completed)):
                c = completed[i]
                prev = completed[i-1]
                tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
                tr_list.append(tr)
            atr = sum(tr_list[-14:]) / Decimal("14")

        # Spread Protection Gates & Spread-to-Target Ratio (v1.9.2)
        point = spec.tick_size
        raw_spread = Decimal(str(spec.spread_points)) * point
        
        # Max Absolute Spread Gate: Reject entries if spread > 2.5 pips (25 points)
        pip_size = point * Decimal("10") if spec.digits in [3, 5] else point
        if raw_spread > Decimal("2.5") * pip_size:
            return None

        # Stop Loss: strictly beyond sweep extreme + (1.5x ATR + Current Spread Buffer)
        atr_buffer = Decimal("1.5") * atr + raw_spread
        if direction == Direction.BUY:
            stop_loss = min(last.low, crt_range.low) - atr_buffer
        else:
            stop_loss = max(last.high, crt_range.high) + atr_buffer

        # Spread-to-Target Ratio: Current spread must not exceed 15% of Entry-to-SL distance
        risk_dist = abs(last.close - stop_loss)
        if risk_dist > 0 and raw_spread / risk_dist > Decimal("0.15"):
            return None
        plan=self.tm.build_plan(direction,last.close,stop_loss)
        size=self.sizer.calculate(account,spec,last.close,stop_loss,self.config.risk_limits.risk_pct)
        if size.final_lot_size <= 0: return None
        portfolio_ok,portfolio_reason=self.portfolio.permits(exposures,spec,self.config.risk_limits.risk_pct)
        if not portfolio_ok: return None
        volatility_ok = last.range() > spec.tick_size * Decimal("5")
        score=self.scoring.score(direction,sweep,True,True,htf_ok,session_state,structure,True,volatility_ok,news_state,self.config.minimum_score)
        if not score.passed: return None
        rr=abs(plan.tp2-last.close)/abs(last.close-stop_loss)
        target=str(crt_range.target_high if direction==Direction.BUY else crt_range.target_low)
        explanation=self.explainer.explain(direction,sweep,score,structure,session_state,str(rr),target,"controlled")
        audit={"sequence":["CRT Range","Liquidity Sweep","Rejection","CISD","KOD Close","Structure","HTF Alignment","Session","Risk","Score","Execution Ready"],"risk_reason":risk_reason,"portfolio_reason":portfolio_reason,"news_blockers":news_state.blocking_events}
        return TradeSetup(symbol,timeframe,direction,last.close,stop_loss,plan.tp1,plan.tp2,plan.tp3,rr,score,crt_range,sweep,structure,self.ob.detect(completed),gaps,session_state,size,explanation,audit)
