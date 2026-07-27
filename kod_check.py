import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from decimal import Decimal

recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=2))
print(f"Signals last 2hr: {recent.count()}")
high = recent.filter(confidence__gte=Decimal("75")).count()
print(f"Score>=75: {high}")
print(f"Score>=70: {recent.filter(confidence__gte=Decimal("70")).count()}")
print(f"Score 55-69: {recent.filter(confidence__gte=Decimal("55"),confidence__lt=Decimal("70")).count()}")

# Check KOD mentions
kod_signals = [s for s in recent if "KOD=True" in (s.rationale or "")]
print(f"KOD=True signals: {len(kod_signals)}")

# Show the highest score signal details
highest = recent.order_by("-confidence").first()
if highest:
    print(f"\n=== HIGHEST SCORE SIGNAL ===")
    print(f"ID={highest.id} {highest.symbol.symbol} Score={highest.confidence} Status={highest.status}")
    print(f"Rationale: {highest.rationale[:200]}")
    print(f"Created: {highest.created_at}")

# Show one score=70 signal
seventy = recent.filter(confidence=Decimal("70")).order_by("-created_at").first()
if seventy:
    print(f"\n=== SCORE=70 SIGNAL ===")
    print(f"ID={seventy.id} {seventy.symbol.symbol} Score={seventy.confidence} Status={seventy.status}")
    print(f"Rationale: {seventy.rationale[:200]}")
