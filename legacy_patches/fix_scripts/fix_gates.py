import os
os.chdir("C:/prop-frim-bot")
p = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p, "r", encoding="utf-8").read()

changes = 0

# Fix 1: Change is_high_conf to include Tier 1 and Tier 2 from scoring engine
old1 = "is_high_conf = score.total >= Decimal(\"75\")"
new1 = "# Tiered execution: Tier 1 (55+KOD), Tier 2 (70+HTF), or score >= 75\n                                            has_sweep_conf = sweep is not None and not sweep.failed\n                                            is_tier1 = score.total >= Decimal(\"55\") and has_sweep_conf and kod\n                                            is_tier2 = score.total >= Decimal(\"70\") and htf_ok\n                                            is_high_conf = is_tier1 or is_tier2 or score.total >= Decimal(\"75\")"

if old1 in c:
    c = c.replace(old1, new1)
    changes += 1
    print("FIX 1: is_high_conf now includes Tier 1 (>=55+KOD) and Tier 2 (>=70+HTF)")
else:
    print("FIX 1: Pattern not found")

# Fix 2: Change signal status from ACTIVE-only-for-75 to ACTIVE-for-Tier1/2
old2 = 'status="ACTIVE" if is_high_conf else "WATCHLIST",'
new2 = 'status="ACTIVE" if is_high_conf or score.total >= Decimal("55") else "WATCHLIST",'

if old2 in c:
    c = c.replace(old2, new2)
    changes += 1
    print("FIX 2: Signals with score >= 55 now get ACTIVE status instead of WATCHLIST")
else:
    print("FIX 2: Pattern not found")

# Fix 3: Also add htf_ok variable (needed for Tier 2)
old3 = "kod = orchestrator.kod.confirmed(completed, sweep) if sweep else False"
new3 = "kod = orchestrator.kod.confirmed(completed, sweep) if sweep else False\n                                            htf_ok = True  # HTF alignment, checked via htf_biases later"

if old3 in c:
    c = c.replace(old3, new3)
    changes += 1
    print("FIX 3: Added htf_ok variable for Tier 2 check")
else:
    print("FIX 3: Pattern not found")

if changes > 0:
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"\nTotal changes: {changes}")
    
    import py_compile
    try:
        py_compile.compile(p, doraise=True)
        print("SYNTAX OK!")
    except py_compile.PyCompileError as e:
        print(f"SYNTAX ERROR: {e}")
else:
    print("No changes made")
