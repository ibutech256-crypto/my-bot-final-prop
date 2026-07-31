import os, subprocess, py_compile
os.chdir("C:/prop-frim-bot")

# Git restore
subprocess.run(["git", "checkout", "HEAD", "--", 
    "backend/apps/trading/management/commands/run_mt5_engine.py"], capture_output=True)
print("✅ Git restore done")

# Check syntax
try:
    py_compile.compile("backend/apps/trading/management/commands/run_mt5_engine.py", doraise=True)
    print("✅ SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"❌ SYNTAX ERROR: {e}")
    exit(1)

# Now apply ONLY the essential production fixes

p = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p, "r", encoding="utf-8").read()
changes = 0

# Fix 1: Rate limit 30 -> 2 min
if "minutes=30" in c:
    c = c.replace("minutes=30", "minutes=2")
    changes += 1
    print("✅ Rate limit 30->2min")

# Fix 2: Backtesting 40 -> 10
if "[:40]:" in c:
    c = c.replace("[:40]:", "[:10]:")
    changes += 1
    print("✅ Backtesting 40->10")

# Fix 3: PYTHONIOENCODING
if "PYTHONIOENCODING" not in c:
    c = c.replace(
        'from __future__ import annotations',
        'from __future__ import annotations\nimport os; os.environ["PYTHONIOENCODING"] = "utf-8"'
    )
    changes += 1
    print("✅ PYTHONIOENCODING added")

# Fix 4: Fix is_high_conf to use tiered execution
old = "is_high_conf = score.total >= Decimal(\"75\")"
new = "has_sweep2 = sweep is not None and not sweep.failed\n                                            tier1 = score.total >= Decimal(\"55\") and has_sweep2 and kod\n                                            tier2 = score.total >= Decimal(\"70\") and htf_ok\n                                            is_high_conf = tier1 or tier2 or score.total >= Decimal(\"75\")"
if old in c:
    c = c.replace(old, new)
    changes += 1
    print("✅ Tiered execution (55-T1, 70-T2, 75+)")

# Fix 5: ACTIVE signals at score >= 55
old2 = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
new2 = 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",'
if old2 in c:
    c = c.replace(old2, new2)
    changes += 1
    print("✅ ACTIVE at score >= 55")

# Fix 6: Match execution gate to ACTIVE status
old3 = 'if is_high_conf and broker_setting.enable_autotrading:'
new3 = 'if (is_high_conf or score.total >= Decimal("55")) and broker_setting.enable_autotrading:'
if old3 in c:
    c = c.replace(old3, new3)
    changes += 1
    print("✅ Execution gate at score >= 55")

# Fix 7: Add score to signal rationale to verify it passes through
old4 = 'rationale=f"Confluences active: {[k for k, v in score.components.items() if v > 0]}",'
new4 = 'rationale=f"Score={score.total} Tier1={tier1} Tier2={tier2} Confluences: {[k for k, v in score.components.items() if v > 0]}",'
if old4 in c:
    c = c.replace(old4, new4)
    changes += 1
    print("✅ Score+Tier info in rationale")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print(f"\nTotal changes: {changes}")

# Final syntax check
try:
    py_compile.compile(p, doraise=True)
    print("✅ FINAL SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"❌ Error: {e}")
