"""Direct fix: remove ensure_connected, clear cache, restart clean."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# Stop engine
subprocess.run(['nssm', 'stop', 'TradingMT5Engine'], timeout=10)
time.sleep(2)

# Kill ALL python
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)

# Read engine file and REMOVE any ensure_connected references
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    lines = f.readlines()

print(f"Engine file: {len(lines)} lines")
found = 0
new_lines = []
skip_block = False
for i, line in enumerate(lines):
    if "ensure_connected" in line:
        found += 1
        skip_block = True
        print(f"  REMOVING line {i+1}: {line.strip()[:60]}")
        continue
    if skip_block:
        # Skip the indented block after ensure_connected (4 lines)
        if line.strip() and not line.startswith("                ") and not line.startswith("            "):
            skip_block = False
            new_lines.append(line)
        elif not line.strip():
            continue  # skip blank lines in the block
        else:
            continue  # still in the block
    else:
        new_lines.append(line)

print(f"  Removed {found} references")
with open(eng_path, "w") as f:
    f.writelines(new_lines)

# Verify it's clean
with open(eng_path, "r") as f:
    content = f.read()
if "ensure_connected" in content:
    print("  WARNING: ensure_connected STILL PRESENT!")
else:
    print("  ensure_connected removed successfully")

# Clear ALL pycache  
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
print("  pycache cleared")

# Start engine
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(5)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"Engine: {r.stdout.strip()}")

# Check for errors after 15s
time.sleep(15)

r = subprocess.run(['powershell', '-Command',
    'Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.log -Tail 5'],
    capture_output=True, text=True, timeout=5)
print("\nRecent log:")
print(r.stdout[:500])

r = subprocess.run(['powershell', '-Command',
    'if(Test-Path C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log){Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log -Tail 3}'],
    capture_output=True, text=True, timeout=5)
if r.stdout.strip():
    print(f"Errors: {r.stdout[:200]}")

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("Syntax: OK")
except Exception as e:
    print(f"Syntax ERROR: {e}")

print("\nDONE")
