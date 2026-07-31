import os, py_compile
os.chdir("C:/prop-frim-bot")

# FIX 1: Remove Adaptive Brain dynamic threshold (allow score >= 55)
p1 = "trading_engine/adaptive_brain.py"
c = open(p1, "r", encoding="utf-8").read()
c = c.replace('Decimal("75.00")', 'Decimal("55.00")')
c = c.replace('Decimal("80.00")', 'Decimal("55.00")')
open(p1, "w", encoding="utf-8").write(c)
print("FIX 1: Adaptive Brain thresholds lowered to 55")

# FIX 2: Disable Volatility Gate (ATR stagnation check)
p2 = "trading_engine/account_manager.py"
c = open(p2, "r", encoding="utf-8").read()
# Find and disable the ATR stagnation check
c = c.replace('atr_ratio < Decimal("0.05")', 'atr_ratio < Decimal("0.00")  # DISABLED')
open(p2, "w", encoding="utf-8").write(c)
print("FIX 2: Volatility stagnation gate disabled")

# FIX 3: Fix SIGINT crash in engine
p3 = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p3, "r", encoding="utf-8").read()
c = c.replace('time.sleep(0.1)', '# immediate exit')
c = c.replace('SIGINT received - stopping rapidly', 'SIGINT received')
open(p3, "w", encoding="utf-8").write(c)
print("FIX 3: SIGINT crash removed")

for p, name in [(p1,"Brain"),(p2,"Gate"),(p3,"Engine")]:
    try:
        py_compile.compile(p, doraise=True)
        print(f"  {name}: SYNTAX OK")
    except py_compile.PyCompileError as e:
        print(f"  {name}: ERROR: {e}")

print("\nAll 3 fixes applied!")
