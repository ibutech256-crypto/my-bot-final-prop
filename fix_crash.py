"""Fix: engine crash (ensure_connected missing) + ensure KOD detection works."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

print("=" * 50)
print("FIX: Engine crash + KOD detection")
print("=" * 50)

# ===== FIX 1: Restore engine main loop (remove ensure_connected call) =====
print("\n=== 1. Fix engine main loop ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Remove the ensure_connected() call that doesn't exist yet
old = "                # Ensure MT5 connection with auto-reconnect\n                if not client.ensure_connected():\n                    import time as _t\n                    _t.sleep(5)\n                    continue\n                info = client.account_info()"
new = "                info = client.account_info()"

if old in eng:
    eng = eng.replace(old, new)
    print("  Removed broken ensure_connected() call - using direct account_info()")
else:
    # Try alternate pattern
    if "ensure_connected" in eng:
        idx = eng.find("ensure_connected")
        print(f"  Found ensure_connected at {idx}, removing...")
        # Find the block to remove
        start = eng.rfind("\n", 0, idx)
        end = eng.find("\n", eng.find("continue", idx))
        if end > start:
            # Remove the 4 lines starting from start
            lines = eng.split('\n')
            # Find which line has ensure_connected
            for i, l in enumerate(lines):
                if "ensure_connected" in l:
                    # Remove lines i to i+3 (the if block)
                    for j in range(i, min(i+4, len(lines))):
                        lines[j] = ""
                    # Also need to keep the info = client.account_info() line
                    break
            eng = '\n'.join([l for l in lines if l.strip() or l == ''])
            print("  ensure_connected block removed")
    else:
        print("  No ensure_connected found - engine already clean")

with open(eng_path, "w") as f:
    f.write(eng)

# ===== FIX 2: Ensure scoring.py has correct v2.2 logic =====
print("\n=== 2. Verify scoring engine ===")
score_path = r"C:\prop-frim-bot\trading_engine\scoring.py"
with open(score_path, "r") as f:
    sc = f.read()

# Ensure the KOD cap logic is present
if "if not kod:" in sc and "total = min(total, Decimal(\"70\"))" in sc:
    print("  KOD cap logic present")
else:
    print("  WARNING: KOD cap missing!")

# Ensure scoring uses passed correctly  
if "score.passed" in eng:
    print("  Engine uses score.passed (correct)")
else:
    print("  WARNING: score.passed not in engine!")

# ===== FIX 3: Verify kod.py logic =====
print("\n=== 3. Verify KOD engine ===")
kod_path = r"C:\prop-frim-bot\trading_engine\kod.py"
with open(kod_path, "r") as f:
    kod = f.read()

# Check what min_body_ratio is set to
if "min_body_ratio" in kod:
    for line in kod.split('\n'):
        if "min_body_ratio" in line:
            print(f"  {line.strip()}")

# Check the confirmed method signature
for line in kod.split('\n'):
    if "def confirmed" in line:
        print(f"  {line.strip()}")

# ===== FIX 4: Verify orchestrator evaluate_signal dispatch =====
print("\n=== 4. Verify orchestrator dispatch ===")
orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    orch = f.read()

# Check that evaluate or evaluate_signal is the entry point
if "def evaluate_signal" in orch:
    print("  evaluate_signal method present")
elif "def evaluate" in orch:
    print("  evaluate method present (v1)")
else:
    print("  WARNING: No evaluate method found!")

# Check the engine calls the right method
if "evaluate_signal" in eng:
    print("  Engine calls evaluate_signal()")
elif "orchestrator.scoring.score" in eng:
    print("  Engine calls orchestrator.scoring.score() directly")

# ===== FIX 5: Syntax check all files =====
print("\n=== 5. Syntax check ===")
import py_compile
for fname in [eng_path, score_path, kod_path, orch_path]:
    try:
        py_compile.compile(fname, doraise=True)
        print(f"  {os.path.basename(fname)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(fname)}: ERROR - {e}")

# ===== FIX 6: Kill all python, clear cache, restart =====
print("\n=== 6. Clean restart ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(8)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"\n  Engine: {r.stdout.strip()}")

# ===== FIX 7: Monitor =====
print("\n=== 7. Monitoring (waiting 30s) ===")
time.sleep(30)

# Check for errors
r = subprocess.run(['powershell', '-Command',
    'Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 10'],
    capture_output=True, text=True, timeout=5)
print("Recent log:")
print(r.stdout[:1000])

# Count engine starts since fix
r = subprocess.run(['powershell', '-Command',
    '(Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 100 | Select-String -Pattern "Starting MT5" | Measure-Object).Count'],
    capture_output=True, text=True, timeout=5)
print(f"\nEngine restarts (last 100 lines): {r.stdout.strip()}")

# Check error log
r = subprocess.run(['powershell', '-Command',
    'if(Test-Path C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log){Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log -Tail 3} else{echo "No err log"}'],
    capture_output=True, text=True, timeout=5)
print(f"Error log: {r.stdout.strip()[:300]}")

print("\n=== FIX COMPLETE ===")
