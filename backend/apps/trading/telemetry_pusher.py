"""
WebSocket Telemetry Pusher (v2.0.1)
Pushes tick-by-tick updates through Django Channels / Redis channel layer.
Provides both sync and async methods to avoid blocking the event loop.
"""

from __future__ import annotations
import json
import logging
import asyncio
from datetime import datetime, timezone
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer

logger = logging.getLogger("trading")


class TelemetryPusher:
    """Pushes real-time telemetry to WebSocket clients via Redis channel layer.
    
    Provides sync (for Celery tasks) and async (for Daphne event loop) methods.
    """

    def __init__(self):
        self._channel_layer = None

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._channel_layer = get_channel_layer()
        return self._channel_layer

    # --- Sync Methods (for Celery workers, background threads) ---

    def push_account_telemetry(self, account_data: dict) -> None:
        """Push account balance/equity/margin updates (sync)."""
        try:
            payload = self._build_payload("ACCOUNT_TELEMETRY", {
                "account_number": account_data.get("account_number", ""),
                "balance": float(account_data.get("balance", 0)),
                "equity": float(account_data.get("equity", 0)),
                "margin": float(account_data.get("margin", 0)),
            })
            async_to_sync(self.channel_layer.group_send)(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push account telemetry: {e}")

    def push_positions_sync(self, positions: list[dict]) -> None:
        """Push position updates (sync)."""
        try:
            payload = self._build_payload("POSITIONS_SYNC", {"positions": positions})
            async_to_sync(self.channel_layer.group_send)(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push positions sync: {e}")

    def push_new_signal(self, signal_data: dict) -> None:
        """Push new signal notification (sync)."""
        try:
            payload = self._build_payload("NEW_SIGNAL", {"signal": signal_data})
            async_to_sync(self.channel_layer.group_send)(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push signal: {e}")

    def push_execution_result(self, result_data: dict) -> None:
        """Push order execution result (sync)."""
        try:
            payload = self._build_payload("EXECUTION_RESULT", {"result": result_data})
            async_to_sync(self.channel_layer.group_send)(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push execution result: {e}")

    def push_system_health(self, health_data: dict) -> None:
        """Push system health updates (sync)."""
        try:
            payload = self._build_payload("SYSTEM_HEALTH", {"health": health_data})
            async_to_sync(self.channel_layer.group_send)(
                "system_health", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push system health: {e}")

    def push_heartbeat(self) -> None:
        """Push heartbeat to keep connections alive (sync)."""
        try:
            payload = self._build_payload("HEARTBEAT", {
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            async_to_sync(self.channel_layer.group_send)(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Failed to push heartbeat: {e}")

    # --- Async Methods (for use in async views / consumers directly) ---

    async def a_push_account_telemetry(self, account_data: dict) -> None:
        """Push account telemetry (async, non-blocking)."""
        try:
            payload = self._build_payload("ACCOUNT_TELEMETRY", {
                "account_number": account_data.get("account_number", ""),
                "balance": float(account_data.get("balance", 0)),
                "equity": float(account_data.get("equity", 0)),
                "margin": float(account_data.get("margin", 0)),
            })
            await self.channel_layer.group_send(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Async telemetry push failed: {e}")

    async def a_push_positions_sync(self, positions: list[dict]) -> None:
        """Push positions sync (async)."""
        try:
            payload = self._build_payload("POSITIONS_SYNC", {"positions": positions})
            await self.channel_layer.group_send(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Async positions push failed: {e}")

    async def a_push_new_signal(self, signal_data: dict) -> None:
        """Push new signal (async)."""
        try:
            payload = self._build_payload("NEW_SIGNAL", {"signal": signal_data})
            await self.channel_layer.group_send(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Async signal push failed: {e}")

    async def a_push_execution_result(self, result_data: dict) -> None:
        """Push execution result (async)."""
        try:
            payload = self._build_payload("EXECUTION_RESULT", {"result": result_data})
            await self.channel_layer.group_send(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Async execution push failed: {e}")

    async def a_push_heartbeat(self) -> None:
        """Push heartbeat (async)."""
        try:
            payload = self._build_payload("HEARTBEAT", {
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            await self.channel_layer.group_send(
                "trading", {"type": "event", "payload": payload}
            )
        except Exception as e:
            logger.warning(f"Async heartbeat push failed: {e}")

    # --- Helpers ---

    @staticmethod
    def _build_payload(event: str, data: dict) -> dict:
        return {
            "event": event,
            **data,
        }
