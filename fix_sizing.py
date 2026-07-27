"""Fix the GROWING_PERSONAL position sizing with proper equity-based calculation."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"
with open(acct_path, "r") as f:
    ac = f.read()

# Replace the GROWING_PERSONAL sizing block
old = """        if status.mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            if equity < Decimal(\"100\"):
                raw_lots = min_lot
            elif equity < Decimal(\"250\"):
                raw_lots = min_lot * Decimal(\"2\")
            elif equity < Decimal(\"500\"):
                raw_lots = min_lot * Decimal(\"4\")
            else:
                raw_lots = (equity / Decimal(\"1000\")) * Decimal(\"0.05\")
            safety_max = Decimal(\"0.05\")"""

new = """        if status.mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            risk_amount = equity * Decimal(\"0.005\")
            price_risk = abs(entry_price - stop_loss)
            if price_risk > Decimal(\"0\"):
                cs = Decimal(str(spec.trade_contract_size if spec else symbol_obj.contract_size))
                if cs <= Decimal(\"0\"):
                    cs = Decimal(\"100000\")
                raw_lots = risk_amount / (price_risk * cs)
            else:
                raw_lots = min_lot
            safety_max = Decimal(\"0.20\")"""

if old in ac:
    ac = ac.replace(old, new)
    with open(acct_path, "w") as f:
        f.write(ac)
    print("GROWING_PERSONAL sizing updated: 0.5% risk, equity-based")
else:
    print("Pattern not found!")
    # Show what's there
    idx = ac.find("if status.mode == AccountMode.GROWING_PERSONAL:")
    if idx >= 0:
        end = ac.find("\n        else:", idx)
        print(f"Found: {ac[idx:end+10]}")

import py_compile
try:
    py_compile.compile(acct_path, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")

# Verify final code
print("\n=== Final GROWING sizing code ===")
idx = ac.find("if status.mode == AccountMode.GROWING_PERSONAL:")
if idx >= 0:
    end = ac.find("\n        else:", idx)
    print(ac[idx:end])

print("\nDONE")
