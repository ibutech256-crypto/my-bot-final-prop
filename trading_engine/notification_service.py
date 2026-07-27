"""
Institutional Notification Service v2.0
Centralized alerts via Telegram, Dashboard, and WebSocket.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Callable
import logging
import json

logger = logging.getLogger("notifications")


@dataclass
class Alert:
    type: str  # TRADE, CLOSE, WARNING, ERROR, HEARTBEAT, DAILY_REPORT
    severity: str  # INFO, WARNING, CRITICAL
    title: str
    message: str
    symbol: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")


class NotificationService:
    def __init__(self):
        self._handlers: List[Callable] = []
        self._recent_alerts: List[Alert] = []
        self._max_alerts = 200
    
    def add_handler(self, handler: Callable):
        self._handlers.append(handler)
    
    def send(self, alert: Alert):
        self._recent_alerts.append(alert)
        if len(self._recent_alerts) > self._max_alerts:
            self._recent_alerts = self._recent_alerts[-self._max_alerts:]
        
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Notification handler error: {e}")
    
    def trade_executed(self, symbol: str, direction: str, volume: float, price: float):
        self.send(Alert("TRADE", "INFO", f"Trade Executed", f"{direction} {volume} {symbol} @ {price}", symbol))
    
    def trade_closed(self, symbol: str, profit: float, reason: str):
        sev = "INFO" if profit >= 0 else "WARNING"
        self.send(Alert("CLOSE", sev, f"Trade Closed ({reason})", f"{symbol}: ${profit:.2f}", symbol))
    
    def warning(self, title: str, message: str):
        self.send(Alert("WARNING", "WARNING", title, message))
    
    def error(self, title: str, message: str):
        self.send(Alert("ERROR", "CRITICAL", title, message))
    
    def get_recent(self, limit: int = 50, alert_type: Optional[str] = None) -> List[Alert]:
        if alert_type:
            return [a for a in self._recent_alerts if a.type == alert_type][-limit:]
        return self._recent_alerts[-limit:]

NOTIF_SVC = NotificationService()
