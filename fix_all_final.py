"""Restore clean git, apply ALL fixes, restart."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

import subprocess, time, py_compile

print("=== 1. Restore clean from git ===")
subprocess.run(['git', 'checkout', '--', 
    'broker_engine/mt5_client.py',
    'backend/apps/trading/management/commands/run_mt5_engine.py'], 
    timeout=15, capture_output=True)
print("  Clean files restored")

print("\n=== 2. Add ensure_connected() to mt5_client.py ===")
with open(r"C:\prop-frim-bot\broker_engine\mt5_client.py", "r") as f:
    mc = f.read()

mc = mc.replace("self.path = path", "self.path = path\n        self.is_connected = False\n        self.reconnect_attempts = 0")

ensure = """
    def ensure_connected(self) -> bool:
        import time as _t
        if getattr(self, 'is_connected', False):
            try:
                info = self.mt5.account_info()
                if info is not None:
                    self.reconnect_attempts = 0
                    return True
            except:
                pass
            self.is_connected = False
        self.reconnect_attempts = getattr(self, 'reconnect_attempts', 0) + 1
        delay = min(1.0 * (2 ** (self.reconnect_attempts - 1)), 30.0)
        _t.sleep(delay)
        if self.mt5.initialize() and self.mt5.login(self.login, self.password, self.server):
            self.is_connected = True
            self.reconnect_attempts = 0
            return True
        return False

"""
idx = mc.find("    def connect(self) -> bool:")
if idx > 0:
    mc = mc[:idx] + ensure + mc[idx:]
    with open(r"C:\prop-frim-bot\broker_engine\mt5_client.py", "w") as f:
        f.write(mc)
    print("  ensure_connected() added")

print("\n=== 3. Fix both OpenPosition.update_or_create calls ===")
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    eng = f.read()

# Fix 1: First update_or_create (the one in the position sync loop)
old1 = 'OpenPosition.objects.update_or_create(\n                        account=account,\n                        broker_ticket=ticket,\n                        defaults={\n                            "symbol": sym_obj,\n                            "direction": SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,\n                            "volume": Decimal(str(pos.volume)),\n                            "entry_price": Decimal(str(pos.price_open)),\n                            "current_price": Decimal(str(pos.price_current)),\n                            "stop_loss": Decimal(str(pos.sl)) if pos.sl else None,\n                            "take_profit": Decimal(str(pos.tp)) if pos.tp else None,\n                            "unrealized_profit": Decimal(str(pos.profit)),\n                            "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),\n                        }\n                    )'
new1 = 'OpenPosition.objects.filter(account=account, broker_ticket=ticket).delete()\n                    OpenPosition.objects.create(\n                        account=account,\n                        broker_ticket=ticket,\n                        symbol=sym_obj,\n                        direction=SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,\n                        volume=Decimal(str(pos.volume)),\n                        entry_price=Decimal(str(pos.price_open)),\n                        current_price=Decimal(str(pos.price_current)),\n                        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,\n                        take_profit=Decimal(str(pos.tp)) if pos.tp else None,\n                        unrealized_profit=Decimal(str(pos.profit)),\n                        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),\n                    )'

if old1 in eng:
    eng = eng.replace(old1, new1, 1)
    print("  Fix 1: First update_or_create -> delete+create")
else:
    print("  Fix 1: Pattern not found")

# Fix 2: Second update_or_create (the one in the execution pipeline)
old2 = 'OpenPosition.objects.update_or_create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                defaults={\n                                                                                    "symbol": symbol_obj,\n                                                                                    "direction": SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                    "volume": lot_size,\n                                                                                    "entry_price": filled_price,\n                                                                                    "current_price": filled_price,\n                                                                                    "stop_loss": exec_sl,\n                                                                                    "take_profit": exec_tp,\n                                                                                    "unrealized_profit": Decimal("0.00"),\n                                                                                    "opened_at": django_tz.now(),\n                                                                                }\n                                                                            )'
new2 = 'OpenPosition.objects.filter(account=account, broker_ticket=ticket_str).delete()\n                                                                            OpenPosition.objects.create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                symbol=symbol_obj,\n                                                                                direction=SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                volume=lot_size,\n                                                                                entry_price=filled_price,\n                                                                                current_price=filled_price,\n                                                                                stop_loss=exec_sl,\n                                                                                take_profit=exec_tp,\n                                                                                unrealized_profit=Decimal("0.00"),\n                                                                                opened_at=django_tz.now(),\n                                                                            )'

if old2 in eng:
    eng = eng.replace(old2, new2, 1)
    print("  Fix 2: Second update_or_create -> delete+create")
else:
    print("  Fix 2: Pattern not found - trying alternative...")
    # The file might have \r endings
    old2r = old2.replace('\n', '\r\n')
    if old2r in eng:
        eng = eng.replace(old2r, new2.replace('\n', '\r\n'), 1)
        print("  Fix 2: Matched with \\r\\n")
    else:
        # Show what's around the second update_or_create
        idx = eng.find("update_or_create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str")
        if idx < 0:
            idx = eng.find("update_or_create")
        if idx >= 0:
            print(f"  Found at {idx}:")
            print(repr(eng[idx:idx+100]))

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
    f.write(eng)

print("\n=== 4. Syntax check ===")
for fname in ['broker_engine/mt5_client.py', 'backend/apps/trading/management/commands/run_mt5_engine.py']:
    try:
        py_compile.compile(os.path.join(r"C:\prop-frim-bot", fname), doraise=True)
        print(f"  {os.path.basename(fname)}: OK")
    except py_compile.PyCompileError as e:
        print(f"  {os.path.basename(fname)}: ERROR - {e}")

# Verify no update_or_create remains
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    eng2 = f.read()
if 'OpenPosition.objects.update_or_create' in eng2:
    print("\n⚠️ update_or_create STILL present!")
    idx = eng2.find('OpenPosition.objects.update_or_create')
    line_num = eng2[:idx].count('\n') + 1
    print(f"   Line {line_num}")
else:
    print("\n✅ All OpenPosition.update_or_create removed")

print("\n=== 5. Clean restart ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(4)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(3)

# Clean DB
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import OpenPosition, TradingAccount
c = OpenPosition.objects.count()
OpenPosition.objects.all().delete()
print(f"  Cleaned {c} OpenPosition records")

# Re-create current position from MT5
import MetaTrader5 as mt5
login=int(os.getenv("MT5_LOGIN","436005794"))
pw=os.getenv("MT5_PASSWORD","1234#Dt@")
sv=os.getenv("MT5_SERVER","Exness-MT5Trial9")
mt5.initialize()
mt5.login(login, pw, sv)
acct=TradingAccount.objects.first()
from backend.apps.trading.models import TradingSymbol
from decimal import Decimal
from datetime import datetime, timezone
for pos in (mt5.positions_get() or []):
    ticket=str(pos.ticket)
    sym_obj,_=TradingSymbol.objects.get_or_create(symbol=pos.symbol)
    OpenPosition.objects.create(
        account=acct, broker_ticket=ticket, symbol=sym_obj,
        direction="BUY" if pos.type==0 else "SELL",
        volume=Decimal(str(pos.volume)), entry_price=Decimal(str(pos.price_open)),
        current_price=Decimal(str(pos.price_current)),
        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,
        take_profit=Decimal(str(pos.tp)) if pos.tp else None,
        unrealized_profit=Decimal(str(pos.profit)),
        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc))
    print(f"  Synced: {pos.symbol} ticket={ticket}")
mt5.shutdown()

subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(8)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"\nEngine: {r.stdout.strip()}")

# Git commit
r = subprocess.run(['git', 'add', 'broker_engine/mt5_client.py', 'backend/apps/trading/management/commands/run_mt5_engine.py'], capture_output=True, text=True, timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix: ensure_connected, both OpenPosition delete+create patterns'], capture_output=True, text=True, timeout=10)
print(f"\n{r.stdout[:200]}")
r = subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)
print(r.stdout[:100])

print("\n=== DONE ===")
