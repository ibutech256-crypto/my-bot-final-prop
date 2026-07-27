"""
Live Telemetry Engine v2.0
Records every stage of the execution pipeline for the real-time console.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
import json


@dataclass
class TelemetryEvent:
    timestamp: str
    symbol: str
    stage: str
    status: str  # PASS, WARNING, FAIL, BLOCK, EXECUTED
    message: str
    details: str = ""
    severity: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL


class TelemetryEngine:
    """Records and broadcasts execution pipeline events."""
    
    def __init__(self):
        self.events: List[TelemetryEvent] = []
        self._max_events = 10000
        self._channel_layer = None
    
    def set_channel_layer(self, channel_layer):
        self._channel_layer = channel_layer
    
    def record(self, symbol: str, stage: str, status: str, message: str, details: str = "", severity: str = "INFO") -> TelemetryEvent:
        ev = TelemetryEvent(
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:11],
            symbol=symbol,
            stage=stage,
            status=status,
            message=message,
            details=details,
            severity=severity
        )
        self.events.append(ev)
        
        # Trim
        if len(self.events) > self._max_events:
            self.events = self.events[-self._max_events:]
        
        # Broadcast via channels
        if self._channel_layer:
            try:
                from asgiref.sync import async_to_sync
                async_to_sync(self._channel_layer.group_send)(
                    "trading",
                    {"type": "event", "payload": {"event": "TELEMETRY", "telemetry": {
                        "timestamp": ev.timestamp,
                        "symbol": ev.symbol,
                        "stage": ev.stage,
                        "status": ev.status,
                        "message": ev.message,
                        "details": ev.details,
                        "severity": ev.severity
                    }}}
                )
            except:
                pass
        
        return ev
    
    def pass_(self, symbol: str, stage: str, message: str, details: str = "") -> TelemetryEvent:
        return self.record(symbol, stage, "PASS", message, details)
    
    def block(self, symbol: str, stage: str, message: str, details: str = "") -> TelemetryEvent:
        return self.record(symbol, stage, "BLOCK", message, details, "WARNING")
    
    def fail(self, symbol: str, stage: str, message: str, details: str = "") -> TelemetryEvent:
        return self.record(symbol, stage, "FAIL", message, details, "ERROR")
    
    def execute(self, symbol: str, stage: str, message: str, details: str = "") -> TelemetryEvent:
        return self.record(symbol, stage, "EXECUTED", message, details, "INFO")
    
    def get_recent(self, limit: int = 100, symbol: Optional[str] = None, status: Optional[str] = None) -> List[TelemetryEvent]:
        filtered = self.events
        if symbol:
            filtered = [e for e in filtered if e.symbol == symbol]
        if status:
            filtered = [e for e in filtered if e.status == status]
        return filtered[-limit:]
    
    def get_summary(self) -> dict:
        total = len(self.events)
        passes = sum(1 for e in self.events if e.status == "PASS")
        blocks = sum(1 for e in self.events if e.status == "BLOCK")
        fails = sum(1 for e in self.events if e.status == "FAIL")
        executed = sum(1 for e in self.events if e.status == "EXECUTED")
        return {
            "total": total,
            "passes": passes,
            "blocks": blocks,
            "fails": fails,
            "executed": executed
        }
