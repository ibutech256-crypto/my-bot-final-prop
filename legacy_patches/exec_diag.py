import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, "C:/prop-frim-bot")
sys.path.insert(0, "C:/prop-frim-bot/backend")

import django
django.setup()
from backend.apps.trading.models import Signal

a = Signal.objects.filter(status="ACTIVE")
print(f"Active: {a.count()}")
print(f"Score>=70: {a.filter(confidence__gte=70).count()}")
print(f"Score>=55: {a.filter(confidence__gte=55).count()}")

# Show highest scores
print("\nTop 5 ACTIVE signals:")
for s in a.order_by("-confidence")[:5]:
    print(f"  {s.symbol} conf={s.confidence}")

# Check signals >=70 specifically
high = a.filter(confidence__gte=70)
print(f"\nSignals >=70 confidence: {high.count()}")
if high.count() > 0:
    print("  QUALIFY for Tier 2 execution!")
    for s in high[:3]:
        print(f"    {s.symbol} {s.direction} conf={s.confidence}")

