"""
WebSocket Telemetry Pusher (Module 1)
Pushes tick-by-tick updates through Django Channels / Redis channel layer.
Removes the 5-second HTTP polling dependency.
"""

from __future__ import annotations
import json
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from decimal import Decimal

logger = logging.getLogger("trading")


class TelemetryPusher:
    """Pushes real-time telemetry updates to WebSocket clients via Redis channel layer."""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def push_account_telemetry(self, account_data: dict) -> None:
        """Push account balance/equity/margin updates to trading group."""
        payload = {
            "event": "ACCOUNT_TELEMETRY",
            "account": {
                "account_number": account_data.get("account_number", ""),
                "balance": float(account_data.get("balance", 0)),
                "equity": float(account_data.get("equity", 0)),
                "margin": float(account_data.get("margin", 0)),
            },
        }
        async_to_sync(self.channel_layer.group_send)(
            "trading",
            {"type": "event", "payload": payload},
        )

    def push_positions_sync(self, positions: list[dict]) -> None:
        """Push position updates to trading group."""
        payload = {
            "event": "POSITIONS_SYNC",
            "positions": positions,
        }
        async_to_sync(self.channel_layer.group_send)(
            "trading",
            {"type": "event", "payload": payload},
        )

    def push_new_signal(self, signal_data: dict) -> None:
        """Push new signal notification to trading group."""
        payload = {
            "event": "NEW_SIGNAL",
            "signal": signal_data,
        }
        async_to_sync(self.channel_layer.group_send)(
            "trading",
            {"type": "event", "payload": payload},
        )

    def push_execution_result(self, result_data: dict) -> None:
        """Push order execution result to trading group."""
        payload = {
            "event": "EXECUTION_RESULT",
            "result": result_data,
        }
        async_to_sync(self.channel_layer.group_send)(
            "trading",
            {"type": "event", "payload": payload},
        )

    def push_system_health(self, health_data: dict) -> None:
        """Push system health updates to system_health group."""
        payload = {
            "event": "SYSTEM_HEALTH",
            "health": health_data,
        }
        async_to_sync(self.channel_layer.group_send)(
            "system_health",
            {"type": "event", "payload": payload},
        )

    def push_heartbeat(self) -> None:
        """Push heartbeat to keep connections alive."""
        payload = {
            "event": "HEARTBEAT",
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        async_to_sync(self.channel_layer.group_send)(
            "trading",
            {"type": "event", "payload": payload},
        )
