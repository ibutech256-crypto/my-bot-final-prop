"""Full DB report - no escaping issues."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition
from django.db.models import Count
from decimal import Decimal

print("=== ALL STATUSES ===")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c")[:15]:
    print(f"  {s['status']}: {s['c']}")

print("\n=== SIGNALS LAST 12 HOURS ===")
r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=12))
print(f"  Total: {r.count()}")
print(f"  Unique symbols: {r.values('symbol__symbol').distinct().count()}")

print("\n  By symbol:")
for s in r.values("symbol__symbol").annotate(c=Count("id")).order_by("-c")[:25]:
    print(f"    {s['symbol__symbol']}: {s['c']}")

print("\n  Score distribution:")
buckets = {"55-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0, "<55": 0}
for sig in r:
    sc = int(sig.confidence)
    if sc >= 90: buckets["90-100"] += 1
    elif sc >= 80: buckets["80-89"] += 1
    elif sc >= 70: buckets["70-79"] += 1
    elif sc >= 60: buckets["60-69"] += 1
    elif sc >= 55: buckets["55-59"] += 1
    else: buckets["<55"] += 1
for k, v in buckets.items():
    if v > 0:
        print(f"    {k}: {v}")

print("\n  Top 10 highest scoring:")
for sig in r.order_by("-confidence")[:10]:
    has_kod = "KOD" in (sig.rationale or "") and "KOD=False" not in (sig.rationale or "")
    print(f"    {sig.symbol.symbol:15s} Score={sig.confidence:>5s} KOD={str(has_kod):5s} Status={sig.status:20s} Created={sig.created_at.strftime('%H:%M')}")

print("\n  Most recent signals:")
for sig in r.order_by("-created_at")[:10]:
    print(f"    {sig.symbol.symbol:15s} Score={sig.confidence:>5s} Status={sig.status:20s} Created={sig.created_at.strftime('%H:%M')}")

print("\n=== OPEN POSITIONS ===")
print(f"  Count: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"    {p.symbol.symbol} {p.direction} vol={p.volume} entry={p.entry_price} pnl={p.unrealized_profit}")

print("\n=== ENGINE SYMBOL CHECK ===")
print(f"  FOCUS_SYMBOLS in engine?")
found_focus = False
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    for line in f:
        if "FOCUS_SYMBOLS" in line or "ACTIVE_SYMBOLS" in line:
            print(f"    {line.strip()[:80]}")
            found_focus = True
            break
if not found_focus:
    print("    Neither FOCUS_SYMBOLS nor ACTIVE_SYMBOLS found at top level")
    # Check what variable the scanning loop uses
    with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
        for line in f:
            if "in ACTIVE_SYMBOLS" in line or "in FOCUS_SYMBOLS" in line or "visible_symbols.append" in line:
                print(f"    Scan loop: {line.strip()[:80]}")

print("\nDONE")
