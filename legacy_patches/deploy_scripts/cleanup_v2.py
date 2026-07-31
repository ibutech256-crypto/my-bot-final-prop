import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django
django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order, TradingSymbol, BrokerSetting

cnt = Signal.objects.filter(status__in=["CLOSED_TP","CLOSED_SL","WATCHLIST"]).delete()
print(f"Cleared closed/watchlist signals: {cnt}")

OpenPosition.objects.filter(is_deleted=False).update(is_deleted=True)
print("Cleared DB positions")

Order.objects.all().delete()
print("Cleared orders")

exotics = ["USDMADm","XZNUSDm","USDISKm","USDSARm","USDAEDm","USDKWDm","USDINRm",
           "USDCNHm","USDCZKm","USDDKKm","USDHKDm","USDHUFm","USDPLNm","USDSEKm",
           "USDSGDm","USDTHBm","USDTWDm","CHFHUFm","CHFMXNm","CHFPLNm","CHFSGDm",
           "CHFTRYm","EURCZKm","EURHKDm","EURHUFm","EURMXNm","EURNOKm","EURPLNm",
           "EURSEKm","EURTRYm","EURZARm","GBPHUFm","GBPMXNm","GBPNOKm","GBPSEKm",
           "GBPTRYm","GBPZARm","NZDHUFm","NZDTRYm","NZDZARm"]
for s in exotics:
    TradingSymbol.objects.filter(symbol=s).update(is_tradeable=False)
print(f"Excluded {len(exotics)} exotic symbols")

bs = BrokerSetting.objects.first()
if bs:
    bs.enable_autotrading = True
    bs.save()
    print(f"Auto-trading enabled: {bs.enable_autotrading}")
print("Cleanup complete!")
