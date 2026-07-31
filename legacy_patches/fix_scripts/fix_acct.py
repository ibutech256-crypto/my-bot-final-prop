"""Fix account_manager.py - restore sizing code to correct method."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"

# Restore from git first, then apply targeted fix
print("=== Restoring account_manager.py from git ===")
os.system(f'cd {os.path.dirname(acct_path)} && git checkout -- account_manager.py 2>&1')
os.chdir(r"C:\prop-frim-bot")
os.system('git checkout -- trading_engine/account_manager.py')
print("Restored!")

with open(acct_path, "r") as f:
    ac = f.read()

# Now fix the sizing in calculate_position_size (should be around line 300-330)
idx = ac.find("def calculate_position_size")
if idx >= 0:
    end = ac.find("\n    return final_lots", idx)
    method = ac[idx:end+20]
    print(f"Found calculate_position_size at line {ac[:idx].count(chr(10))+1}")
    
    # Replace the growing personal sizing block
    old_sizing = """            safety_max = Decimal(\"0.50\")
        
        final_lots = (raw_lots / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step"""
    
    new_sizing = """            safety_max = Decimal(\"0.50\")
        
        # Growth mode: scale from equity (0.5% risk)
        if status.mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            risk_amount = equity * Decimal(\"0.005\")
            price_risk = abs(entry_price - stop_loss)
            if price_risk > Decimal(\"0\"):
                cs = Decimal(str(spec.trade_contract_size if spec else symbol_obj.contract_size))
                if cs <= Decimal(\"0\"):
                    cs = Decimal(\"100000\")
                raw_by_risk = risk_amount / (price_risk * cs)
                raw_by_equity = (equity / Decimal(\"1000\")) * Decimal(\"0.05\")
                raw_lots = min(raw_by_risk, raw_by_equity)
        
        final_lots = (raw_lots / lot_step).to_integral_value(rounding=ROUND_DOWN) * lot_step"""
    
    if old_sizing in ac:
        ac = ac.replace(old_sizing, new_sizing)
        with open(acct_path, "w") as f:
            f.write(ac)
        print("Position sizing updated: 0.5% risk-based, equity-aware")
    else:
        print("Old sizing pattern not found!")
        print(f"Looking for: '{old_sizing[:60]}...'")
        # Show what's between safety_max and final_lots
        idx2 = ac.find("safety_max", idx)
        print(f"Context: {ac[idx2:idx2+200]}")
else:
    print("calculate_position_size not found!")

import py_compile
try:
    py_compile.compile(acct_path, doraise=True)
    print("SYNTAX: OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")

# Also fix SignalViewSet using sed-like approach
print("\n=== Fixing SignalViewSet ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

# Replace the get_queryset return line
old_line = "return Signal.objects.select_related(\"symbol\", \"author\").filter(is_deleted=False, status=\"ACTIVE\").order_by(\"-confidence\", \"-created_at\")"
new_line = "return Signal.objects.select_related(\"symbol\", \"author\").filter(is_deleted=False).order_by(\"-confidence\", \"-created_at\")"

if old_line in vc:
    vc = vc.replace(old_line, new_line)
    with open(views_path, "w") as f:
        f.write(vc)
    print("SignalViewSet fixed!")
else:
    # Try without escaped quotes
    old_line2 = 'return Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status="ACTIVE").order_by("-confidence", "-created_at")'
    new_line2 = 'return Signal.objects.select_related("symbol", "author").filter(is_deleted=False).order_by("-confidence", "-created_at")'
    if old_line2 in vc:
        vc = vc.replace(old_line2, new_line2)
        with open(views_path, "w") as f:
            f.write(vc)
        print("SignalViewSet fixed (alt)!")
    else:
        print("Pattern not found!")
        idx = vc.find("is_deleted=False, status=")
        if idx >= 0:
            print(f"Found at {idx}: {vc[idx:idx+120]}")

import py_compile
try:
    py_compile.compile(views_path, doraise=True)
    print("VIEWS SYNTAX: OK")
except Exception as e:
    print(f"VIEWS SYNTAX ERROR: {e}")

print("\nDONE")
