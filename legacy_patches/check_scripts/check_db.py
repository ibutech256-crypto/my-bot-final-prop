
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal

recent = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=10))
print(f"Signals in last 10min: {recent.count()}")
for s in recent.order_by("-confidence")[:15]:
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Created={s.created_at.strftime('%H:%M:%S')}")
