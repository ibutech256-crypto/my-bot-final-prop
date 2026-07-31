"""Remove ensure_connected calls from engine, keep method in mt5_client."""
import os, re

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Remove ensure_connected calls (they were crashing)
# Pattern: the if block that calls ensure_connected and continues
lines = eng.split('\n')
new_lines = []
skip = False
for line in lines:
    if 'ensure_connected' in line:
        skip = True
        continue
    if skip:
        if 'continue' in line:
            skip = False
            continue
        if line.strip() == '' or line.strip().startswith('import') or line.strip().startswith('#'):
            continue
        # Check if line has minimal indent (end of block)
        stripped = line.lstrip()
        ai = len(line) - len(stripped)
        if ai <= 16:  # back to main while loop level or less
            skip = False
            new_lines.append(line)
        continue
    new_lines.append(line)

# Also remove any "                # Ensure MT5 connection" comment
new_lines = [l for l in new_lines if 'Ensure MT5 connection' not in l]

eng = '\n'.join(new_lines)

# Verify clean
if 'ensure_connected' in eng:
    print("WARNING: ensure_connected still present!")
    for i, l in enumerate(eng.split('\n'), 1):
        if 'ensure_connected' in l:
            print(f"  Line {i}: {l[:100]}")
else:
    print("ALL ensure_connected calls removed from engine")

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
