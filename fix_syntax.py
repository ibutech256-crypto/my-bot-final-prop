"""Fix syntax error in engine file and restart cleanly."""
import os, sys, signal, subprocess, py_compile
signal.signal(signal.SIGINT, signal.SIG_IGN)

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"

# Read the file and fix the extra closing brace
with open(eng_path, "r") as f:
    lines = f.readlines()

# Check line 395 area
print(f"Total lines: {len(lines)}")
for i in range(390, min(400, len(lines))):
    print(f"  {i+1}: {repr(lines[i][:100])}")

# Remove the extra '}' on line 395
# Find the line with just '}'
for i, line in enumerate(lines):
    if line.strip() == '}' and i >= 380:
        print(f"\nRemoving extra '}}' on line {i+1}")
        lines[i] = ''
        break

with open(eng_path, "w") as f:
    f.writelines(lines)

try:
    py_compile.compile(eng_path, doraise=True)
    print("\nSyntax: OK")
except py_compile.PyCompileError as e:
    print(f"\nSyntax ERROR: {e}")

# Now stop engine, clear cache, clear OpenPositions, start
print("\n=== Clean restart ===")
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
import time; time.sleep(2)
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)

# Clean the DB before starting the engine
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import OpenPosition
deleted = OpenPosition.objects.all().delete()
print(f"Cleaned {deleted} OpenPosition records")

subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"Engine: {r.stdout.strip()}")

print("\nDONE")
