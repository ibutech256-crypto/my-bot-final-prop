import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from backend.apps.trading.models import Signal

# Find the highest confidence signal
sig = Signal.objects.filter(confidence__gte=76).order_by("-created_at").first()
if sig:
    print(f"SIGNAL_ID: {sig.id}")
    print(f"SYMBOL: {sig.symbol.symbol}")
    print(f"DIRECTION: {sig.direction}")
    print(f"SCORE: {sig.confidence}")
    print(f"STATUS: {sig.status}")
    print(f"STRATEGY: {sig.strategy_name}")
    print(f"ENTRY: {sig.entry_price}")
    print(f"SL: {sig.stop_loss}")
    print(f"TP: {sig.take_profit}")
    print(f"RATIONALE: {sig.rationale}")
    print(f"CREATED: {sig.created_at}")
    print(f"SYMBOL_TRADEABLE: {sig.symbol.is_tradeable}")
else:
    print("NO_HIGH_SIGNAL")

# Also check the score distribution
print("\n=== SCORE DISTRIBUTION ===")
from django.db.models import Count
from decimal import Decimal
high = Signal.objects.filter(confidence__gte=Decimal("70"), created_at__gte=django.utils.timezone.now() - django.utils.timezone.timedelta(hours=1)).count()
mid = Signal.objects.filter(confidence__gte=Decimal("55"), confidence__lt=Decimal("70"), created_at__gte=django.utils.timezone.now() - django.utils.timezone.timedelta(hours=1)).count()
print(f"Score>=70 (last 1hr): {high}")
print(f"Score 55-69 (last 1hr): {mid}")

# Count KOD=True vs False in recent signals
with_kod = Signal.objects.filter(rationale__icontains="KOD=True", created_at__gte=django.utils.timezone.now() - django.utils.timezone.timedelta(hours=1)).count()
without_kod = Signal.objects.filter(rationale__icontains="KOD=False", created_at__gte=django.utils.timezone.now() - django.utils.timezone.timedelta(hours=1)).count()
print(f"With KOD (1hr): {with_kod}")
print(f"Without KOD (1hr): {without_kod}")
