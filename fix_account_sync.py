"""Fix account balance sync and ensure WebSocket connects."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from backend.apps.trading.models import TradingAccount, OpenPosition, Signal
from decimal import Decimal
import MetaTrader5 as mt5

# 1. Sync account from MT5
print("=== Syncing account from MT5 ===")
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)
info = mt5.account_info()
if info:
    print(f"MT5: balance={info.balance} equity={info.equity} login={info.login}")
    acct = TradingAccount.objects.first()
    if acct:
        acct.balance = Decimal(str(info.balance))
        acct.equity = Decimal(str(info.equity))
        acct.margin = Decimal(str(info.margin))
        acct.save()
        print(f"DB: balance={acct.balance} equity={acct.equity}")
else:
    print(f"MT5 login failed: {mt5.last_error()}")

# 2. Sync positions
positions = mt5.positions_get() or []
print(f"\nMT5 positions: {len(positions)}")
mt5_tickets = set(str(p.ticket) for p in positions)

# Mark stale DB positions as deleted
acct = TradingAccount.objects.first()
OpenPosition.objects.filter(account=acct).update(is_deleted=True)

# Create current positions
for pos in positions:
    ticket = str(pos.ticket)
    sym_obj, _ = __import__('backend.apps.trading.models', fromlist=['TradingSymbol']).TradingSymbol.objects.get_or_create(symbol=pos.symbol)
    direction = "BUY" if pos.type == 0 else "SELL"
    
    OpenPosition.objects.update_or_create(
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
            "opened_at": __import__('datetime').datetime.fromtimestamp(pos.time, tz=__import__('datetime').timezone.utc),
            "is_deleted": False,
        }
    )
    print(f"  Position synced: {pos.symbol} ticket={ticket} pnl={pos.profit:.2f}")

mt5.shutdown()

print(f"\nDone. Open positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
