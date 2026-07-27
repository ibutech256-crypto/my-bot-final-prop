import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, "C:/prop-frim-bot")
sys.path.insert(0, "C:/prop-frim-bot/backend")
import django; django.setup()
from backend.apps.trading.models import Signal, Order, OpenPosition
from django.db.models import Count

print("=== SIGNAL STATUS ===")
for r in Signal.objects.values("status").annotate(c=Count("id")):
    print(f"  {r['status']}: {r['c']}")

# Check latest signals  
print("\nLatest signals:")
for s in Signal.objects.all().order_by("-created_at")[:5]:
    print(f"  {s.symbol} conf={s.confidence} status={s.status} created={s.created_at.strftime('%H:%M')}")

# Check signal API output
print("\n=== API signals check ===")
from backend.apps.trading.views import SignalViewSet
qs = SignalViewSet().get_queryset()
print(f"API returns: {qs.count()} signals")
if qs.count() > 0:
    for s in qs[:3]:
        print(f"  {s.symbol} conf={s.confidence} status={s.status}")

# Check orders  
print(f"\nOrders: {Order.objects.count()}")
print(f"Open Positions: {OpenPosition.objects.filter(is_deleted=False).count()}")

# Check last engine error
import os as _os
log = "C:/prop-frim-bot/logs/TradingMT5Engine.log"
if _os.path.exists(log):
    with open(log, "rb") as f:
        f.seek(max(0, _os.fstat(f.fileno()).st_size - 5000))
        data = f.read().decode("latin-1")
    lines = [l for l in data.split("\n") if l.strip()]
    for term in ["loop stopping", "Error inside", "TRADE EXECUTED", "BLOCKED", "REJECTED"]:
        matches = [l for l in lines if term in l]
        if matches:
            print(f"\n{term}: {len(matches)}")
            for m in matches[-2:]:
                print(f"  {m[:150]}")

