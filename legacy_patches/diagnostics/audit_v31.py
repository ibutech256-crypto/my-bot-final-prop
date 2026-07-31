"""Audit v3.1 state and identify gaps."""
import os, sys
os.chdir(r"C:\prop-frim-bot")
sys.path.insert(0, ".")

# Check mt5_client for safety net
with open(r"C:\prop-frim-bot\broker_engine\mt5_client.py", "r") as f:
    mc = f.read()

if "TRADE_ACTION_SLTP" in mc and "sl = 0.0" in mc:
    print("TWO-STEP ECN DISPATCH: DEPLOYED")
    # Check for emergency close fallback
    if "emergency" in mc.lower() or "opposite" in mc.lower():
        print("  Emergency close fallback: PRESENT")
    else:
        print("  Emergency close fallback: MISSING - NEEDS FIX")
else:
    print("TWO-STEP ECN DISPATCH: MISSING")

# Check signal_freshness for JSON logging
with open(r"C:\prop-frim-bot\system\signal_freshness.py", "r") as f:
    sf = f.read()
if "json" in sf.lower() and "payload" in sf.lower():
    print("EXPIRED SIGNAL JSON LOGGING: PRESENT")
else:
    print("EXPIRED SIGNAL JSON LOGGING: MISSING")

# Check for BLOCKED badges
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    eng = f.read()
badges = ["SPREAD_THRESHOLD", "CISD", "DRAWDOWN", "SESSION_GAP", "HTF_ALIGNMENT"]
found = [b for b in badges if b in eng]
missing = [b for b in badges if b not in eng]
print(f"\nBLOCKED badges found: {found}")
print(f"BLOCKED badges missing: {missing}")

# Check session expiry (180s)
with open(r"C:\prop-frim-bot\system\signal_freshness.py", "r") as f:
    sf = f.read()
if "SESSION_TIMEOUTS" in sf:
    print("SESSION TIMEOUTS: PRESENT")
    if "180" in sf:
        print("  180s session expiry: PRESENT")
    else:
        print("  180s session expiry: CHECK")
else:
    print("SESSION TIMEOUTS: MISSING")

print("\n=== AUDIT COMPLETE ===")
