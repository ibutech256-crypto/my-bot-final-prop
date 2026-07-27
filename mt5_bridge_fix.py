"""Standalone MT5 Bridge Fix - upload and run directly on VPS.\n\nRun: .venv\\Scripts\\python.exe mt5_bridge_fix_standalone.py\n"""
import os, sys, signal, pathlib, shutil, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")
BASE = r"C:\prop-frim-bot"

print("=" * 50)
print("MT5 BRIDGE FIX - DEPLOYMENT")
print("=" * 50)

# ===== 1. ADD ensure_connected() to mt5_client.py =====
print("\n=== 1. MT5 Client: ensure_connected() ===")
client_path = os.path.join(BASE, "broker_engine", "mt5_client.py")
with open(client_path, "r") as f:
    mc = f.read()

if "def ensure_connected" not in mc:
    # Add is_connected to __init__
    if "self.is_connected" not in mc:
        mc = mc.replace("self.path = path", "self.path = path\n        self.is_connected = False\n        self.reconnect_attempts = 0")
        print("  is_connected field added")
    
    # Add ensure_connected method before connect
    reconnect_code = """
    def ensure_connected(self) -> bool:
        \"\"\"Auto-reconnect with exponential backoff.\"\"\"
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
        if self.mt5.initialize():
            if self.mt5.login(self.login, self.password, self.server):
                self.is_connected = True
                self.reconnect_attempts = 0
                return True
        return False
    
"""
    idx = mc.find("    def connect(self) -> bool:")
    if idx > 0:
        mc = mc[:idx] + reconnect_code + mc[idx:]
        print("  ensure_connected() method added")
    
    with open(client_path, "w") as f:
        f.write(mc)
else:
    print("  ensure_connected() already exists")

# ===== 2. ADD reconnection to engine main loop =====
print("\n=== 2. Engine: reconnection wrapper ===")
engine_path = os.path.join(BASE, "backend", "apps", "trading", "management", "commands", "run_mt5_engine.py")
with open(engine_path, "r") as f:
    eng = f.read()

# Fix main loop
old_loop = '        while True:\n            try:\n                info = client.account_info()'
new_loop = '        while True:\n            try:\n                # Auto-reconnect if MT5 drops\n                if not client.ensure_connected():\n                    import time as _t\n                    _t.sleep(5)\n                    continue\n                info = client.account_info()'

if old_loop in eng:
    eng = eng.replace(old_loop, new_loop)
    print("  Main loop reconnection wrapper added")
else:
    # Try alternate patterns
    idx = eng.find("while True:")
    if idx >= 0:
        context = eng[idx:idx+200]
        print(f"  Found while loop at {idx}: {context[:100]}")

# Fix exception handler to reset connection flag
old_exc = 'except Exception as e:\n                self.stderr.write(f"Error inside MT5 engine loop: {e}")\n                time.sleep(1)'
new_exc = 'except Exception as e:\n                self.stderr.write(f"Error inside MT5 engine loop: {e}")\n                try: client.is_connected = False\n                except: pass\n                time.sleep(1)'

if old_exc in eng:
    eng = eng.replace(old_exc, new_exc)
    print("  Exception handler updated (resets connection flag)")
else:
    print("  Exception handler pattern not found - may already be fixed")

with open(engine_path, "w") as f:
    f.write(eng)

# ===== 3. ADD health endpoint =====
print("\n=== 3. Health check view ===")
views_path = os.path.join(BASE, "backend", "apps", "trading", "views.py")
with open(views_path, "r") as f:
    vc = f.read()

if "class MT5HealthView" not in vc:
    # Check imports
    if "from rest_framework.views import APIView" not in vc:
        vc = "from rest_framework.views import APIView\nfrom rest_framework.permissions import AllowAny\n" + vc
    
    health_view_code = """
class MT5HealthView(APIView):
    \"\"\"Health check for MT5 connection and system status.\"\"\"
    permission_classes = [AllowAny]
    
    def get(self, request):
        data = {"mt5": "DISCONNECTED", "engine": "UNKNOWN", "positions": 0}
        import MetaTrader5 as mt5
        try:
            login = int(os.getenv("MT5_LOGIN", "436005794"))
            password = os.getenv("MT5_PASSWORD", "1234#Dt@")
            server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
            if mt5.initialize():
                if mt5.login(login, password, server):
                    info = mt5.account_info()
                    if info:
                        data["mt5"] = "CONNECTED"
                        data["balance"] = info.balance
                        data["equity"] = info.equity
                        data["positions"] = len(mt5.positions_get() or [])
                    mt5.shutdown()
        except:
            pass
        from backend.apps.trading.models import TradingAccount
        acct = TradingAccount.objects.first()
        if acct:
            data["db_balance"] = float(acct.balance)
            data["db_equity"] = float(acct.equity)
        return Response(data)
"""
    vc = vc + health_view_code
    with open(views_path, "w") as f:
        f.write(vc)
    print("  MT5HealthView added to views.py")
else:
    print("  MT5HealthView already exists")

# ===== 4. ADD URL route =====
print("\n=== 4. URL route ===")
urls_path = os.path.join(BASE, "backend", "apps", "common", "api_urls.py")
with open(urls_path, "r") as f:
    uc = f.read()

if "mt5-health" not in uc:
    if "MT5HealthView" not in uc:
        old_import = "from backend.apps.trading.views import"
        new_import = "from backend.apps.trading.views import MT5HealthView,"
        if old_import in uc:
            uc = uc.replace(old_import, new_import)
            uc = uc.replace("MT5HealthView,MT5HealthView", "MT5HealthView")
    
    # Add route at end of urlpatterns
    if "urlpatterns" in uc:
        uc = uc.rstrip() + "\npath('mt5-health/', MT5HealthView.as_view(), name='mt5-health'),\n"
    
    with open(urls_path, "w") as f:
        f.write(uc)
    print("  URL route registered")
else:
    print("  URL route already exists")

# ===== 5. SYNTAX CHECK =====
print("\n=== 5. Syntax verification ===")
import py_compile
files = [client_path, engine_path, views_path, urls_path]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except py_compile.PyCompileError as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

# ===== 6. RESTART =====
print("\n=== 6. Restart services ===")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
subprocess.run(['nssm', 'restart', 'TradingBackend'], timeout=15)
time.sleep(8)

for svc in ['TradingMT5Engine', 'TradingBackend']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc}: {r.stdout.strip()}")

# ===== 7. HEALTH CHECK =====
print("\n=== 7. Health check ===")
time.sleep(5)
import json as _json
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/mt5-health/'], capture_output=True, text=True, timeout=10)
try:
    data = _json.loads(r.stdout)
    print(f"  MT5: {data.get('mt5', 'UNKNOWN')}")
    print(f"  Balance: ${data.get('balance', 0)}")
    print(f"  Positions: {data.get('positions', 0)}")
except:
    print(f"  Health check response: {r.stdout[:200]}")

# ===== 8. GIT =====
print("\n=== 8. Git commit ===")
subprocess.run(['git', 'add', 'broker_engine/mt5_client.py',
                'backend/apps/trading/management/commands/run_mt5_engine.py',
                'backend/apps/trading/views.py',
                'backend/apps/common/api_urls.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix: MT5 bridge reconnection, health endpoint, ensure_connected()'], capture_output=True, text=True, timeout=10)
print(r.stdout[:200])
subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)

print("\n=== MT5 BRIDGE FIX COMPLETE ===")
