"""KILL ALL competing MT5 connections. Run ONLY the engine thread."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

print("=" * 50)
print("FIX: Eliminate MT5 IPC conflict")
print("=" * 50)

# 1. STOP everything
print("\n=== 1. Killing all processes ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)

# 2. Rewrite engine_runner.py to ONLY run the engine - NO other threads
print("\n=== 2. Rewriting engine_runner.py (single thread only) ===")
runner = '''"""Engine Runner - runs ONLY the MT5 engine. NO competing threads."""
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
    log("ENGINE RUNNER STARTED (SINGLE THREAD)")
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
    f.write(runner)
print("  engine_runner.py: single thread, no Position Manager, no health daemon")

# 3. Remove the "Position Manager daemon started" line from engine
# (the engine should NOT start its own position manager thread)
print("\n=== 3. Checking engine for position manager thread ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

if "pm_thread.start()" in eng:
    eng = eng.replace("pm_thread.start()\n        self.stdout.write(\"Position Manager daemon started\")", "# Position Manager disabled - IPC conflict prevention")
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  Position Manager thread removed from engine")
else:
    print("  Position Manager not found in engine")

# Also remove any PositionManager imports
if "from trading_engine.position_manager import PositionManager" in eng:
    eng = eng.replace("from trading_engine.position_manager import PositionManager\n        import threading\n        pm = PositionManager()\n        pm_thread = threading.Thread(target=pm.run_loop, daemon=True)\n        pm_thread.start()\n        # Position Manager disabled - IPC conflict prevention", "# Position Manager disabled")
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  PositionManager import removed from engine")

# 4. Clear ALL pycache
print("\n=== 4. Clearing cache ===")
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)

# 5. Start engine
print("\n=== 5. Starting engine ===")
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(8)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

# 6. Monitor
print("\n=== 6. Monitoring (waiting 30s) ===")
time.sleep(30)

r = subprocess.run(['powershell', '-Command',
    'Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 10'],
    capture_output=True, text=True, timeout=5)
print("=== Engine log ===")
print(r.stdout[:1000])

r = subprocess.run(['powershell', '-Command',
    'if(Test-Path C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log){Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log -Tail 3} else{echo "No errors"}'],
    capture_output=True, text=True, timeout=5)
print(f"\nErrors: {r.stdout.strip()[:200]}")

# 7. Count engine restarts
r = subprocess.run(['powershell', '-Command',
    '(Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 100 | Select-String -Pattern "Starting MT5" | Measure-Object).Count'],
    capture_output=True, text=True, timeout=5)
print(f"Restarts: {r.stdout.strip()}")

print("\n=== FIX COMPLETE ===")
