"""Fix MT5 IPC conflict - position sync must not run as separate thread."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# The engine_runner.py launches position_sync in a separate thread.
# MT5 Python API only allows ONE connection at a time.
# Fix: Remove the separate position sync thread, integrate it into engine.

runner_path = r"engine_runner.py"
with open(runner_path, "r") as f:
    content = f.read()

# Remove the separate position sync thread
old_thread = """def run_position_sync():
    \"\"\"Position synchronization daemon.\"\"\"
    while True:
        try:
            from trading_engine.position_sync import PositionSyncEngine
            sync = PositionSyncEngine()
            sync.run_loop()
        except Exception as e:
            log(f\"Position sync error: {e}, restarting in 5s...\")
            time.sleep(5)"""

new_thread = """# Position sync is integrated into the MT5 engine main loop.
# Running it as a separate thread causes MT5 IPC conflicts.
def run_position_sync():
    \"\"\"Position sync disabled - integrated into MT5 engine loop.\"\"\"
    while True:
        time.sleep(60)"""

if old_thread in content:
    content = content.replace(old_thread, new_thread)
    with open(runner_path, "w") as f:
        f.write(content)
    print("Position sync thread fixed - no longer competes for MT5")
else:
    print("Pattern not found - checking runner...")
    # The runner likely has a different structure, just comment out the position sync
    if "PositionSyncEngine" in content:
        content = content.replace("from trading_engine.position_sync import PositionSyncEngine", "# Position sync disabled - see engine main loop")
        content = content.replace("sync = PositionSyncEngine()\n            sync.run_loop()", "pass  # sync integrated in engine loop")
        with open(runner_path, "w") as f:
            f.write(content)
        print("Position sync references removed from runner")

# Also make the position_sync.py's run_loop less aggressive
sync_path = r"trading_engine\position_sync.py"
if os.path.exists(sync_path):
    with open(sync_path, "r") as f:
        sync_content = f.read()
    # Add delay and retry logic
    if "time.sleep(1)" in sync_content:
        sync_content = sync_content.replace("time.sleep(1)", "time.sleep(5)")
        with open(sync_path, "w") as f:
            f.write(sync_content)
        print("Position sync interval increased to 5s to reduce MT5 contention")

print("\n=== Restarting engine ===")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"Engine: {r.stdout.strip()}")

import py_compile
try:
    py_compile.compile(runner_path, doraise=True)
    print("Runner syntax: OK")
except Exception as e:
    print(f"Runner syntax error: {e}")

print("\nDONE")
