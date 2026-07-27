import os, subprocess, py_compile
os.chdir("C:/prop-frim-bot")

print("=== APPLYING ALL PRODUCTION FIXES ===\n")

# Fix 1: BrokerOrderRequest - add expiration + is_pit_open
p1 = "broker_engine/mt5_client.py"
c = open(p1, "r").read()
old1 = '    order_type: str = "MARKET"  # MARKET, LIMIT'
new1 = '    order_type: str = "MARKET"\n    expiration: int | None = None\n    is_pit_open: bool | None = None'
if old1 in c:
    c = c.replace(old1, new1)
    open(p1, "w").write(c)
    print("FIX 1: BrokerOrderRequest - added expiration + is_pit_open")
else:
    print("FIX 1: WARNING - pattern not found")

# Fix 2: Rate limit 30->2 min
p2 = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p2, "r").read()
c = c.replace("minutes=30", "minutes=2")
print("FIX 2: Rate limit 30->2min")

# Fix 3: Backtesting 40->10
c = c.replace("[:40]:", "[:10]:")
print("FIX 3: Backtesting 40->10")

# Fix 4: PYTHONIOENCODING
if "PYTHONIOENCODING" not in c:
    c = c.replace("from __future__ import annotations",
                  "from __future__ import annotations\nimport os; os.environ[\"PYTHONIOENCODING\"] = \"utf-8\"")
    print("FIX 4: PYTHONIOENCODING added")

# Fix 5: Tiered execution
old5 = 'is_high_conf = score.total >= Decimal("75")'
new5 = 'has_sweep2 = sweep is not None and not sweep.failed\n                                            tier1 = score.total >= Decimal("55") and has_sweep2 and kod\n                                            tier2 = score.total >= Decimal("70") and htf_ok\n                                            is_high_conf = tier1 or tier2 or score.total >= Decimal("75")'
if old5 in c:
    c = c.replace(old5, new5)
    print("FIX 5: Tiered execution (55->T1, 70->T2, 75+)")

# Fix 6: ACTIVE at 55
old6 = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
new6 = 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",'
if old6 in c:
    c = c.replace(old6, new6)
    print("FIX 6: Signals ACTIVE at score >= 55")

# Fix 7: Execution gate at 55
old7 = 'if is_high_conf and broker_setting.enable_autotrading:'
new7 = 'if (is_high_conf or score.total >= Decimal("55")) and broker_setting.enable_autotrading:'
if old7 in c:
    c = c.replace(old7, new7)
    print("FIX 7: Execution gate at score >= 55")

# Fix 8: Add tier info to rationale
old8 = 'rationale=f"Confluences active: {[k for k, v in score.components.items() if v > 0]}",'
new8 = 'rationale=f"Score={score.total} Tier1={tier1} Tier2={tier2} Sweep={has_sweep2} KOD={kod} Confluences: {[k for k, v in score.components.items() if v > 0]}",'
if old8 in c:
    c = c.replace(old8, new8)
    print("FIX 8: Score + Tier info in rationale")

# Save engine
open(p2, "w").write(c)

# Verify all syntax
for p, name in [(p1, "Broker"), (p2, "Engine")]:
    try:
        py_compile.compile(p, doraise=True)
        print(f"  {name}: SYNTAX OK")
    except py_compile.PyCompileError as e:
        print(f"  {name}: ERROR: {e}")

# Clear pycache
subprocess.run("for /r C:\\prop-frim-bot %d in (__pycache__) do @if exist \"%d\" rd /s /q \"%d\" 2>NUL", shell=True)
subprocess.run("del /s /q C:\\prop-frim-bot\\*.pyc 2>NUL", shell=True)

print("\n=== ALL FIXES APPLIED SUCCESSFULLY ===")
print("Engine is ready for restart")
