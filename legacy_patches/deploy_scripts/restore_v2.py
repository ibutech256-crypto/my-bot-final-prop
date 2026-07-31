import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal

print("=== Correcting ACTIVE/WATCHLIST classification ===")

# Only touch signals that are currently ACTIVE or WATCHLIST
affected = Signal.objects.filter(status__in=["ACTIVE", "WATCHLIST"])
print(f"Total ACTIVE or WATCHLIST: {affected.count()}")

for s in affected:
    # Determine KOD presence
    has_kod = False
    r = s.rationale or ""
    
    if "KOD=True" in r:
        has_kod = True
    elif "'KOD'" in r and "KOD=False" not in r:
        # New format: confluences list includes 'KOD'
        has_kod = True
    else:
        has_kod = False
    
    desired = "ACTIVE" if has_kod else "WATCHLIST"
    
    if s.status != desired:
        print(f"  FIX: ID={s.id} {s.symbol.symbol} Score={s.confidence} {s.status} -> {desired} (KOD={has_kod})")
        s.status = desired
        s.save()

# Verify
print(f"\nFinal ACTIVE: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Final WATCHLIST: {Signal.objects.filter(status='WATCHLIST').count()}")

# Show the ACTIVE ones
print("\nACTIVE signals (execution-eligible):")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at")[:10]:
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} Created={s.created_at.strftime('%H:%M:%S')}")

print("\nDONE")
