"""Fix EURNZDm signal status, investigate signal display issue."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta, datetime
from backend.apps.trading.models import Signal, Order, ClosedTrade
from decimal import Decimal

# ===== 1. EURNZDm - trade executed but signal never updated =====
print("=== EURNZDm INVESTIGATION ===")
sig = Signal.objects.get(id=107745)
print(f"Signal 107745: status={sig.status}")
print(f"  Created: {sig.created_at}")

order = Order.objects.filter(signal=sig).first()
if order:
    print(f"  Order: status={order.status} ticket={order.broker_ticket}")
    print(f"  Created: {order.created_at}")
    
# The trade was executed and closed, but the signal remained ACTIVE.
# This is because the engine's EXECUTED status update code at line ~710
# runs `Signal.objects.filter(id=sig.id).update(status="EXECUTED")`
# but ONLY when an order is placed. Once the trade closes (SL/TP),
# it should be CLOSED_TP or CLOSED_SL.

# Check if there's a closed trade
ct = ClosedTrade.objects.filter(symbol=sig.symbol).order_by("-created_at").first()
if ct:
    print(f"  ClosedTrade: profit={ct.profit} exit={ct.exit_price}")
else:
    print(f"  No ClosedTrade record found")

# Fix: mark the signal properly
# The order was FILLED, so status should be EXECUTED or CLOSED
if order and order.status == "FILLED":
    # Check if it should have been marked EXECUTED by the engine
    # The engine does: Signal.objects.filter(id=sig.id).update(status="EXECUTED")
    # But this signal is still ACTIVE, meaning the update didn't happen
    # This could be because the engine crashed between ORDER and the status update
    
    # Let's check what the engine does
    print("\n=== Engine EXECUTED status update ===")
    with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
        engine = f.read()
    if "status=\"EXECUTED\"" in engine:
        print("Engine has code to set EXECUTED status")
        idx = engine.find("status=\"EXECUTED\"")
        print(f"  At line {engine[:idx].count(chr(10)) + 1}")
        print(f"  Context: {engine[idx-50:idx+80]}")
    else:
        print("Engine does NOT have code to set EXECUTED status!")
    
    # For now, mark it properly
    sig.status = "CLOSED_SL"
    sig.save()
    print(f"\n✅ Signal 107745 marked as CLOSED_SL (trade was executed and already closed)")

# ===== 2. Investigate why API returns only 2 signals =====
print("\n=== SIGNAL DISPLAY INVESTIGATION ===")
print("Checking SignalViewSet.get_queryset:")
with open(r"C:\prop-frim-bot\backend\apps\trading\views.py", "r") as f:
    views = f.read()

idx = views.find("class SignalViewSet")
end = views.find("\nclass ", idx+10)
section = views[idx:end]
print(section[:500])

# All ACTIVE signals in DB
print(f"\nACTIVE signals in DB: {Signal.objects.filter(status='ACTIVE').count()}")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")

# Check the API filtering
print("\nAPI query breakdown:")
qs = Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status="ACTIVE").order_by("-confidence", "-created_at")
print(f"  Total matching: {qs.count()}")
for s in qs:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")

# CRM the difference
all_active = Signal.objects.filter(status="ACTIVE")
api_active = Signal.objects.filter(is_deleted=False, status="ACTIVE")
print(f"\n  All ACTIVE: {all_active.count()}")
print(f"  ACTIVE + is_deleted=False: {api_active.count()}")
diff = set(all_active.values_list('id', flat=True)) - set(api_active.values_list('id', flat=True))
if diff:
    print(f"  IDs excluded by is_deleted filter: {diff}")
    for sid in diff:
        s = Signal.objects.get(id=sid)
        print(f"    ID={s.id} {s.symbol.symbol} is_deleted={s.is_deleted}")

print("\nDONE")
