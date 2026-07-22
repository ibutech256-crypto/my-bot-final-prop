from django.urls import re_path
from backend.apps.trading.consumers import TradingConsumer
from backend.apps.notifications.consumers import NotificationConsumer
from backend.apps.system.consumers import SystemHealthConsumer
websocket_urlpatterns=[re_path(r"ws/trading/$",TradingConsumer.as_asgi()),re_path(r"ws/notifications/$",NotificationConsumer.as_asgi()),re_path(r"ws/system/$",SystemHealthConsumer.as_asgi())]
