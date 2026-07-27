"""
Institutional Risk Engine v2.0
Real-time risk monitoring, protection, and emergency controls.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, List, Callable
import json


@dataclass
class RiskState:
    balance: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    floating_pl: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    free_margin: Decimal = Decimal("0")
    margin_level: Decimal = Decimal("0")
    open_positions: int = 0
    daily_pnl: Decimal = Decimal("0")
    daily_loss_pct: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    leverage_used: Decimal = Decimal("0")
    exposure_by_currency: Dict[str, Decimal] = field(default_factory=dict)
    exposure_by_asset: Dict[str, Decimal] = field(default_factory=dict)
    correlation_risk: Decimal = Decimal("0")
    risk_score: int = 0


@dataclass
class RiskConfig:
    max_daily_loss_pct: Decimal = Decimal("5.0")
    max_drawdown_pct: Decimal = Decimal("15.0")
    max_position_size: Decimal = Decimal("0.10")
    max_correlated_positions: int = 3
    max_simultaneous_trades: int = 10
    max_leverage: Decimal = Decimal("50")
    daily_loss_lock_enabled: bool = True
    drawdown_lock_enabled: bool = True
    weekend_protection: bool = True
    news_protection: bool = True
    spread_protection: bool = True


class RiskEngine:
    """Monitors and enforces risk limits with emergency controls."""
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.state = RiskState()
        self._frozen = False
        self._freeze_reason = ""
        self._daily_loss_updated = datetime.now(timezone.utc).date()
    
    def update(self, state: RiskState) -> None:
        self.state = state
        date_today = datetime.now(timezone.utc).date()
        if date_today != self._daily_loss_updated:
            self.state.daily_pnl = Decimal("0")
            self.state.daily_loss_pct = Decimal("0")
            self._daily_loss_updated = date_today
        
        # Auto-protection checks
        if self.config.daily_loss_lock_enabled and self.state.daily_loss_pct >= self.config.max_daily_loss_pct:
            self.freeze("Daily loss limit reached")
        if self.config.drawdown_lock_enabled and self.state.max_drawdown >= self.config.max_drawdown_pct:
            self.freeze("Maximum drawdown reached")
    
    def freeze(self, reason: str) -> None:
        self._frozen = True
        self._freeze_reason = reason
    
    def unfreeze(self) -> None:
        self._frozen = False
        self._freeze_reason = ""
    
    @property
    def is_frozen(self) -> bool:
        return self._frozen
    
    @property
    def freeze_reason(self) -> str:
        return self._freeze_reason
    
    def can_trade(self, symbol: str, volume: Decimal, direction: str) -> tuple[bool, str]:
        if self._frozen:
            return False, f"Trading frozen: {self._freeze_reason}"
        if self.state.open_positions >= self.config.max_simultaneous_trades:
            return False, f"Max simultaneous trades reached ({self.config.max_simultaneous_trades})"
        if volume > self.config.max_position_size:
            return False, f"Volume {volume} exceeds max position size {self.config.max_position_size}"
        return True, "OK"
    
    def get_risk_score(self) -> int:
        score = 0
        if self.state.margin_level > 0 and self.state.margin_level < Decimal("200"):
            score += 25
        if self.state.daily_loss_pct > Decimal("3"):
            score += 25
        if self.state.max_drawdown > Decimal("10"):
            score += 25
        if self.state.open_positions > 5:
            score += 15
        if self._frozen:
            score += 10
        self.state.risk_score = min(score, 100)
        return self.state.risk_score
    
    def to_dict(self) -> dict:
        return {
            "balance": float(self.state.balance),
            "equity": float(self.state.equity),
            "floating_pl": float(self.state.floating_pl),
            "margin": float(self.state.margin),
            "free_margin": float(self.state.free_margin),
            "margin_level": float(self.state.margin_level),
            "open_positions": self.state.open_positions,
            "daily_pnl": float(self.state.daily_pnl),
            "daily_loss_pct": float(self.state.daily_loss_pct),
            "max_drawdown": float(self.state.max_drawdown),
            "leverage_used": float(self.state.leverage_used),
            "risk_score": self.get_risk_score(),
            "is_frozen": self._frozen,
            "freeze_reason": self._freeze_reason,
            "max_daily_loss_pct": float(self.config.max_daily_loss_pct),
            "max_drawdown_pct": float(self.config.max_drawdown_pct),
            "max_position_size": float(self.config.max_position_size),
            "max_simultaneous_trades": self.config.max_simultaneous_trades,
        }
