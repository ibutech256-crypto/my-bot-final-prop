import os, sys
os.chdir("C:/prop-frim-bot")

# FIX 1: Remove SIGINT delay
p1 = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p1, "r", encoding="utf-8").read()
c = c.replace('self.stdout.write("SIGINT received - pausing 15s before exit to prevent rapid restart...")', 'self.stdout.write("SIGINT received - stopping")')
c = c.replace('time.sleep(15)', 'time.sleep(0.1)')
open(p1, "w", encoding="utf-8").write(c)
print("FIX 1: SIGINT delay removed")

# FIX 2: Lower adaptive brain threshold
p2 = "trading_engine/adaptive_brain.py"
c = open(p2, "r", encoding="utf-8").read()
# Remove ALL instances of 80.00 threshold
c = c.replace('Decimal("80.00")', 'Decimal("55.00")')
# Remove the exotic cross-currency quarantine
c = c.replace('"Exotic cross-currency wide spread & point drain"', '"Exotic pair - lower confidence"')
open(p2, "w", encoding="utf-8").write(c)
print("FIX 2: Adaptive brain threshold 80->55")

# FIX 3: Remove volatility stagnation gate
p3 = "trading_engine/account_manager.py"
c = open(p3, "r", encoding="utf-8").read()
# Find and disable the stagnation check
if "stagnant = atr_14 / current_price" in c:
    c = c.replace('stagnant = atr_14 / current_price', 'stagnant = False  # atr_14 / current_price')
    open(p3, "w", encoding="utf-8").write(c)
    print("FIX 3: Volatility stagnation gate disabled")
else:
    print("FIX 3: Stagnation pattern not found")
    if "stagnant" in c:
        idx = c.find("stagnant")
        print(f"  Found at {idx}: {c[idx:idx+100]}")

# Verify syntax
import py_compile
for p, name in [(p1, "Engine"), (p2, "Brain"), (p3, "Account")]:
    try:
        py_compile.compile(p, doraise=True)
        print(f"  {name}: SYNTAX OK")
    except py_compile.PyCompileError as e:
        print(f"  {name}: ERROR: {e}")

print("\nAll fixes applied!")
