import os, sys
os.chdir("C:/prop-frim-bot")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, "C:/prop-frim-bot/backend")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order
from django.utils import timezone
from decimal import Decimal

# Clean up stale signals > 3 hours old (they've been through enough scan cycles)
old = timezone.now() - timezone.timedelta(hours=3)
stale = Signal.objects.filter(status="ACTIVE", created_at__lt=old).count()
expired = Signal.objects.filter(status="ACTIVE", created_at__lt=old).update(status="CLOSED_SL")
print(f"Expired {expired} stale ACTIVE signals (>3h old)")

# Check what's executing now  
print(f"\n=== EXECUTION STATUS ===")
print(f"ACTIVE signals remaining: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Open Positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
print(f"Orders placed: {Order.objects.count()}")
print(f"Total signals: {Signal.objects.count()}")

# Show signals ordered by confidence (what the API now returns)
print("\n=== TOP SIGNALS READY FOR EXECUTION ===")
active = Signal.objects.filter(status="ACTIVE").order_by("-confidence")[:10]
for s in active:
    print(f"  {s.symbol} {s.direction} conf={s.confidence} created={s.created_at.strftime('%H:%M')}")

# Show the last log execution activity
log = "logs/TradingMT5Engine.log"
with open(log, "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 20000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]

print("\n=== LAST EXECUTION EVENTS ===")
for t in ["TRADE EXECUTED", "EXECUTING CRT", "BLOCKED", "REJECTED"]:
    matches = [l for l in lines if t in l]
    if matches:
        for m in matches[-3:]:
            print(f"  {m[:150]}")

print(f"\nLoop stops in sample: {len([l for l in lines if 'loop stopping' in l])}")
print("Engine: STABLE" if len([l for l in lines if 'loop stopping' in l]) <= 1 else "Engine: CRASH-LOOPING")

