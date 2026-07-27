"""
Market Intelligence Engine v2.0
Market overview, currency strength, sentiment, session tracking.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


@dataclass
class MarketSession:
    name: str
    start_utc: int
    end_utc: int
    is_active: bool = False
    time_until: str = ""


class MarketIntel:
    """Provides market overview data: sessions, sentiment, strength."""
    
    SESSIONS = [
        ("Sydney", 22, 7),    # 22:00-07:00 UTC
        ("Tokyo/Asia", 0, 9),  # 00:00-09:00 UTC
        ("London", 8, 17),    # 08:00-17:00 UTC
        ("New York", 13, 22), # 13:00-22:00 UTC
        ("Overlap (London+NY)", 13, 17),
    ]
    
    @classmethod
    def get_sessions(cls, dt_utc: Optional[datetime] = None) -> List[MarketSession]:
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        hour = dt_utc.hour + dt_utc.minute / 60.0
        sessions = []
        for name, start, end in cls.SESSIONS:
            active = (start <= hour < end) if end > start else (hour >= start or hour < end)
            sessions.append(MarketSession(name, start, end, active))
        return sessions
    
    @classmethod
    def current_session(cls, dt_utc: Optional[datetime] = None) -> str:
        for s in cls.get_sessions(dt_utc):
            if s.is_active:
                return s.name
        return "Sydney/Off-Hours"
    
    @classmethod
    def currency_strength(cls, forex_prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate relative currency strength from forex pairs."""
        currencies = {}
        for pair, price in forex_prices.items():
            if len(pair) == 6:
                base, quote = pair[:3], pair[3:6]
                for c, is_base in [(base, True), (quote, False)]:
                    if c not in currencies:
                        currencies[c] = {"sum": 0.0, "count": 0}
                    currencies[c]["sum"] += (1.0 / price if is_base else price)
                    currencies[c]["count"] += 1
        return {c: round(d["sum"] / d["count"], 4) for c, d in currencies.items()} if currencies else {}


class AIDecisionEngine:
    """Explainable AI decision layer for trade confidence."""
    
    @staticmethod
    def score_confidence(
        regime_score: float,    # -100 to 100
        trend_strength: float,  # 0-100
        volatility: float,      # 0-100
        liquidity: float,       # 0-100
        structure_score: float, # 0-100
        session_quality: float, # 0-100
        news_impact: float,     # 0-100 (lower is better)
        historical_rr: float    # average R multiple
    ) -> tuple[float, Dict[str, float]]:
        """Calculate AI confidence score with contributing factors."""
        components = {
            "market_regime": max(-20, min(20, regime_score * 0.2)),
            "trend_strength": trend_strength * 0.15,
            "volatility": volatility * 0.10,
            "liquidity": liquidity * 0.10,
            "structure": structure_score * 0.15,
            "session": session_quality * 0.10,
            "news_safety": (100 - news_impact) * 0.10,
            "historical_edge": min(10, historical_rr * 5),
        }
        total = sum(components.values())
        return round(min(99, max(1, total)), 1), components
