import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from decimal import Decimal

recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=2))
print("Signals last 2hr:", recent.count())
high = recent.filter(confidence__gte=Decimal("75")).count()
print("Score>=75:", high)
print("Score>=70:", recent.filter(confidence__gte=Decimal("70")).count())
kod_signals = [s for s in recent if "KOD=True" in (s.rationale or "")]
print("KOD=True signals:", len(kod_signals))
highest = recent.order_by("-confidence").first()
if highest:
    print("\nHIGHEST:", highest.id, highest.symbol.symbol, highest.confidence, highest.status)
    print("  Rationale:", highest.rationale[:200])
