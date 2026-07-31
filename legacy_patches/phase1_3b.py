"""Phase 1b: Fix the SignalViewSet properly and sizing."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# ===== FIX SignalViewSet =====
print("=== SignalViewSet fix ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

# Find the get_queryset and replace it
idx = vc.find("class SignalViewSet")
end = vc.find("\nclass ", idx+10)
section = vc[idx:end]
print(f"Current SignalViewSet:\n{section[:600]}")

# Replace the entire get_queryset to show ALL signals
old_get = """    def get_queryset(self):
        # Restrict to the last 50 signals to keep serialization lightning fast and prevent timeouts!
        # NOTE: no slice here - slicing before DRF OrderingFilter runs raises
        # \"Cannot reorder a query once a slice has been taken\".
        qs = Signal.objects.select_related(\"symbol\", \"author\").filter(is_deleted=False, status=\"ACTIVE\").order_by(\"-confidence\", \"-created_at\")
        return qs"""

new_get = """    def get_queryset(self):
        qs = Signal.objects.select_related(\"symbol\", \"author\").filter(is_deleted=False).order_by(\"-confidence\", \"-created_at\")
        return qs"""

if old_get.strip() in vc:
    vc = vc.replace(old_get.strip(), new_get.strip())
    with open(views_path, "w") as f:
        f.write(vc)
    print("SignalViewSet.get_queryset fixed - shows ALL signals, not just ACTIVE")
else:
    print("get_queryset pattern not found!")
    print(f"Looking for: '{old_get[:50]}...'")

# ===== FIX Position Sizing =====
print("\n=== Position sizing fix ===")
acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"
with open(acct_path, "r") as f:
    ac = f.read()

# Find the actual growing personal sizing block
idx = ac.find("if mode == AccountMode.GROWING_PERSONAL:")
if idx >= 0:
    end = ac.find("\n        else:", idx)
    section = ac[idx:end]
    print(f"Current GROWING_PERSONAL sizing:\n{section[:500]}")
    
    old_sizing = section.split("\n        else:")[0]
    
    new_sizing = """        if mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            risk_amount = equity * Decimal(\"0.005\")  # 0.5% risk per trade
            price_risk = abs(entry_price - stop_loss)
            if price_risk <= Decimal(\"0\"):
                return min_lot
            contract_size = Decimal(str(spec.trade_contract_size)) if spec else Decimal(\"100000\")
            raw_lots = risk_amount / (price_risk * contract_size)
            safety_max = Decimal(\"0.20\")"""
    
    ac = ac.replace(section, new_sizing)
    with open(acct_path, "w") as f:
        f.write(ac)
    print("Position sizing updated - 0.5% risk, equity-based")
else:
    print("GROWING_PERSONAL block not found!")

# Verify syntax
import py_compile
try:
    py_compile.compile(views_path, doraise=True)
    print("VIEWS SYNTAX: OK")
except Exception as e:
    print(f"VIEWS SYNTAX ERROR: {e}")
try:
    py_compile.compile(acct_path, doraise=True)
    print("ACCOUNT_MANAGER SYNTAX: OK")
except Exception as e:
    print(f"ACCOUNT_MANAGER SYNTAX ERROR: {e}")

print("\nDONE")
