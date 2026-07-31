"""Check recent signals in DB to verify KOD capping and lifecycle."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from django.db.models import Count

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=10))
print(f"Signals in last 10min: {r.count()}")

# Check status distribution
print("\n=== Status Distribution ===")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c"):
    print(f"  {s['status']}: {s['c']}")

# Show top scoring recent signals
print("\n=== Top Recent Signals ===")
for s in r.order_by("-confidence")[:15]:
    has_kod = "KOD=True" in (s.rationale or "") or "KOD: True" in (s.rationale or "")
    kod_str = "KOD=True" if has_kod else "KOD=False"
    print(f"  {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} {kod_str}")

# Check if any signals have ACTIVE_MONITORING or EXECUTION_READY
new_statuses = Signal.objects.filter(status__in=["ACTIVE_MONITORING", "EXECUTION_READY"]).count()
print(f"\nNew lifecycle statuses (ACTIVE_MONITORING/EXECUTION_READY): {new_statuses}")

# Show any signals with these new statuses
for s in Signal.objects.filter(status__in=["ACTIVE_MONITORING", "EXECUTION_READY"])[:5]:
    print(f"  {s.symbol.symbol} Score={s.confidence} Status={s.status}")
