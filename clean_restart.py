"""Clean restart: kill everything, start ONLY the engine, verify no IPC errors."""
import os, sys, signal, subprocess, time, json
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

print("=== 1. Stop services ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
subprocess.run(['nssm', 'stop', 'TradingWorker'], timeout=10)
subprocess.run(['nssm', 'stop', 'TradingBeat'], timeout=10)
time.sleep(2)

print("=== 2. Kill ALL python processes ===")
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)

# Verify no python left
r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], capture_output=True, text=True, timeout=5)
py_count = r.stdout.count('python.exe')
print(f"  Python processes after kill: {py_count}")
if py_count > 0:
    # Force kill with WMIC
    subprocess.run(['wmic', 'PROCESS', 'WHERE', "name='python.exe'", 'CALL', 'terminate'], capture_output=True, timeout=10)
    time.sleep(2)

print("=== 3. Clear cache ===")
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)

print("=== 4. Verify engine file is clean (no syntax errors) ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("  Engine syntax: OK")
except Exception as e:
    print(f"  Engine syntax ERROR: {e}")

# Check for ensure_connected
with open(eng_path, "r") as f:
    eng = f.read()
if "ensure_connected" in eng:
    print("  Removing ensure_connected references...")
    lines = eng.split('\n')
    new_lines = [l for l in lines if "ensure_connected" not in l]
    eng = '\n'.join(new_lines)
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  ensure_connected removed")

print("=== 5. Start engine ===")
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(5)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

# Start workers back
subprocess.run(['nssm', 'start', 'TradingWorker'], timeout=10)
subprocess.run(['nssm', 'start', 'TradingBeat'], timeout=10)

print("\n=== 6. Monitoring (45s) ===")
time.sleep(45)

# Check engine log for errors
r = subprocess.run(['powershell', '-Command',
    'Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 15'],
    capture_output=True, text=True, timeout=5)
print("\n=== Engine log ===")
print(r.stdout[:1500])

# Check error log
r = subprocess.run(['powershell', '-Command',
    'if(Test-Path C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log){Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log -Tail 3}'],
    capture_output=True, text=True, timeout=5)
if r.stdout.strip():
    print(f"\nErrors: {r.stdout[:300]}")
else:
    print("\nNo errors!")

# Count restarts
r = subprocess.run(['powershell', '-Command',
    '(Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 100 | Select-String -Pattern "Starting MT5" | Measure-Object).Count'],
    capture_output=True, text=True, timeout=5)
print(f"Engine restarts (last 100 lines): {r.stdout.strip()}")

# Check signals
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=5'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"\nSignals: {len(data)}")
    for s in data:
        print(f"  {s['symbol_name']:15s} Score={s['confidence']:>5s} Status={s['status']}")
except:
    print(f"API: {r.stdout[:100]}")

# Check positions
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/open-positions/?limit=3'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"Positions: {len(data)}")
except:
    pass

print("\n=== DONE ===")
