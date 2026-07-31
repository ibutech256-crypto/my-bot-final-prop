"""Diagnose dashboard sync issues."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import OpenPosition, Signal, TradingAccount, Order
from decimal import Decimal

# 1. Check what the signals API returns
print("=== SIGNALS API: What it returns ===")
recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=6))
print(f"Signals last 6hrs: {recent.count()}")
print(f"ACTIVE: {recent.filter(status='ACTIVE').count()}")
print(f"WATCHLIST: {recent.filter(status='WATCHLIST').count()}")

# Show all recent signals
for s in recent.order_by("-created_at")[:10]:
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Created={s.created_at.strftime('%H:%M:%S')}")

# 2. Check the signals API view
print("\n=== VIEWS: SignalViewSet ===")
import importlib
try:
    views = importlib.import_module("backend.apps.trading.views")
    if hasattr(views, 'SignalViewSet'):
        from rest_framework import viewsets
        qs = views.SignalViewSet.queryset
        if callable(qs):
            pass
        print(f"SignalViewSet queryset: {qs}")
        # Check serializer
        if hasattr(views.SignalViewSet, 'serializer_class'):
            print(f"Serializer: {views.SignalViewSet.serializer_class}")
except Exception as e:
    print(f"Error reading views: {e}")

# 3. Check positions API view
print("\n=== POSITIONS API ===")
try:
    if hasattr(views, 'OpenPositionViewSet'):
        print(f"OpenPositionViewSet exists")
        print(f"  queryset: {views.OpenPositionViewSet.queryset}")
    else:
        print("No OpenPositionViewSet - check URLs")
except Exception as e:
    print(f"Error: {e}")

# 4. Check if there's a signal filter limiting to 3
print("\n=== SIGNAL FILTER CHECK ===")
if recent.count() > 3:
    print(f"There are {recent.count()} recent signals but dashboard shows 3")
    print("The API likely has a filter/limit of 3")
    
# Check the views for pagination/filtering
try:
    import inspect
    print(f"\n=== SignalViewSet methods ===")
    svs = views.SignalViewSet
    for name, method in inspect.getmembers(svs):
        if not name.startswith('__'):
            print(f"  {name}: {type(method)}")
except Exception as e:
    print(f"Error: {e}")

# 5. Check URL routing
print("\n=== URL PATTERNS ===")
from backend.config import urls as config_urls
for url in config_urls.urlpatterns:
    print(f"  {url.pattern}")
