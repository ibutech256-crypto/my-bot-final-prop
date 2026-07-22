from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from trading_engine.types import AccountSnapshot, PositionSize, SymbolSpec
@dataclass(frozen=True)
class RiskLimits:
    risk_pct: Decimal = Decimal("1.00")
    max_daily_loss_pct: Decimal = Decimal("3.00")
    max_weekly_loss_pct: Decimal = Decimal("6.00")
    max_monthly_loss_pct: Decimal = Decimal("10.00")
    max_drawdown_pct: Decimal = Decimal("12.00")
    max_open_trades: int = 5
    max_total_exposure_pct: Decimal = Decimal("25.00")
    emergency_stop: bool = False
@dataclass(frozen=True)
class RiskState:
    daily_loss: Decimal = Decimal("0")
    weekly_loss: Decimal = Decimal("0")
    monthly_loss: Decimal = Decimal("0")
    drawdown_pct: Decimal = Decimal("0")
    open_trades: int = 0
    exposure_pct: Decimal = Decimal("0")
class PositionSizingEngine:
    def calculate(self, account: AccountSnapshot, spec: SymbolSpec, entry: Decimal, stop_loss: Decimal, risk_pct: Decimal, confidence: Decimal = Decimal("1")) -> PositionSize:
        stop_distance=abs(entry-stop_loss)
        if stop_distance <= 0: raise ValueError("Stop loss distance must be positive")
        risk_amount=account.equity*(risk_pct/Decimal("100"))*confidence
        value_per_price_unit = spec.tick_value / spec.tick_size if spec.tick_size else spec.contract_size
        raw = risk_amount / (stop_distance * value_per_price_unit + spec.commission_per_lot + (spec.spread_points * spec.tick_value))
        notional_per_lot = entry * spec.contract_size
        margin_per_lot = spec.margin_initial if spec.margin_initial > 0 else notional_per_lot / max(spec.leverage, Decimal("1"))
        max_by_margin = account.free_margin / margin_per_lot if margin_per_lot > 0 else spec.max_volume
        max_allowed = min(spec.max_volume, max_by_margin)
        rounded = spec.normalize_volume(raw)
        final = spec.normalize_volume(min(rounded, max_allowed)) if max_allowed >= spec.min_volume else Decimal("0")
        return PositionSize(risk_amount, raw, final*margin_per_lot, max_allowed, rounded, final)
class RiskEngine:
    def validate(self, limits: RiskLimits, state: RiskState) -> tuple[bool, str]:
        if limits.emergency_stop: return False, "Emergency stop is active"
        if state.open_trades >= limits.max_open_trades: return False, "Maximum open trades reached"
        if state.daily_loss >= limits.max_daily_loss_pct: return False, "Maximum daily loss reached"
        if state.weekly_loss >= limits.max_weekly_loss_pct: return False, "Maximum weekly loss reached"
        if state.monthly_loss >= limits.max_monthly_loss_pct: return False, "Maximum monthly loss reached"
        if state.drawdown_pct >= limits.max_drawdown_pct: return False, "Maximum drawdown reached"
        if state.exposure_pct >= limits.max_total_exposure_pct: return False, "Maximum portfolio exposure reached"
        return True, "Risk validation passed"
