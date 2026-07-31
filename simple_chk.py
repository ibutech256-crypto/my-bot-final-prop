"""Ultra-simple DB check."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition

print("COUNT:", Signal.objects.count())
print("OPEN POSITIONS:", OpenPosition.objects.filter(is_deleted=False).count())

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=12))
print("RECENT:", r.count())
print("SYMBOLS:", list(r.values_list('symbol__symbol', flat=True).distinct()[:20]))

for s in r.order_by("-confidence")[:5]:
    print(f"ID={s.id} {s.symbol.symbol} Score={s.confidence} Status={s.status}")
    print(f"  R={s.rationale[:150]}")
