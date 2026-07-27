"""Check MT5 and DB positions directly, then sync."""
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

print("=== MT5 DIRECT ===")
mt5.initialize()
if not mt5.login(login, pw, sv):
    print(f"MT5 login failed: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

positions = mt5.positions_get() or []
print(f"Positions: {len(positions)}")
for p in positions:
    print(f"  {p.symbol} vol={p.volume} entry={p.price_open} current={p.price_current}")
    print(f"  sl={p.sl} tp={p.tp} profit={p.profit:.2f} ticket={p.ticket}")

info = mt5.account_info()
if info:
    print(f"Balance: {info.balance} Equity: {info.equity}")

print("\n=== DB BEFORE SYNC ===")
acct = TradingAccount.objects.first()
db_pos = OpenPosition.objects.filter(is_deleted=False)
print(f"Open positions (is_deleted=False): {db_pos.count()}")
for p in db_pos:
    print(f"  {p.symbol.symbol} {p.direction} vol={p.volume} entry={p.entry_price} pnl={p.unrealized_profit} ticket={p.broker_ticket}")

total = OpenPosition.objects.count()
print(f"Total position records: {total}")

# If there are positions in MT5 but not in DB, or DB is stale, force sync
if positions:
    print("\n=== FORCE SYNC ===")
    # Mark all existing DB positions as deleted first (clean slate)
    deleted_count = OpenPosition.objects.filter(account=acct).delete()
    print(f"Cleared {deleted_count} old records")
    
    for p in positions:
        ticket = str(p.ticket)
        sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=p.symbol)
        direction = "BUY" if p.type == 0 else "SELL"
        
        OpenPosition.objects.create(
            account=acct,
            symbol=sym_obj,
            direction=direction,
            volume=Decimal(str(p.volume)),
            entry_price=Decimal(str(p.price_open)),
            current_price=Decimal(str(p.price_current)),
            stop_loss=Decimal(str(p.sl)) if p.sl else None,
            take_profit=Decimal(str(p.tp)) if p.tp else None,
            unrealized_profit=Decimal(str(p.profit)),
            opened_at=datetime.fromtimestamp(p.time, tz=timezone.utc),
            broker_ticket=ticket,
        )
        print(f"  Created: {p.symbol} ticket={ticket} profit={p.profit:.2f}")
    
    print(f"\nDB positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
else:
    print("\nNo positions in MT5. Cleaning stale DB records.")
    OpenPosition.objects.filter(account=acct).update(is_deleted=True)
    print("All DB positions marked as deleted")

mt5.shutdown()

print("\nDONE")
