"""Fix WebSocket reconnection and position sync."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from backend.apps.trading.models import TradingAccount, OpenPosition, TradingSymbol
from decimal import Decimal
from datetime import datetime, timezone
import MetaTrader5 as mt5

# 1. Force position sync
print("=== Force position sync ===")
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)
positions = mt5.positions_get() or []
acct = TradingAccount.objects.first()

print(f"MT5 positions: {len(positions)}")
for pos in positions:
    ticket = str(pos.ticket)
    print(f"  Found: {pos.symbol} ticket={ticket} vol={pos.volume} pnl={pos.profit:.2f}")
    
    sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
    direction = "BUY" if pos.type == 0 else "SELL"
    
    # Force update the position
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
            "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),
            "is_deleted": False,
        }
    )
    print(f"    -> Synced to DB")

# Clean stale positions
mt5_tickets = set(str(p.ticket) for p in positions)
for dbp in OpenPosition.objects.filter(is_deleted=False):
    if dbp.broker_ticket not in mt5_tickets:
        dbp.is_deleted = True
        dbp.save()
        print(f"  Removed stale: {dbp.symbol.symbol} ticket={dbp.broker_ticket}")

mt5.shutdown()

print(f"\nOpen positions in DB: {OpenPosition.objects.filter(is_deleted=False).count()}")
for p in OpenPosition.objects.filter(is_deleted=False):
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} pnl={p.unrealized_profit}")

# 2. Restart backend + frontend to reset WebSocket
print("\n=== Restarting WebSocket services ===")
subprocess.run(['nssm', 'restart', 'TradingBackend'], timeout=15)
time.sleep(3)
subprocess.run(['nssm', 'restart', 'TradingFrontend'], timeout=15)
time.sleep(5)

for svc in ['TradingBackend', 'TradingFrontend', 'TradingMT5Engine']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc}: {r.stdout.strip()}")

# 3. Verify API
print("\n=== API Check ===")
import json
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/open-positions/?limit=5'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"Positions API: {len(data)}")
    for p in data:
        print(f"  {p['symbol_name']} {p['direction']} PnL={p['unrealized_profit']} ticket={p.get('broker_ticket','?')}")
except:
    print(f"Positions: {r.stdout[:100]}")

r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=5'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"Signals API: {len(data)} signals")
    for s in data[:3]:
        print(f"  {s['symbol_name']:15s} Status={s['status']:20s} Score={s['confidence']}")
except:
    print(f"Signals: {r.stdout[:100]}")

print("\nDONE")
