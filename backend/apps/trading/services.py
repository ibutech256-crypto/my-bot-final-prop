from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable
from django.contrib.auth import get_user_model
from django.db import transaction
from trading_engine.news_filter import EconomicEvent
from trading_engine.orchestrator import EngineConfig, RomeoTPTOrchestrator
from trading_engine.portfolio import Exposure
from trading_engine.risk import RiskLimits, RiskState
from trading_engine.types import AccountSnapshot, Candle, SymbolSpec, Timeframe, TradeSetup
from backend.apps.trading.models import Signal, SignalDirection, TradingSymbol

class InstitutionalTradingService:
    """Django application-layer adapter for the deterministic institutional engine."""
    def __init__(self, minimum_score: Decimal = Decimal("75"), risk_limits: RiskLimits | None = None):
        self.engine = RomeoTPTOrchestrator(EngineConfig(minimum_score=minimum_score, risk_limits=risk_limits or RiskLimits()))
    def evaluate(self, symbol: str, timeframe: Timeframe, candles: list[Candle], htf_candles: dict[Timeframe, list[Candle]], account: AccountSnapshot, spec: SymbolSpec, risk_state: RiskState, exposures: list[Exposure], events: list[EconomicEvent], now: datetime | None = None) -> TradeSetup | None:
        return self.engine.evaluate(symbol, timeframe, candles, htf_candles, account, spec, risk_state, exposures, events, now or datetime.now(timezone.utc))
    @transaction.atomic
    def publish_signal(self, setup: TradeSetup, author_username: str) -> Signal:
        User = get_user_model()
        author = User.objects.select_for_update().get(username=author_username)
        symbol, _ = TradingSymbol.objects.get_or_create(symbol=setup.symbol, defaults={"asset_class": "CRYPTO" if "BTC" in setup.symbol.upper() or "ETH" in setup.symbol.upper() else "FOREX"})
        return Signal.objects.create(
            symbol=symbol,
            author=author,
            strategy_name="Romeo TPT Institutional",
            direction=SignalDirection.BUY if setup.direction.value == "BUY" else SignalDirection.SELL,
            entry_price=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit_2,
            confidence=setup.score.total,
            rationale=setup.explanation,
        )
