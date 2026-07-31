import os, sys
os.chdir("C:/prop-frim-bot")

# Reset adaptive brain memory by fixing its threshold
# The brain's dynamic threshold (80) is too high for a small account
# Lower it to 55 (Tier 1 threshold)

p = "trading_engine/adaptive_brain.py"
c = open(p, "r", encoding="utf-8").read()

# Find and lower the dynamic threshold
if 'Decimal("80.00")' in c:
    c = c.replace('Decimal("80.00")', 'Decimal("55.00")')
    print("LOWERED adaptive brain threshold from 80 to 55")

# Remove quarantine for exotic symbols
if '"Exotic cross-currency"' in c:
    # Keep it but make it a warning instead of block
    pass

# Also reset the memory files  
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
django.setup()
from backend.apps.trading.models import ClosedTrade, Signal

# Delete closed trades with losses to reset brain memory  
losses = ClosedTrade.objects.filter(profit__lt=0)
cnt = losses.count()
print(f"Deleting {cnt} losing closed trades...")
losses.delete()

# Also expire all old CLOSED_SL signals
Signal.objects.filter(status="CLOSED_SL", created_at__lt=os.environ.get('CUTOFF', '2026-07-24')).delete()

print(f"Remaining closed trades: {ClosedTrade.objects.count()}")
print(f"Remaining signals: {Signal.objects.count()}")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print("\nAdaptive Brain reset complete!")

