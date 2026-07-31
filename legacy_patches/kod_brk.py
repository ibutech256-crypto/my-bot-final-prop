import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal, TradingSymbol
from collections import Counter

# Scan for KOD=True signals
kod_signals = []
total_scanned = 0
for s in Signal.objects.iterator():
    total_scanned += 1
    r = s.rationale or ""
    is_kod = False
    if "KOD=True" in r:
        is_kod = True
    elif "'KOD'" in r and "KOD=False" not in r:
        is_kod = True
    if is_kod:
        kod_signals.append((s.symbol.symbol, s.direction, str(s.created_at)[:10], s.status, s.confidence))

print(f"Total signals scanned: {total_scanned}")
print(f"Total KOD=True: {len(kod_signals)}")
print(f"KOD rate: {len(kod_signals)/total_scanned*100:.1f}%")

print(f"\n=== By symbol (top 20) ===")
symbols = Counter(s[0] for s in kod_signals)
for sym, cnt in symbols.most_common(20):
    print(f"  {sym}: {cnt}")

print(f"\n=== KOD=True by date ===")
dates = Counter(s[2] for s in kod_signals)
for date, cnt in sorted(dates.items()):
    print(f"  {date}: {cnt}")

print(f"\n=== KOD=True today {len([s for s in kod_signals if '2026-07-27' in s[2]])} ===")
for s in kod_signals:
    if "2026-07-27" in s[2]:
        print(f"  {s[0]:15s} {s[1]:5s} Score={s[4]:>6s} Status={s[3]:20s}")

# Show what's tradeable vs not
print(f"\n=== Tradeable status of KOD symbols ===")
for sym, _ in symbols.most_common():
    try:
        ts = TradingSymbol.objects.get(symbol=sym)
        print(f"  {sym}: tradeable={ts.is_tradeable}")
    except:
        print(f"  {sym}: symbol not in DB")
