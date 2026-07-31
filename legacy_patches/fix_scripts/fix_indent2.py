"""Fix indentation in mt5_client.py line 90."""
import os, sys

path = r"C:\prop-frim-bot\broker_engine\mt5_client.py"
lines = open(path, "r").readlines()

print(f"Lines 85-100:")
for i in range(84, min(100, len(lines))):
    ai = len(lines[i]) - len(lines[i].lstrip())
    print(f"  {i+1}: indent={ai:3d} |{lines[i][:80]}")

# The function was fixed from indent 0 to 4, but the class method should be at indent 4
# If line 90 is `def place_market_order` at indent 0, it's wrong
for i, line in enumerate(lines):
    if "def place_market_order" in line:
        ai = len(line) - len(line.lstrip())
        if ai != 4:
            print(f"\nFixing line {i+1}: indent {ai} -> 4")
            lines[i] = "    " + line.lstrip()
            break

# Also fix any other lines at indent 0 that should be at 4
# Look for lines that are class methods without indentation
for i, line in enumerate(lines):
    stripped = line.lstrip()
    ai = len(line) - len(line.lstrip())
    if ai == 0 and stripped and not stripped.startswith("class ") and not stripped.startswith("import ") and not stripped.startswith("from ") and not stripped.startswith("#") and not stripped.startswith('"""'):
        # Check if previous line has a class or ends with :
        prev = lines[i-1].strip() if i > 0 else ""
        if prev.endswith(":") or (i > 0 and lines[i-1].strip().startswith("class ")):
            print(f"  Fixing line {i+1}: {stripped[:50]}")
            lines[i] = "    " + stripped

open(path, "w").writelines(lines)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("\nSYNTAX: OK")
except Exception as e:
    print(f"\nSYNTAX ERROR: {e}")
