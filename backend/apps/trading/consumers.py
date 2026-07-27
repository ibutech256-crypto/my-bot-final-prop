import json
import asyncio
import logging
from datetime import datetime, timezone
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("trading")


class TradingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer with 20-second ping/pong heartbeat (v2.0.1).
    
    Sends a HEARTBEAT event every 20 seconds to prevent proxy/firewall
    idle timeouts and allow the frontend to detect stale connections.
    """

    async def connect(self):
        await self.channel_layer.group_add("trading", self.channel_name)
        await self.accept()
        # Start background heartbeat loop
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"WS trading connected: {self.channel_name}")

    async def disconnect(self, code):
        await self.channel_layer.group_discard("trading", self.channel_name)
        if hasattr(self, 'heartbeat_task'):
            self.heartbeat_task.cancel()
        logger.info(f"WS trading disconnected ({code}): {self.channel_name}")

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages. Respond to PING with PONG."""
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get("event") == "PING":
                    await self.send(text_data=json.dumps({
                        "event": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
            except json.JSONDecodeError:
                pass

    async def event(self, event):
        """Receive channel-layer event and push to WebSocket."""
        await self.send(text_data=json.dumps(event.get("payload", {})))

    async def _heartbeat_loop(self):
        """Send a heartbeat ping every 20 seconds to prevent idle disconnects."""
        try:
            while True:
                await asyncio.sleep(20)
                await self.send(text_data=json.dumps({
                    "event": "HEARTBEAT",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Trading heartbeat error: {e}")


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer with 20-second heartbeat."""

    async def connect(self):
        await self.channel_layer.group_add("notifications", self.channel_name)
        await self.accept()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"WS notif connected: {self.channel_name}")

    async def disconnect(self, code):
        await self.channel_layer.group_discard("notifications", self.channel_name)
        if hasattr(self, 'heartbeat_task'):
            self.heartbeat_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get("event") == "PING":
                    await self.send(text_data=json.dumps({
                        "event": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
            except json.JSONDecodeError:
                pass

    async def event(self, event):
        await self.send(text_data=json.dumps(event.get("payload", {})))

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(20)
                await self.send(text_data=json.dumps({
                    "event": "HEARTBEAT",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Notif heartbeat error: {e}")


class SystemHealthConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer with 20-second heartbeat."""

    async def connect(self):
        await self.channel_layer.group_add("system_health", self.channel_name)
        await self.accept()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"WS syshealth connected: {self.channel_name}")

    async def disconnect(self, code):
        await self.channel_layer.group_discard("system_health", self.channel_name)
        if hasattr(self, 'heartbeat_task'):
            self.heartbeat_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get("event") == "PING":
                    await self.send(text_data=json.dumps({
                        "event": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
            except json.JSONDecodeError:
                pass

    async def event(self, event):
        await self.send(text_data=json.dumps(event.get("payload", {})))

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(20)
                await self.send(text_data=json.dumps({
                    "event": "HEARTBEAT",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"SysHealth heartbeat error: {e}")
