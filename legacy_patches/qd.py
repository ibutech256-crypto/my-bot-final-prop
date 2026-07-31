import os, sys, time
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order, BrokerSetting
from decimal import Decimal

bs = BrokerSetting.objects.first()
print(f"enable_autotrading: {bs.enable_autotrading}")

# Recent signals
recent = Signal.objects.filter(created_at__gte=timezone.now()-timezone.timedelta(hours=1)) if 'timezone' in dir() else Signal.objects.all()[:0]

from django.utils import timezone
from datetime import timedelta
recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=1))
print(f"Signals 1hr: {recent.count()}")

# Check for any KOD=True
kod_true = [s for s in recent if "KOD=True" in (s.rationale or "")]
print(f"KOD=True: {len(kod_true)}")

# Check for any with score.passed eligibility
# score.passed means kod=True + (tier1 or tier2)
# We check the rationale
high = recent.filter(confidence__gte=Decimal("70"))
print(f"Score>=70: {high.count()}")

for s in high.order_by("-confidence")[:5]:
    has_kod = "KOD=True" in (s.rationale or "")
    print(f"  {s.symbol.symbol} Score={s.confidence} Status={s.status} KOD={has_kod}")

# Check positions
print(f"\nOpen Positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
print(f"Orders: {Order.objects.count()}")

# Check what statuses exist  
from django.db.models import Count
print("\nStatus distribution:")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c")[:10]:
    print(f"  {s['status']}: {s['c']}")
