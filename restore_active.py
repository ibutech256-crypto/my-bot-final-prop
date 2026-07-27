import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal

print("=== Fixing ACTIVE signal classification ===")

# Restore signal 107717 to ACTIVE - it has KOD in its confluences
sig = Signal.objects.get(id=107717)
print(f"107717 {sig.symbol.symbol} rationale: {sig.rationale[:150]}")
sig.status = "ACTIVE"
sig.save()
print("  -> Restored to ACTIVE")

# Now re-classify properly
print("\n=== Proper classification ===")
for s in Signal.objects.order_by("-confidence")[:20]:
    has_kod = False
    
    # Check OLD rationale format: "KOD=True" or "KOD=False"
    if "KOD=True" in s.rationale:
        has_kod = True
    elif "KOD=False" in s.rationale:
        has_kod = False
    # Check NEW rationale format: "'KOD'" in the confluences list
    elif "'KOD'" in s.rationale and "KOD=False" not in s.rationale:
        has_kod = True
    else:
        has_kod = False
    
    desired = "ACTIVE" if has_kod else "WATCHLIST"
    
    if s.status != desired:
        print(f"ID={s.id} {s.symbol.symbol} Score={s.confidence} was={s.status} should={desired} KOD={has_kod}")
        s.status = desired
        s.save()

# Final verification
print("\n=== Final ACTIVE signals ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-confidence")[:5]:
    print(f"ID={s.id} {s.symbol.symbol} Score={s.confidence} Rationale={s.rationale[:100]}")

print(f"\nTotal ACTIVE: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Total WATCHLIST: {Signal.objects.filter(status='WATCHLIST').count()}")
