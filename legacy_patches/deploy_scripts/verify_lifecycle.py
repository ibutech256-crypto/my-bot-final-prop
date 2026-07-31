"""Verify lifecycle states in DB."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from django.db.models import Count

# Check signal status distribution
statuses = Signal.objects.values("status").annotate(count=Count("id")).order_by("-count")
print("=== Signal Status Distribution ===")
for s in statuses:
    print(f"  {s['status']}: {s['count']}")

# Check recent signals (last 5 min)
recent = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=5))
print(f"\n=== Recent Signals (last 5 min): {recent.count()} ===")
for s in recent.order_by("-created_at")[:10]:
    print(f"  {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Strategy={s.strategy_name}")
    if hasattr(s, 'lifecycle_events'):
        events = s.lifecycle_events.all()[:3]
        for e in events:
            print(f"    Lifecycle: {e.previous_status} -> {e.new_status}: {e.reason[:50] if e.reason else ''}")

# Check executed trades
executed = Signal.objects.filter(status="EXECUTED")
print(f"\n=== Executed Trades: {executed.count()} ===")

# Check blocked signals
blocked = Signal.objects.filter(status__startswith="BLOCKED")
print(f"\n=== Blocked Signals: {blocked.count()} ===")
for s in blocked.order_by("-created_at")[:5]:
    print(f"  {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status}")
