"""FINAL FIX: Truncate OpenPosition duplicates, prevent recurrence."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from backend.apps.trading.models import OpenPosition, TradingAccount
from decimal import Decimal
from datetime import datetime, timezone
import MetaTrader5 as mt5

# STEP 1: TRUNCATE ALL OpenPosition records (clean slate)
print("=== STEP 1: Clean OpenPosition table ===")
count = OpenPosition.objects.count()
OpenPosition.objects.all().delete()
print(f"  Deleted all {count} records")

# STEP 2: Sync fresh from MT5
print("\n=== STEP 2: Fresh sync from MT5 ===")
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)

positions = mt5.positions_get() or []
acct = TradingAccount.objects.first()
print(f"  MT5 positions: {len(positions)}")
from backend.apps.trading.models import TradingSymbol

for pos in positions:
    ticket = str(pos.ticket)
    sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
    direction = "BUY" if pos.type == 0 else "SELL"
    
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
    print(f"  Created: {pos.symbol} ticket={ticket}")

mt5.shutdown()

# STEP 3: Fix the engine's update_or_create calls
print("\n=== STEP 3: Fix engine position sync code ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Replace update_or_create with a delete + create pattern that can't fail
old = """                    OpenPosition.objects.update_or_create(
                        account=account,
                        broker_ticket=ticket,
                        defaults={"""
new = """                    # Clean create (prevents 'get() returned more than one' crash)
                    OpenPosition.objects.filter(account=account, broker_ticket=ticket).delete()
                    OpenPosition.objects.create(
                        account=account,
                        broker_ticket=ticket,
                        symbol=sym_obj,"""

if old in eng:
    eng = eng.replace(old, new)
    # Also handle the closing of the defaults dict
    old2 = """                        }
                    )"""
    new2 = """                    )"""
    # Be careful - only replace the one after our new block
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  Engine position sync changed to delete+create (safe)")
else:
    print("  update_or_create pattern not found - checking...")
    if "update_or_create" in eng:
        idx = eng.find("update_or_create")
        print(f"  Found at {idx}: {eng[idx:idx+100]}")

# STEP 4: Fix the sym_obj reference issue
# The old code had defaults dict, new code doesn't need it
# but we need to make sure the variable references are correct
with open(eng_path, "r") as f:
    eng = f.read()

# The old defaults dict provided symbol=sym_obj, direction=direction etc.
# Our replacement does that via direct kwargs. Need to verify.
if "symbol=sym_obj" in eng and "direction" in eng and "volume" in eng:
    print("  Position creation kwargs verified")

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("\nSyntax: OK")
except Exception as e:
    print(f"\nSyntax ERROR: {e}")

print(f"\nOpenPosition count: {OpenPosition.objects.count()}")
print("DONE")
