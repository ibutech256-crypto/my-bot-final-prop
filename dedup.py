import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition

# Delete duplicate CADCHFm H1 ACTIVE signals
sigs = Signal.objects.filter(status="ACTIVE", symbol__symbol="CADCHFm", strategy_name__contains="H1").order_by("-created_at")
print(f"CADCHFm H1 ACTIVE: {sigs.count()}")
keep = sigs.first()
if keep:
    print(f"  Keeping ID={keep.id}")
for s in sigs[1:]:
    print(f"  Deleting duplicate ID={s.id} created={s.created_at}")
    s.delete()

# Show current ACTIVE signals
print(f"\nTotal ACTIVE signals now: {Signal.objects.filter(status='ACTIVE').count()}")
for s in Signal.objects.filter(status="ACTIVE").order_by("-confidence")[:10]:
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Strat={s.strategy_name}")

# Show OpenPositions
print(f"\nOpenPositions: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} entry={p.entry_price} pnl={p.unrealized_profit}")
