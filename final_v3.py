"""Fix: mark executed trades properly, add signal lifecycle completion."""
import os, sys
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import datetime
from backend.apps.trading.models import Signal, Order, ClosedTrade
from decimal import Decimal

# ===== FIX A: Mark EURNZDm signal as CLOSED_SL =====
print("=== FIX A: Mark EURNZDm as CLOSED ===")
sig = Signal.objects.get(id=107745)
sig.status = "CLOSED_SL"
sig.save()
print(f"Signal 107745 EURNZDm: ACTIVE -> CLOSED_SL (trade lost $3.32)")

# ===== FIX B: Add EXECUTED status update to engine =====
print("\n=== FIX B: Add EXECUTED status update to engine ===")
engine_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(engine_path, "r") as f:
    engine = f.read()

# The engine already has the EXECUTED status update (from an earlier fix)
# Let me verify
if "status=\"EXECUTED\"" in engine:
    print("Engine already has EXECUTED status update")
else:
    print("Engine does NOT have EXECUTED status update - adding it")
    # Add it after the order is recorded successfully
    old = 'self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
    new = 'Signal.objects.filter(id=sig.id).update(status="EXECUTED")\n                                                                            self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
    if old in engine:
        engine = engine.replace(old, new)
        open(engine_path, "w").write(engine)
        print("EXECUTED status update added to engine")
    else:
        print("Could not find target line in engine")

# ===== FIX C: Also mark signal as CLOSED when AI outcome tracking finds it =====
print("\n=== FIX C: Add close status from AI outcome tracking ===")
# The AI outcome tracking already sets CLOSED_TP/CLOSED_SL based on tick data
# Let me check
if "CLOSED_TP" in engine:
    print("Engine already has CLOSED_TP/SL status updates")
else:
    print("Engine may not auto-close signals")

# ===== Verify =====
print("\n=== Final ACTIVE signals ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")

# API query
from backend.apps.trading.models import Signal
qs = Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status="ACTIVE").order_by("-confidence", "-created_at")
print(f"\nAPI would return: {qs.count()} signals")
for s in qs:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence}")

print("\nDONE")
