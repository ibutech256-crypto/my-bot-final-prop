"""Force position sync with cleanup of duplicates."""
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

# Delete ALL existing DB positions
deleted = OpenPosition.objects.filter(account=acct).delete()
print(f"Cleared {deleted} old DB positions")

for pos in positions:
    try:
        ticket = str(pos.ticket)
        sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
        direction = "BUY" if pos.type == 0 else "SELL"
        
        # Create fresh - no duplicates possible
        OpenPosition.objects.create(
            account=acct,
            symbol=sym_obj,
            direction=direction,
            volume=Decimal(str(pos.volume)),
            entry_price=Decimal(str(pos.price_open)),
            current_price=Decimal(str(pos.price_current)),
            stop_loss=Decimal(str(pos.sl)) if pos.sl else None,
            take_profit=Decimal(str(pos.tp)) if pos.tp else None,
            unrealized_profit=Decimal(str(pos.profit)),
            opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),
            broker_ticket=ticket,
        )
        print(f"  Created: {pos.symbol} ticket={ticket} vol={pos.volume} pnl={pos.profit:.2f}")
    except Exception as e:
        print(f"  Error: {pos.symbol} - {e}")

mt5.shutdown()
print(f"\nDB positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} pnl={p.unrealized_profit}")
