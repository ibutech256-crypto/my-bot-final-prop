"""Apply Fix 1 (pass confidence), Fix 2 (safety_max), and diagnose dashboard sync."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# ===== FIX 1: Pass confidence to calculate_position_size =====
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
content = open(p).read()

old = "lot_size = mgr.calculate_position_size(symbol_obj, sig.entry_price, sig.stop_loss)"
new = "lot_size = mgr.calculate_position_size(symbol_obj, sig.entry_price, sig.stop_loss, sig.confidence)"
if old in content:
    content = content.replace(old, new)
    open(p, "w").write(content)
    print("FIX 1: confidence passed to calculate_position_size")
else:
    # Check what actually exists
    idx = content.find("calculate_position_size")
    if idx >= 0:
        print(f"FOUND at {idx}: {content[idx:idx+120]}")
    else:
        print("NOT FOUND!")

# ===== FIX 2: safety_max = 0.10 =====
p2 = r"C:\prop-frim-bot\trading_engine\account_manager.py"
content2 = open(p2).read()

old2 = "safety_max = Decimal(\"0.05\")"
new2 = "safety_max = Decimal(\"0.10\")"
count = content2.count(old2)
if count > 0:
    # Only replace the one in Growing Personal section (first occurrence)
    content2 = content2.replace(old2, new2, 1)
    open(p2, "w").write(content2)
    print(f"FIX 2: safety_max 0.05 -> 0.10 (Growing Personal)")
else:
    print("FIX 2: pattern not found!")

# Verify syntax
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print(f"ENGINE SYNTAX: OK")
except Exception as e:
    print(f"ENGINE SYNTAX ERROR: {e}")

try:
    py_compile.compile(p2, doraise=True)
    print(f"ACCOUNT_MANAGER SYNTAX: OK")
except Exception as e:
    print(f"ACCOUNT_MANAGER SYNTAX ERROR: {e}")

# ===== DIAGNOSE DASHBOARD SYNC =====
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import OpenPosition, TradingAccount, Signal
from decimal import Decimal

print("\n=== DASHBOARD SYNC DIAGNOSIS ===")

# Check OpenPositions in DB
db_positions = OpenPosition.objects.filter(is_deleted=False)
print(f"OpenPositions in DB: {db_positions.count()}")
for pos in db_positions:
    print(f"  {pos.symbol.symbol} {pos.direction} ticket={pos.broker_ticket} volume={pos.volume} entry={pos.entry_price}")

# Check TradingAccount for current values
acct = TradingAccount.objects.first()
if acct:
    print(f"\nTradingAccount in DB: balance={acct.balance} equity={acct.equity} margin={acct.margin}")

# Compare with MT5
import MetaTrader5 as mt5
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
mt5.initialize()
mt5.login(login, pw, sv)

info = mt5.account_info()
if info:
    print(f"\nMT5 Account: balance={info.balance} equity={info.equity} margin={info.margin} margin_free={info.margin_free}")
    print(f"DB balance matches MT5: {acct and abs(acct.balance - Decimal(str(info.balance))) < Decimal('0.01')}")

positions = mt5.positions_get() or []
print(f"\nMT5 open positions: {len(positions)}")
for pos in positions:
    print(f"  {pos.symbol} {'BUY' if pos.type==0 else 'SELL'} ticket={pos.ticket} vol={pos.volume} entry={pos.price_open} sl={pos.sl} tp={pos.tp} profit={pos.profit:.2f}")

# Check if MT5 positions match DB OpenPositions
mt5_tickets = set(str(p.ticket) for p in positions)
db_tickets = set(p.broker_ticket for p in db_positions)
missing_in_db = mt5_tickets - db_tickets
extra_in_db = db_tickets - mt5_tickets
if missing_in_db:
    print(f"\n⚠️ Positions in MT5 but NOT in DB: {missing_in_db}")
if extra_in_db:
    print(f"⚠️ Positions in DB but NOT in MT5: {extra_in_db}")
if not missing_in_db and not extra_in_db:
    print("✅ DB and MT5 position sets match")

mt5.shutdown()

print("\n=== DIAGNOSIS COMPLETE ===")
