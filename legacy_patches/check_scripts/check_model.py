import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from backend.apps.trading.models import Signal, SignalStatus, BrokerSetting

print("=== SignalStatus choices ===")
for choice in SignalStatus.choices:
    print(f"  {choice[0]}: {choice[1]}")

print("\n=== BrokerSetting ===")
bs = BrokerSetting.objects.first()
print(f"  enable_autotrading: {bs.enable_autotrading}")
print(f"  order_deviation_points: {bs.order_deviation_points}")
print(f"  max_retry_count: {bs.max_retry_count}")

# Also check max_position_size and other config
from backend.apps.trading.models import TradingAccount
print("\n=== TradingAccount ===")
acct = TradingAccount.objects.first()
print(f"  balance: {acct.balance}")
print(f"  equity: {acct.equity}")
print(f"  account_name: {acct.account_name}")

# Check for any EXECUTED / EXECUTION_READY / ACTIVE_MONITORING statuses in DB
from django.db.models import Count
print("\n=== All statuses in DB ===")
for s in Signal.objects.values("status").annotate(c=Count("id")).order_by("-c"):
    print(f"  {s['status']}: {s['c']}")
