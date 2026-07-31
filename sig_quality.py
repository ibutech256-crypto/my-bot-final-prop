"""Check signal quality - SL distance, ATR, price action."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django
django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal
from decimal import Decimal

print("=== SIGNAL QUALITY CHECK (last 12hrs) ===")
r = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(hours=12))

print(f"Total signals: {r.count()}")
print(f"Unique symbols: {r.values('symbol__symbol').distinct().count()}")

# Show detailed quality of recent signals
print("\n=== DETAILED SIGNAL QUALITY ===")
for sig in r.order_by("-created_at")[:15]:
    risk = abs(sig.entry_price - sig.stop_loss) if sig.stop_loss else Decimal("0")
    reward = abs(sig.take_profit - sig.entry_price) if sig.take_profit else Decimal("0")
    rr = reward / risk if risk > 0 else 0
    has_kod = "KOD" in (sig.rationale or "") and "KOD=False" not in (sig.rationale or "")
    has_sweep = "Sweep" in (sig.rationale or "") or "Liquidity" in (sig.rationale or "")
    
    # SL in pips (approximate)
    sl_pips = risk * 10000 if risk < 0.1 else risk * 100  # 4-digit or 2-digit pairs
    
    print(f"  {sig.symbol.symbol:15s} {sig.direction:5s} Score={sig.confidence:>5s} KOD={str(has_kod):5s} Sweep={str(has_sweep):5s}")
    print(f"    Entry={sig.entry_price} SL={sig.stop_loss} TP={sig.take_profit}")
    print(f"    SL_dist={risk:.6f} R:R={rr:.1f} Rationale={sig.rationale[:120]}")

print("\n=== SIGNALS WITH KOD vs WITHOUT ===")
kod_true = 0
kod_false = 0
for sig in r:
    if "KOD=True" in (sig.rationale or ""):
        kod_true += 1
    elif "'KOD'" in (sig.rationale or "") and "KOD=False" not in (sig.rationale or ""):
        kod_true += 1
    else:
        kod_false += 1
print(f"  KOD=True: {kod_true}")
print(f"  KOD=False/No KOD: {kod_false}")

print("\n=== AVERAGE CONFIDENCE ===")
from statistics import mean
scores = [float(s.confidence) for s in r]
if scores:
    print(f"  Mean: {mean(scores):.1f}")
    print(f"  Max: {max(scores)}")
    print(f"  Min: {min(scores)}")

print("\nDONE")
