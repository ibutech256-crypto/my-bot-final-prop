"""Simple position sync from MT5 to DB."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol
from decimal import Decimal
from datetime import datetime, timezone
import MetaTrader5 as mt5

login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)
positions = mt5.positions_get() or []
acct = TradingAccount.objects.first()
print(f"MT5 positions: {len(positions)}")

# Mark all DB positions as deleted first
OpenPosition.objects.filter(account=acct).update(is_deleted=True)

for pos in positions:
    try:
        ticket = str(pos.ticket)
        sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
        direction = "BUY" if pos.type == 0 else "SELL"
        
        obj, created = OpenPosition.objects.update_or_create(
            account=acct,
            broker_ticket=ticket,
            defaults={
                "symbol": sym_obj,
                "direction": direction,
                "volume": Decimal(str(pos.volume)),
                "entry_price": Decimal(str(pos.price_open)),
                "current_price": Decimal(str(pos.price_current)),
                "stop_loss": Decimal(str(pos.sl)) if pos.sl else None,
                "take_profit": Decimal(str(pos.tp)) if pos.tp else None,
                "unrealized_profit": Decimal(str(pos.profit)),
                "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                "is_deleted": False,
            }
        )
        print(f"  {'Created' if created else 'Updated'}: {pos.symbol} ticket={ticket} pnl={pos.profit:.2f}")
    except Exception as e:
        print(f"  Error syncing {pos.symbol}: {e}")

mt5.shutdown()
print(f"\nDB positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} pnl={p.unrealized_profit}")
