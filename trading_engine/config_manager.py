"""
Configuration Manager v2.0
Centralized, persistent configuration for all trading parameters.
All thresholds are editable from the Settings page - no hardcoded values.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Dict, Any, Optional
import json, os

CONFIG_PATH = "C:/prop-frim-bot/config/trading_config.json"


@dataclass
class TradingConfig:
    # Risk Management
    risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 15.0
    max_position_size: float = 0.10
    max_simultaneous_trades: int = 10
    max_correlated_positions: int = 3
    max_leverage: int = 100
    
    # Execution
    default_slippage_points: int = 20
    order_timeout_seconds: int = 240
    min_stop_distance_points: int = 15
    
    # Protection
    max_spread_pips_forex: float = 2.5
    max_spread_pips_gold: float = 5.0
    max_spread_pct_entry: float = 15.0
    news_blackout_minutes: int = 15
    min_volatility_atr_multiple: float = 1.8
    
    # Scoring
    tier1_score_min: float = 55.0
    tier2_score_min: float = 70.0
    high_conviction_score: float = 85.0
    morning_guard_score: float = 70.0
    
    # Position Management
    tp1_pct: float = 50.0
    tp2_pct: float = 75.0
    tp3_pct: float = 100.0
    breakeven_after_tp1: bool = True
    trailing_stop_enabled: bool = True
    trailing_activation_rr: float = 1.0
    
    # Sessions
    session_asian_enabled: bool = True
    session_london_enabled: bool = True
    session_ny_enabled: bool = True
    session_asian_start: str = "02:00"
    session_asian_end: str = "10:00"
    session_london_start: str = "10:00"
    session_london_end: str = "20:00"
    session_ny_start: str = "15:00"
    session_ny_end: str = "23:00"
    
    # Alerts
    alert_on_trade: bool = True
    alert_on_close: bool = True
    alert_on_daily_loss: bool = True
    alert_on_margin_warning: bool = True
    alert_on_connection_loss: bool = True
    
    def save(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls) -> TradingConfig:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except:
                pass
        config = cls()
        config.save()
        return config
    
    def update(self, updates: Dict[str, Any]) -> TradingConfig:
        for k, v in updates.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.save()
        return self

CONFIG = TradingConfig.load()
