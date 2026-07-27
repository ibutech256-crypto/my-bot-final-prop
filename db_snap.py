import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition, TradingAccount
from django.db.models import Count

print("=== ACCOUNT ===")
acct = TradingAccount.objects.first()
print(f"Name: {acct.account_name}")
print(f"Balance: ${acct.balance}")
print(f"Equity: ${acct.equity}")

print("\n=== SIGNAL STATUSES ===")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c")[:10]:
    print(f"  {s['status']}: {s['c']}")

print("\n=== ACTIVE SIGNALS ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-confidence")[:5]:
    print(f"  ID={s.id} {s.symbol.symbol:15s} Score={s.confidence} Created={s.created_at.strftime('%m/%d %H:%M')}")

print(f"\n=== POSITIONS ===")
print(f"Open: {OpenPosition.objects.filter(is_deleted=False).count()}")

print("\n=== SCORE DISTRIBUTION (last 24h) ===")
recent = Signal.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24))
tiers = {"50-54": 0, "55-69": 0, "70-84": 0, "85-100": 0}
from decimal import Decimal
for s in recent:
    sc = int(s.confidence)
    if sc >= 85: tiers["85-100"] += 1
    elif sc >= 70: tiers["70-84"] += 1
    elif sc >= 55: tiers["55-69"] += 1
    elif sc >= 50: tiers["50-54"] += 1
for k,v in tiers.items():
    print(f"  {k}: {v}")
print(f"  Total: {sum(tiers.values())}")
