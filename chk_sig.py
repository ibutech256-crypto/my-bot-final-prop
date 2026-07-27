import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal

# Check all ACTIVE signals
print("=== ACTIVE Signals in DB ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Created={s.created_at}")

# Check total counts
print(f"\nTotal ALL: {Signal.objects.count()}")
print(f"Total ACTIVE: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Total WATCHLIST: {Signal.objects.filter(status='WATCHLIST').count()}")

# Check top 5 by created_at
print("\nMost recent 5 signals:")
for s in Signal.objects.order_by("-created_at")[:5]:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Status={s.status} Created={s.created_at}")
