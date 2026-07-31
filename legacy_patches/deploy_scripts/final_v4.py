import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from backend.apps.trading.models import Signal, Order, ClosedTrade

# FIX A: Mark EURNZDm as CLOSED_SL
print("=== FIX A: EURNZDm CLOSED ===")
sig = Signal.objects.get(id=107745)
sig.status = "CLOSED_SL"
sig.save()
print(f"Signal 107745 EURNZDm marked CLOSED_SL")

# FIX B: Check engine for EXECUTED status update
print("\n=== FIX B: Engine EXECUTED status ===")
engine_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(engine_path, "r") as f:
    engine = f.read()
if "status=\"EXECUTED\"" in engine:
    print("Engine has EXECUTED status update")
else:
    print("Engine DOES NOT have EXECUTED status - adding it")
    old = 'self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
    new = 'Signal.objects.filter(id=sig.id).update(status="EXECUTED")\n                                                                            self.stdout.write(f"TRADE EXECUTED & RECORDED: {sym} {sig.direction} @ {filled_price} (Ticket: #{ticket_str})")'
    if old in engine:
        engine = engine.replace(old, new)
        open(engine_path, "w").write(engine)
        print("Added EXECUTED status update")
    else:
        print("Pattern not found in engine!")
        # Search for what's there
        idx = engine.find("TRADE EXECUTED & RECORDED")
        if idx >= 0:
            print(f"Found at {idx}: {engine[idx:idx+120]}")

# Final state
print("\n=== Final ACTIVE signals ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at}")

qs = Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status="ACTIVE").order_by("-confidence", "-created_at")
print(f"\nAPI would return: {qs.count()} signals")

print("\nDONE")
