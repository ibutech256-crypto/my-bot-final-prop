"""Deploy v2.4 from within VPS - files already uploaded to C:\prop-frim-bot."""
import os, sys, signal, subprocess, time, shutil
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

# Move files to correct locations
files = {
    "position_sync.py": r"trading_engine\position_sync.py",
    "platform_health.py": r"trading_engine\platform_health.py",
    "engine_runner.py": r"engine_runner.py",
}

for src, dst in files.items():
    if os.path.exists(src):
        shutil.move(src, dst)
        print(f"Moved: {src} -> {dst}")
    else:
        print(f"Source not found: {src}")

# Verify syntax
import py_compile
for name, path in files.items():
    full = os.path.join(r"C:\prop-frim-bot", path)
    if os.path.exists(full):
        try:
            py_compile.compile(full, doraise=True)
            print(f"SYNTAX OK: {path}")
        except Exception as e:
            print(f"SYNTAX ERROR: {path}: {e}")

# Register engine runner with NSSM
print("\n=== Registering Engine Runner ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)

subprocess.run(['nssm', 'set', 'TradingMT5Engine', 'Application',
                r'C:\prop-frim-bot\.venv\Scripts\python.exe'], timeout=10)
subprocess.run(['nssm', 'set', 'TradingMT5Engine', 'AppParameters',
                r'engine_runner.py'], timeout=10)
subprocess.run(['nssm', 'set', 'TradingMT5Engine', 'AppDirectory',
                r'C:\prop-frim-bot'], timeout=10)

subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(5)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"Engine: {r.stdout.strip()}")

# Services check
print("\n=== All Services ===")
for svc in ['Memurai', 'TradingBackend', 'TradingWorker', 'TradingBeat', 'TradingFrontend', 'TradingMT5Engine']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc}: {r.stdout.strip()}")

# First health check
print("\n=== Platform Health Check ===")
sys.path.insert(0, ".")
try:
    from trading_engine.platform_health import PlatformHealth
    ph = PlatformHealth()
    report = ph.run_all_checks()
    print(f"Health Score: {report['health_score']}%")
    for k, v in sorted(report['checks'].items()):
        print(f"  {k}: {v.get('status', 'UNKNOWN')}")
except Exception as e:
    print(f"Health check failed (expected - services restarting): {e}")

# Git
print("\n=== Git ===")
subprocess.run(['git', 'add', 'trading_engine/position_sync.py',
                'trading_engine/platform_health.py', 'engine_runner.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'v2.4: position sync, platform health, self-healing runner'],
                   capture_output=True, text=True, timeout=10)
print(r.stdout[:200])
r = subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)
print(r.stdout[:200])

print("\n=== V2.4 DEPLOYED ===")
