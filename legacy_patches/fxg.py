import os, sys
os.chdir("C:/prop-frim-bot")
p = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p, "r", encoding="utf-8").read()

# FIX: Change the execution gate from "is_high_conf" to match ACTIVE status threshold
# Signals become ACTIVE at score >= 55, so execution should also trigger at score >= 55
old = 'if is_high_conf and broker_setting.enable_autotrading:'
new = 'if (is_high_conf or score.total >= Decimal("55")) and broker_setting.enable_autotrading:'

if old in c:
    c = c.replace(old, new)
    open(p, "w", encoding="utf-8").write(c)
    print("FIX: Execution gate now matches ACTIVE status threshold (score >= 55)")
else:
    print("Pattern not found, checking...")
    idx = c.find("if is_high_conf and broker_setting")
    if idx >= 0:
        print(f"Found: {c[idx:idx+80]}")
    else:
        print("Gate not found in expected location")

# Verify syntax
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")

# Also log what changed
print(f"\nOld: {old}")
print(f"New: {new}")
