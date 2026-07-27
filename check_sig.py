
import os
import sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
p = "C:" + os.sep + "prop-frim-bot"
sys.path.insert(0, p)
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from django.db.models import Count

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=15))
print("Signals 15min:", r.count())
print("Status dist:")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c"):
    print(f"  {s['status']}: {s['c']}")
print("Top:")
for s in r.order_by("-confidence")[:10]:
    print(f"  {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status}")
print("DONE")
