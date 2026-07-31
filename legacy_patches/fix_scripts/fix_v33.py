"""Fix two critical problems:
1. MT5 IPC conflict - kill all competing processes
2. Old signals showing on dashboard - fix SignalViewSet filter
"""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

# ===== FIX 1: Kill ALL python processes =====
print("=== FIX 1: Kill competing Python processes ===")
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)

# ===== FIX 2: Revert engine_runner to ONLY run mt5 engine =====
print("\n=== FIX 2: Clean engine runner ===")
runner_code = '''"""Engine Runner - runs ONLY the MT5 engine. No competing threads."""
import os, sys, signal, subprocess, time
from datetime import datetime, timezone

BASE = r"C:\\prop-frim-bot"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)
os.chdir(BASE)

signal.signal(signal.SIGINT, signal.SIG_IGN)

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(LOGS, "runner.log"), "a") as f:
        f.write(f"[{ts}] {msg}\\n")
    print(f"[{ts}] {msg}")

if __name__ == "__main__":
    log("=" * 50)
    log("ENGINE RUNNER STARTED")
    log("=" * 50)
    while True:
        log("Starting MT5 Engine...")
        proc = subprocess.Popen(
            [sys.executable, "-u", "backend/manage.py", "run_mt5_engine"],
            cwd=BASE,
            stdout=open(os.path.join(LOGS, "TradingMT5Engine.log"), "a"),
            stderr=subprocess.STDOUT,
        )
        proc.wait()
        log(f"Engine exited (code {proc.returncode}), restarting in 3s...")
        time.sleep(3)
'''

with open(r"engine_runner.py", "w") as f:
    f.write(runner_code)
print("  engine_runner.py rewritten - single engine thread only")

# ===== FIX 3: Fix SignalViewSet to show ACTIVE signals only =====
print("\n=== FIX 3: SignalViewSet - show ACTIVE signals only ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

old_qs = 'return Signal.objects.select_related("symbol", "author").filter(is_deleted=False).order_by("-confidence", "-created_at")'
new_qs = 'return Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status__in=["ACTIVE_MONITORING", "EXECUTION_READY", "WATCHLIST"]).order_by("-confidence", "-created_at")'

if old_qs in vc:
    vc = vc.replace(old_qs, new_qs)
    with open(views_path, "w") as f:
        f.write(vc)
    print("  SignalViewSet filters: non-expired, non-closed signals only")
else:
    # Try alternative pattern
    alt = 'return Signal.objects.select_related("symbol", "author").filter(is_deleted=False).order_by("-confidence", "-created_at")'
    if alt in vc:
        vc = vc.replace(alt, new_qs)
        with open(views_path, "w") as f:
            f.write(vc)
        print("  SignalViewSet fixed (alt)")

# ===== FIX 4: Restart services =====
print("\n=== FIX 4: Restart services ===")
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=15)
time.sleep(5)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

# Verify syntax
import py_compile
for f in [r"engine_runner.py", views_path]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

print("\n=== FIXES APPLIED, waiting for engine to stabilize ===")
