
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
import sys
sys.path.insert(0, ".")
import django
django.setup()
from backend.apps.trading.models import Signal
from django.db.models import Count
print("Signals:", Signal.objects.count())
statuses = Signal.objects.values("status").annotate(c=Count("id")).order_by("-c")
for s in statuses:
    print(f"  {s['status']}: {s['c']}")
print("Recent:")
for s in Signal.objects.order_by("-created_at")[:5]:
    print(f"  {s.symbol.symbol} Score={s.confidence} Status={s.status} Created={s.created_at}")
