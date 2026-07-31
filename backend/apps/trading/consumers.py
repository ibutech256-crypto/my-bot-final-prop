"""WebSocket consumers for the live trading telemetry stream.

v2.0.2 fix
----------
The previous revision called ``asyncio.create_task(self._ping_loop())`` inside
``connect()`` but ``_ping_loop`` was never defined on any of these classes.
Every websocket handshake therefore raised

    AttributeError: 'TradingConsumer' object has no attribute '_ping_loop'

inside ``websocket_connect``, so Daphne accepted the socket and then instantly
tore it down (WSCONNECT immediately followed by WSDISCONNECT).  The browser saw
three failed sockets in a row and fell back to the 5-second HTTP polling path,
which is why the dashboard badge read "Polling (HTTP 5s)".

``TradingConsumer`` also carried a duplicated ``connect()`` stub that shadowed
the real one and left the class docstring stranded in the middle of the body.

This revision keeps a single keepalive task per consumer, defines it properly,
and cancels it cleanly on disconnect.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("trading")

# Seconds between server-initiated HEARTBEAT frames. Kept below the common
# 30s idle timeout used by proxies/NAT so the socket is never reaped.
HEARTBEAT_INTERVAL = 15


class _HeartbeatConsumer(AsyncWebsocketConsumer):
    """Shared group-subscribe + heartbeat behaviour."""

    group_name: str = ""
    log_label: str = "ws"

    async def connect(self):
        self.heartbeat_task = None
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WS %s connected: %s", self.log_label, self.channel_name)

    async def disconnect(self, code):
        task = getattr(self, "heartbeat_task", None)
        if task is not None:
            task.cancel()
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("WS %s disconnected (%s): %s", self.log_label, code, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Reply to a client PING with a PONG so the browser can measure RTT."""
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if data.get("event") == "PING":
            await self.send(text_data=json.dumps({
                "event": "PONG",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

    async def event(self, event):
        """Fan out a channel-layer event to this socket."""
        await self.send(text_data=json.dumps(event.get("payload", {})))

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.send(text_data=json.dumps({
                    "event": "HEARTBEAT",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # socket already gone, nothing to recover
            logger.warning("%s heartbeat stopped: %s", self.log_label, exc)


class TradingConsumer(_HeartbeatConsumer):
    """Live account / position / signal / telemetry stream (group: ``trading``)."""

    group_name = "trading"
    log_label = "trading"


class NotificationConsumer(_HeartbeatConsumer):
    group_name = "notifications"
    log_label = "notif"


class SystemHealthConsumer(_HeartbeatConsumer):
    group_name = "system_health"
    log_label = "syshealth"
