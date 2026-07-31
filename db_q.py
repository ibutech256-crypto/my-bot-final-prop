import sys, os
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from django.db.models import Count

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=4))
print(f"Signals last 4hrs: {r.count()}")
print(f"Unique symbols: {r.values('symbol__symbol').distinct().count()}")
print("By symbol:")
for s in r.values('symbol__symbol').annotate(c=Count('id')).order_by('-c')[:30]:
    print(f"  {s['symbol__symbol']}: {s['c']}")

active = Signal.objects.filter(status__in=['WATCHLIST','ACTIVE_MONITORING','EXECUTION_READY'],is_deleted=False)
print(f"\nActive (non-expired): {active.count()}")
print(f"Active symbols: {active.values('symbol__symbol').distinct().count()}")
for s in active.values('symbol__symbol').annotate(c=Count('id')).order_by('-c')[:20]:
    print(f"  {s['symbol__symbol']}: {s['c']}")

print(f"\nAll statuses:")
for s in Signal.objects.values('status').annotate(c=Count('id')).order_by('-c')[:10]:
    print(f"  {s['status']}: {s['c']}")
