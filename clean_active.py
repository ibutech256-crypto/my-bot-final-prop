import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal

print("=== All ACTIVE signals ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-confidence")[:5]:
    print(f"ID={s.id} {s.symbol.symbol} Score={s.confidence}")
    print(f"  Rationale: {s.rationale[:200]}")
    has_kod_true = "KOD=True" in s.rationale
    has_kod_false = "KOD=False" in s.rationale
    print(f"  KOD=True: {has_kod_true}, KOD=False: {has_kod_false}")
    
    # If KOD=False or no KOD mention (new format), move to WATCHLIST
    if not has_kod_true:
        print(f"  -> Moving to WATCHLIST")
        s.status = "WATCHLIST"
        s.save()

print("\n=== After cleanup ===")
for s in Signal.objects.filter(status="ACTIVE")[:5]:
    print(f"ID={s.id} {s.symbol.symbol} Score={s.confidence}")
