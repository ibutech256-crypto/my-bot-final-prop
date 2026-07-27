
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from decimal import Decimal

recent = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=1)).order_by("-created_at")
print(f"Signals last 1hr: {recent.count()}")
print()
print("=== MOST RECENT SIGNAL (first in DB) ===")
s = recent.first()
if s:
    print(f"ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Strategy={s.strategy_name}")
    print(f"Created: {s.created_at}")
    print(f"Rationale: {s.rationale[:200]}")

print()
print("=== HIGHEST SCORE IN LAST 1HR ===")
high = recent.order_by("-confidence").first()
if high:
    print(f"ID={high.id} {high.symbol.symbol} {high.direction} Score={high.confidence} Status={high.status}")
    print(f"Created: {high.created_at}")
    print(f"Rationale: {high.rationale[:200]}")

print()
print("=== ALL SCORES IN LAST 1HR (dedup) ===")
scores = {}
for s in recent:
    score = int(s.confidence)
    if score not in scores:
        scores[score] = 0
    scores[score] += 1
for score in sorted(scores.keys(), reverse=True):
    print(f"  Score={score}: {scores[score]} signals")
