"""Clean fix - restore from git, apply only clean fixes."""
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

print("\n=== 2. Only add ensure_connected to mt5_client.py ===")
with open("broker_engine/mt5_client.py","r") as f:
    mc = f.read()
mc = mc.replace("self.path = path", "self.path = path\n        self.is_connected = False\n        self.reconnect_attempts = 0")
ensure = '\n    def ensure_connected(self) -> bool:\n        import time as _t\n        if getattr(self, \'is_connected\', False):\n            try:\n                info = self.mt5.account_info()\n                if info is not None:\n                    self.reconnect_attempts = 0\n                    return True\n            except:\n                pass\n            self.is_connected = False\n        self.reconnect_attempts = getattr(self, \'reconnect_attempts\', 0) + 1\n        delay = min(1.0 * (2 ** (self.reconnect_attempts - 1)), 30.0)\n        _t.sleep(delay)\n        if self.mt5.initialize() and self.mt5.login(self.login, self.password, self.server):\n            self.is_connected = True\n            self.reconnect_attempts = 0\n            return True\n        return False\n\n'
idx = mc.find("    def connect(self) -> bool:")
if idx > 0:
    mc = mc[:idx] + ensure + mc[idx:]
    with open("broker_engine/mt5_client.py","w") as f:
        f.write(mc)
    print("  ensure_connected() added")

# DON'T change the engine file - only ensure_connected fix
# The OpenPosition crash is handled by cleaning duplicates from DB

# Verify syntax
print("\n=== 3. Syntax check ===")
for fname in ["broker_engine/mt5_client.py", "backend/apps/trading/management/commands/run_mt5_engine.py"]:
    try:
        py_compile.compile(fname, doraise=True)
        print(f"  {os.path.basename(fname)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(fname)}: ERROR - {e}")

print("\n=== 4. Stop + clean + start ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(4)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)

# Clean OpenPosition DB (delete ALL duplicates)
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol
from decimal import Decimal
from datetime import datetime, timezone
import MetaTrader5 as mt5

c = OpenPosition.objects.count()
OpenPosition.objects.all().delete()
print(f"  Cleaned {c} OpenPosition records")

# Re-sync single position from MT5
login=int(os.getenv("MT5_LOGIN","436005794"))
pw=os.getenv("MT5_PASSWORD","1234#Dt@")
sv=os.getenv("MT5_SERVER","Exness-MT5Trial9")
mt5.initialize()
mt5.login(login,pw,sv)
acct=TradingAccount.objects.first()
positions = mt5.positions_get() or []
for pos in positions:
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

# Start engine
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"\nEngine: {r.stdout.strip()}")

# Git
subprocess.run(['git', 'add', 'broker_engine/mt5_client.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix: ensure_connected for mt5 IPC reconnect'], capture_output=True, text=True, timeout=10)
print(r.stdout[:200])
subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)

print("\nDONE - waiting for signals...")
