"""Final cleanup: remove duplicate CADCHFm and ensure clean state."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition, TradingAccount, TradingSymbol
from decimal import Decimal

# 1. Remove hard duplicates - same symbol+direction+strategy, keep only newest
print("=== Cleaning duplicates ===")
from django.db.models import Count

dupes = Signal.objects.values("symbol_id", "direction", "strategy_name").annotate(
    cnt=Count("id")
).filter(cnt__gt=1)

nil = 0
for d in dupes:
    sigs = Signal.objects.filter(
        symbol_id=d["symbol_id"], 
        direction=d["direction"], 
        strategy_name=d["strategy_name"]
    ).order_by("-created_at")
    
    keep = sigs.first()
    for s in sigs[1:]:
        # Keep the one with ACTIVE status if possible
        if s.status == "ACTIVE" and keep.status != "ACTIVE":
            keep, s = s, keep
        s.delete()
        nil += 1
        
print(f"Removed {nil} duplicate signals")

# 2. Show final state
print(f"\nFinal ACTIVE signals: {Signal.objects.filter(status='ACTIVE').count()}")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Strat={s.strategy_name} Created={s.created_at}")

print(f"\nOpen positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} pnl={p.unrealized_profit}")

print("\nDONE")
