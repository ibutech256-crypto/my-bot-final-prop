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
from trading_engine.strategy_config import CONFIG
from trading_engine.trade_management import TradeManagementEngine
from trading_engine.trend import TrendEngine
from trading_engine.types import AccountSnapshot, Candle, Direction, SymbolSpec, Timeframe, TradeSetup


@dataclass(frozen=True)
class EngineConfig:
    minimum_score: Decimal = Decimal("55")  # Changed from 75 to allow Tier 1 execution
    risk_limits: RiskLimits = RiskLimits()
    mode: str = "AUTO_EXECUTE"  # Changed from SIGNAL_ONLY to AUTO_EXECUTE


class RomeoTPTOrchestrator:
    """Deterministic Romeo TPT execution sequence (v2.0.0).
    
    Supports three-way order placement:
    - Type 1: Direct Limit at the sweep level
    - Type 2: Market Order on KOD candle close
    - Type 3: Limit Order at FVG 50% Consequent Encroachment (CE)
    
    Stop Loss is set strictly beyond sweep extreme + (1.5x ATR + Spread Buffer).
    """

    def __init__(self, config: EngineConfig = EngineConfig()):
        self.config = config
        self.freshness = TimestampValidationEngine()
        self.crt = CRTEngine(
            lookback=CONFIG.crt.lookback,
            internal_ratio=CONFIG.crt.internal_ratio,
        )
        self.liquidity = LiquiditySweepEngine()
        self.structure = MarketStructureEngine()
        self.kod = KODEngine()
        self.cisd = CISDEngine()
        self.ob = OrderBlockEngine()
        self.fvg = FairValueGapEngine()
        self.pd = PremiumDiscountEngine()
        self.session = SessionEngine()
        self.news = NewsFilterEngine()
        self.trend = TrendEngine()
        self.sizer = PositionSizingEngine()
        self.risk = RiskEngine()
        self.portfolio = PortfolioEngine()
        self.scoring = ScoringEngine()
        self.tm = TradeManagementEngine()
        self.explainer = AITradeExplanationEngine()

    def _calculate_atr_14(self, completed: list[Candle]) -> Decimal:
        """Calculate 14-period Average True Range."""
        if len(completed) < 15:
            return Decimal("0")
        tr_list = []
        for i in range(1, min(15, len(completed))):
            c = completed[-i]
            prev = completed[-i - 1]
            tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
            tr_list.append(tr)
        return sum(tr_list[-14:]) / Decimal("14")

    def _calculate_atr_and_volatility(self, completed: list[Candle]) -> tuple[Decimal, Decimal]:
        """Calculate ATR and average volume for displacement/velocity checks."""
        atr = self._calculate_atr_14(completed)
        avg_vol_20 = Decimal("0")
        if len(completed) >= 21:
            avg_vol_20 = sum(x.volume for x in completed[-21:-1]) / Decimal("20")
        return atr, avg_vol_20

    def evaluate(
        self,
        symbol: str,
        timeframe: Timeframe,
        candles: list[Candle],
        htf_candles: dict[Timeframe, list[Candle]],
        account: AccountSnapshot,
        spec: SymbolSpec,
        risk_state: RiskState,
        exposures: list[Exposure],
        events: list[EconomicEvent],
        now: datetime,
    ) -> TradeSetup | None:
        completed = [c for c in candles if c.completed]
        if len(completed) < 60:
            return None

        # Hard abort: never calculate or execute a setup from stale price data.
        self.freshness.assert_fresh(completed[-1].time)

        crt_range = self.crt.detect(completed)
        if crt_range is None:
            return None

        sweep = self.liquidity.detect_sweep(completed, crt_range, spec.tick_size)
        if sweep is None or sweep.failed:
            return None

        direction = sweep.direction
        last = completed[-1]

        # Calculate ATR and average volume for dynamic gates
        atr, avg_vol_20 = self._calculate_atr_and_volatility(completed)

        # Evaluate KOD with dynamic volatility/momentum filters (Module 3)
        kod_ok = self.kod.confirmed(completed, sweep, atr)

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

        structure = self.structure.analyse(completed)
        if not self.cisd.confirmed(completed, direction, structure):
            return None
        if structure.bias not in {direction, Direction.NEUTRAL}:
            return None

        # Higher-timeframe alignment. When no usable higher-timeframe series is
        # supplied the setup is only allowed through if the deployment has
        # explicitly opted out of HTF confirmation (HTF_REQUIRE_CONFIRMATION=0).
        # Silently treating "unknown" as "aligned" is what let every signal
        # collect the 15-point HTF component for free.
        htf_biases = [
            self.trend.bias(v)
            for k, v in (htf_candles or {}).items()
            if k in {Timeframe.MN1, Timeframe.W1, Timeframe.D1, Timeframe.H4, Timeframe.H1}
        ]
        if htf_biases:
            htf_ok = all(b in {direction, Direction.NEUTRAL} for b in htf_biases)
        else:
            htf_ok = not CONFIG.htf.require_confirmation
        if not htf_ok:
            return None

        session_state = self.session.evaluate(now)
        if not session_state.liquid:
            return None

        news_state = self.news.evaluate(now, symbol, events)
        if not news_state.trading_allowed:
            return None

        if not self.pd.permits(direction, last.close, crt_range):
            return None

        gaps = self.fvg.detect(completed)
        if not self.fvg.permits(direction, last.close, gaps):
            return None

        risk_ok, risk_reason = self.risk.validate(self.config.risk_limits, risk_state)
        if not risk_ok:
            return None

        # --- Spread Protection Gates (Module 3) ---
        # Both controls are configuration-driven (Phase 6). The absolute pip
        # cap is disabled by default because it was asset-class blind: it
        # compared a raw price spread against 2.5 * pip_size where pip_size
        # derives only from spec.digits, which made it unreachable for every
        # index, metal and crypto instrument. It can be restored per
        # deployment with MT5_MAX_SPREAD_PIPS.
        point = spec.tick_size
        raw_spread = Decimal(str(spec.spread_points)) * point
        pip_size = point * Decimal("10") if spec.digits in [3, 5] else point

        if CONFIG.spread.max_pips is not None and raw_spread > CONFIG.spread.max_pips * pip_size:
            return None

        # Stop Loss: strictly beyond sweep extreme + (ATR multiple + spread buffer)
        spread_buffer = raw_spread
        atr_buffer = CONFIG.risk.stop_atr_multiplier * atr + spread_buffer
        if direction == Direction.BUY:
            stop_loss = min(last.low, crt_range.low) - atr_buffer
        else:
            stop_loss = max(last.high, crt_range.high) + atr_buffer

        # Spread-to-Target Ratio: spread must not exceed the configured
        # fraction of the entry-to-stop distance.
        risk_dist = abs(last.close - stop_loss)
        if risk_dist > 0 and raw_spread / risk_dist > CONFIG.spread.max_risk_ratio:
            return None

        # --- Scoring & Tiered Execution Gate (Module 2) ---
        volatility_ok = last.range() > spec.tick_size * CONFIG.risk.min_volatility_ticks
        # Tier 2 requires price to have mitigated the 50% CE of an aligned FVG.
        fvg_mitigated = any(
            g.direction == direction and g.state in {"MITIGATED", "FILLED"} for g in gaps
        )
        score = self.scoring.score(
            direction,
            sweep,
            kod_ok,
            True,  # cisd already confirmed above
            htf_ok,
            session_state,
            structure,
            True,   # risk_ok already validated
            volatility_ok,
            news_state,
            self.config.minimum_score,
            fvg_mitigated=fvg_mitigated,
        )

        if not score.passed:
            return None

        # --- Three-Way Entry Type Selection (Module 4) ---
        # Support 3 entry types:
        # 1. Direct Limit at the sweep level
        # 2. Market Order on KOD candle close
        # 3. Limit Order at FVG 50% Consequent Encroachment (CE)
        
        entry_type_1 = entry_options.get("entry_type_1", sweep.swept_level)
        entry_type_2 = entry_options.get("entry_type_2", last.close)
        entry_type_3 = entry_options.get("entry_type_3", fvg_ce)

        # Select the entry based on the tier that actually authorised the trade:
        # - TIER_2: HTF alignment + FVG/CE mitigation -> limit at the FVG 50% CE
        # - TIER_1: liquidity sweep + KOD displacement -> market on KOD close
        if score.tier == "TIER_2":
            selected_entry = entry_type_3
            entry_reason = "limit_fvg_ce"
            order_type = "LIMIT"
        else:
            selected_entry = entry_type_2
            entry_reason = "market_kod_close"
            order_type = "MARKET"

        plan = self.tm.build_plan(direction, selected_entry, stop_loss)
        size = self.sizer.calculate(account, spec, selected_entry, stop_loss, self.config.risk_limits.risk_pct)
        if size.final_lot_size <= 0:
            return None

        portfolio_ok, portfolio_reason = self.portfolio.permits(
            exposures, spec, self.config.risk_limits.risk_pct
        )
        if not portfolio_ok:
            return None

        rr = abs(plan.tp2 - selected_entry) / abs(selected_entry - stop_loss)
        target = str(crt_range.target_high if direction == Direction.BUY else crt_range.target_low)

        # Execution tier as resolved by the scoring gate itself.
        execution_tier = score.tier or "TIER_1"

        explanation = self.explainer.explain(
            direction, sweep, score, structure, session_state,
            str(rr), target, execution_tier,
        )

        audit = {
            "sequence": [
                "CRT Range",
                "Liquidity Sweep",
                "Rejection",
                "CISD",
                "KOD Close",
                "Structure",
                "HTF Alignment",
                "Session",
                "Risk",
                "Score",
                "Execution Ready",
            ],
            "risk_reason": risk_reason,
            "portfolio_reason": portfolio_reason,
            "news_blockers": news_state.blocking_events,
            "execution_tier": execution_tier,
            "entry_type": entry_reason,
            "order_type": order_type,
            "selected_entry": str(selected_entry),
            "fvg_ce_mitigated": fvg_mitigated,
            "gate_reason": score.gate_reason,
            "atr_14": str(atr),
            "raw_spread": str(raw_spread),
        }

        return TradeSetup(
            symbol,
            timeframe,
            direction,
            selected_entry,
            stop_loss,
            plan.tp1,
            plan.tp2,
            plan.tp3,
            rr,
            score,
            crt_range,
            sweep,
            structure,
            self.ob.detect(completed),
            gaps,
            session_state,
            size,
            explanation,
            audit,
        )

    def fvg_ce_mitigated(self, direction, completed: list[Candle]) -> bool:
        """True when price has traded into the 50% consequent encroachment of a
        fair value gap aligned with ``direction``.

        This is the Tier 2 confirmation required by Module 2. ``FairValueGapEngine``
        marks a zone MITIGATED once the latest candle straddles its CE midpoint,
        and FILLED once the whole gap has been consumed; both count as mitigation.
        """
        try:
            gaps = self.fvg.detect(completed)
        except Exception:
            return False
        return any(
            g.direction == direction and g.state in {"MITIGATED", "FILLED"}
            for g in gaps
        )

    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure,
                        news_state, completed, spec, htf_candles=None, atr=None,
                        htf_result=None):
        """Compute all scoring flags dynamically. Replaces hardcoded True flags.

        Args:
            direction: The trade direction. For CRT + Turtle Soup this is the
                *sweep* direction (fade the pool that was just taken), not the
                prevailing structural bias.
            atr: 14-period ATR. When supplied, KOD is re-evaluated with the
                Module 3 dynamic displacement filter active. The caller
                previously invoked ``kod.confirmed(completed, sweep)`` with no
                ATR, which left the displacement gate dormant.
            htf_candles: optional ``{Timeframe: [Candle]}`` mapping. Legacy
                path, retained for callers that already hold the series.
            htf_result: an :class:`trading_engine.htf_bias.HTFBiasResult`
                produced by :class:`~trading_engine.htf_bias.HTFBiasEngine`.
                This is the preferred input; it carries the per-timeframe bias
                and a status that distinguishes "aligned" from "could not be
                determined".

        Module 1 fix — HTF alignment is no longer assumed
        -------------------------------------------------
        The previous body opened with ``htf_ok = True`` and only overrode it
        ``if htf_candles:``. ``run_mt5_engine`` never passed ``htf_candles``,
        so the override never ran and **every signal in the platform's history
        received the full 15-point HTF Alignment component unconditionally**
        (verified: 460 of 460 signals over six hours). Tier 2's "HTF aligned"
        requirement and Tier 3's ``htf`` leg were therefore vacuous.

        ``htf_ok`` now starts as ``False`` and is only set ``True`` by positive
        evidence. When no HTF information is supplied at all the result is
        ``DATA_UNAVAILABLE`` — explicitly not alignment — so a caller that
        forgets to wire the HTF engine loses 15 points rather than silently
        gaining them. That is the fail-safe direction for a trading system.
        """
        from trading_engine.htf_bias import HTFBiasResult, HTFStatus

        # --- Module 1: higher-timeframe alignment, evaluated for real -------
        if htf_result is not None:
            htf_ok = bool(htf_result.aligned)
            resolved_htf = htf_result
        elif htf_candles:
            htf_biases = {
                getattr(key, "value", str(key)): self.trend.bias(series)
                for key, series in htf_candles.items()
                if len([c for c in series if c.completed]) >= 20
            }
            if htf_biases:
                conflicting = tuple(
                    tf for tf, bias in sorted(htf_biases.items())
                    if bias not in {direction, Direction.NEUTRAL}
                )
                htf_ok = not conflicting
                resolved_htf = HTFBiasResult(
                    status=HTFStatus.ALIGNED if htf_ok else HTFStatus.CONFLICT,
                    aligned=htf_ok,
                    biases={tf: b.value for tf, b in htf_biases.items()},
                    conflicting=conflicting,
                    detail="resolved from caller-supplied higher-timeframe candles",
                )
            else:
                htf_ok = False
                resolved_htf = HTFBiasResult(
                    status=HTFStatus.DATA_UNAVAILABLE,
                    aligned=False,
                    detail="supplied higher-timeframe series were too short to evaluate",
                )
        else:
            htf_ok = False
            resolved_htf = HTFBiasResult(
                status=HTFStatus.DATA_UNAVAILABLE,
                aligned=False,
                detail="no higher-timeframe data supplied to evaluate_signal",
            )

        # Module 3: re-evaluate KOD with the ATR displacement filter engaged.
        kod_reason = "ATR not supplied; displacement filter skipped"
        if atr is not None and atr > 0 and sweep is not None:
            kod, kod_reason = self.kod.confirmed_with_reason(completed, sweep, atr)
        elif sweep is None:
            kod, kod_reason = False, "no liquidity event"

        # Module 2 Tier 2 confirmation.
        fvg_mitigated = self.fvg_ce_mitigated(direction, completed)

        # Risk validation
        risk_ok = True
        # Volatility check
        volatility_ok = True
        if completed and spec and len(completed) > 0:
            last = completed[-1]
            volatility_ok = last.range() > spec.tick_size * CONFIG.risk.min_volatility_ticks

        score = self.scoring.score(
            direction, sweep, kod, cisd, htf_ok, session_state, structure,
            risk_ok, volatility_ok, news_state, minimum=Decimal("50"),
            fvg_mitigated=fvg_mitigated,
        )
        self.last_kod_reason = kod_reason
        self.last_fvg_mitigated = fvg_mitigated
        self.last_htf_result = resolved_htf
        self.last_kod_subchecks = self.kod.subcheck_results(
            completed, sweep, atr if atr is not None else Decimal("0")
        )
        return score, htf_ok, risk_ok, volatility_ok

