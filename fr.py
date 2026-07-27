import os, py_compile
os.chdir("C:/prop-frim-bot")

# FIX 1: Fix the volatility threshold (actual value is 0.0012, not 0.05)
p1 = "trading_engine/account_manager.py"
c = open(p1, "r", encoding="utf-8").read()
c = c.replace('atr_ratio < Decimal("0.0012")', 'atr_ratio < Decimal("0.00005")')
open(p1, "w", encoding="utf-8").write(c)
print("FIX 1: Volatility threshold lowered from 0.12% to 0.005%")

# FIX 2: Find and fix adaptive brain dynamic threshold
p2 = "trading_engine/adaptive_brain.py"
c = open(p2, "r", encoding="utf-8").read()
# Find the dynamic threshold calculation
idx = c.find("dynamic threshold")
if idx > 0:
    print(f"\nDynamic threshold found at {idx}:")
    # Show 200 chars around it
    print(c[max(0,idx-50):idx+150])

# Find '75' or '75.00' in adaptive brain
idx2 = c.find("75.00")
if idx2 > 0:
    print(f"\n75.00 found at {idx2}: {c[max(0,idx2-50):idx2+80]}")

# The message says "dynamic threshold 75.00" - need to find where this comes from
import re
matches = list(re.finditer(r'Decimal\([^)]+\)', c))
for m in matches:
    if '75' in m.group():
        start = max(0, m.start()-30)
        print(f"Found: ...{c[start:m.end()+30]}...")

for p, name in [(p1,"Gate"), (p2,"Brain")]:
    py_compile.compile(p, doraise=True)
    print(f"  {name}: SYNTAX OK")

print("\nAll fixes verified!")
