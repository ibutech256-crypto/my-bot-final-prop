
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
import sys
sys.path.insert(0, ".")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from django.db.models import Count

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=30))
print(f"Signals in 30min: {r.count()}")
print("Status distribution:")
for s in r.values("status").annotate(c=Count("id")).order_by("-c"):
    print(f"  {s['status']}: {s['c']}")
print("Recent 5:")
for s in r.order_by("-created_at")[:5]:
    print(f"  {s.symbol.symbol} Score={s.confidence} Status={s.status} Created={s.created_at}")
