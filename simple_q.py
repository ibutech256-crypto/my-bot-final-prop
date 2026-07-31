import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal

r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=12))
print(f"Total: {r.count()}")
print(f"Symbols: {r.values('symbol__symbol').distinct().count()}")

for s in r.order_by("-created_at")[:15]:
    print(f"  {s.symbol.symbol:15s} Score={s.confidence:>5s} SL={str(s.stop_loss)[:12]:12s} Entry={str(s.entry_price)[:12]:12s}")
    print(f"    Rationale: {s.rationale[:150]}")
