import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from decimal import Decimal

# ===== 1. How many signals have KOD=True EVER? =====
print("=== KOD=True SIGNALS (ALL TIME) ===")
all_signals = Signal.objects.count()
print(f"Total signals ever generated: {all_signals}")

# Count KOD=True in OLD rationale format (KOD=True)
kod_old = Signal.objects.filter(rationale__icontains="KOD=True").count()
print(f"KOD=True (old format 'KOD=True'): {kod_old}")

# Count KOD=True in NEW rationale format ('KOD' in confluences list)
kod_new = 0
for s in Signal.objects.iterator():
    r = s.rationale or ""
    if "'KOD'" in r and "KOD=False" not in r:
        kod_new += 1
# This is slow, let me just sample
print(f"(scanning for new format...)")

# Better approach: check the last 1000 signals
print("\n=== Scanning last 1000 signals ===")
kod_true_signals = []
for s in Signal.objects.order_by("-created_at")[:1000]:
    r = s.rationale or ""
    is_kod = False
    if "KOD=True" in r:
        is_kod = True
    elif "'KOD'" in r and "KOD=False" not in r:
        is_kod = True
    if is_kod:
        kod_true_signals.append(s)

print(f"KOD=True in last 1000 signals: {len(kod_true_signals)}")
for s in kod_true_signals:
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Status={s.status} Created={s.created_at}")

# ===== 2. Recent signals breakdown =====
print("\n=== RECENT SIGNALS (last 2 hours) ===")
recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=2))
print(f"Total in 2hr: {recent.count()}")

# Score distribution
score_bands = {
    "85+": recent.filter(confidence__gte=Decimal("85")).count(),
    "70-84": recent.filter(confidence__gte=Decimal("70"), confidence__lt=Decimal("85")).count(),
    "55-69": recent.filter(confidence__gte=Decimal("55"), confidence__lt=Decimal("70")).count(),
}
print("Score distribution:")
for k, v in score_bands.items():
    print(f"  {k}: {v}")

# Check for KOD in recent
kod_in_recent = 0
for s in recent:
    r = s.rationale or ""
    if "'KOD'" in r and "KOD=False" not in r:
        kod_in_recent += 1
    elif "KOD=True" in r:
        kod_in_recent += 1
print(f"KOD=True in last 2hr: {kod_in_recent}")

# ===== 3. Show ALL unique symbols with ACTIVE signals =====
print("\n=== ALL UNIQUE SYMBOLS WITH SIGNALS (last 24hr) ===")
last_24h = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24))
symbols = last_24h.values_list("symbol__symbol", flat=True).distinct()
print(f"Unique symbols in 24hr: {len(symbols)}")
print(f"Sample: {list(symbols)[:15]}")

# ===== 4. Check the CRT/KOD detection logic =====
print("\n=== KOD DETECTION IN CODE ===")
with open(r"C:\prop-frim-bot\trading_engine\orchestrator.py", "r") as f:
    orch = f.read()

# Find KOD detection
for i, line in enumerate(orch.split('\n')):
    if "kod" in line.lower() and ("detect" in line.lower() or "confirmed" in line.lower()):
        print(f"  Line {i+1}: {line.strip()[:150]}")
        if i < 20:
            for j in range(i+1, min(i+10, len(orch.split('\n')))):
                next_line = orch.split('\n')[j]
                if next_line.strip():
                    print(f"    {next_line.strip()[:150]}")

# ===== 5. Check how often scoring gets kod=True =====
print("\n=== SCORING ENGINE ===")
with open(r"C:\prop-frim-bot\trading_engine\scoring.py", "r") as f:
    scoring = f.read()
print(scoring)

print("\nDONE")
