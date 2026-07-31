import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition, Order
from decimal import Decimal
from django.db.models import Count

# Check ACTIVE signals - are they old?
print("=== ACTIVE SIGNALS ===")
actives = Signal.objects.filter(status="ACTIVE")
print(f"Total ACTIVE: {actives.count()}")

# Age distribution
recent_actives = actives.filter(created_at__gte=timezone.now()-timedelta(hours=1))
old_actives = actives.filter(created_at__lt=timezone.now()-timedelta(hours=1))
print(f"ACTIVE (last 1hr): {recent_actives.count()}")
print(f"ACTIVE (older): {old_actives.count()}")

# Show some old ones
for s in old_actives.order_by("-confidence")[:5]:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")
    print(f"  Rationale: {s.rationale[:150]}")

# Show recent ones
print("\n=== RECENT ACTIVE SIGNALS ===")
for s in recent_actives.order_by("-created_at")[:5]:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")
    print(f"  Rationale: {s.rationale[:150]}")

# Check if any WATCHLIST signals have KOD=True
print("\n=== WATCHLIST SIGNALS CHECK ===")
watchlist = Signal.objects.filter(status="WATCHLIST")
recent_wl = watchlist.filter(created_at__gte=timezone.now()-timedelta(hours=1))
print(f"WATCHLIST (last 1hr): {recent_wl.count()}")

# Check rationality of each high-score WATCHLIST
for s in recent_wl.filter(confidence__gte=Decimal("70")).order_by("-confidence")[:5]:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Status={s.status}")
    print(f"  Rationale: {s.rationale[:200]}")

# Show status counts for ALL signals
print("\n=== ALL STATUSES ===")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c"):
    print(f"  {s['status']}: {s['c']}")
