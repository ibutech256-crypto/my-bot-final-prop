import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order
from backend.apps.trading.models import TradingAccount, BrokerProfile

# Close ALL existing ACTIVE signals
count = Signal.objects.filter(status="ACTIVE").count()
print(f"ACTIVE signals to close: {count}")
Signal.objects.filter(status="ACTIVE").update(status="WATCHLIST")
print("All ACTIVE signals moved to WATCHLIST")

# Clear stale OpenPositions
stale = OpenPosition.objects.filter(is_deleted=False)
print(f"Open positions in DB: {stale.count()}")
for p in stale:
    p.is_deleted = True
    p.save()
    print(f"  Deleted position: {p.symbol.symbol} ticket={p.broker_ticket}")

# Check broker settings
from backend.apps.trading.models import BrokerSetting
bs = BrokerSetting.objects.first()
if bs:
    bs.enable_autotrading = True
    bs.save()
    print(f"BrokerSetting: auto_trading={bs.enable_autotrading}")
else:
    print("No BrokerSetting found!")

print("Cleanup complete!")