from django.urls import re_path

from backend.apps.notifications.consumers import NotificationConsumer
from backend.apps.system.consumers import SystemHealthConsumer
from backend.apps.trading.consumers import TradingConsumer

websocket_urlpatterns = [
    # Canonical trading telemetry stream.
    re_path(r"^ws/trading/?$", TradingConsumer.as_asgi()),
    # Short alias: ws://<host>:8000/ws  -> same trading stream.
    re_path(r"^ws/?$", TradingConsumer.as_asgi()),
    re_path(r"^ws/notifications/?$", NotificationConsumer.as_asgi()),
    re_path(r"^ws/system/?$", SystemHealthConsumer.as_asgi()),
]
