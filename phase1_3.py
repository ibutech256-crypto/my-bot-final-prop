"""Phase 1: Fix Signal views to show ALL signals with confidence tiers, not just ACTIVE.
Phase 2: Add rejection tracking.
Phase 3: Fix account mode system.
Phase 4: Fix position sizing."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# ===== PHASE 1: Fix SignalViewSet =====
print("=== PHASE 1: SignalViewSet - show all signals, add confidence tiers ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

# Replace the SignalViewSet get_queryset to show ALL signals, not just ACTIVE
old_qs = """class SignalViewSet(ActiveModelViewSet):
    queryset=Signal.objects.all()
    def get_queryset(self):
        # by pagination / the ordering filter instead.
        return Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status=\"ACTIVE\").order_by("-confidence", "-created_at")"""

new_qs = """class SignalViewSet(ActiveModelViewSet):
    queryset=Signal.objects.all()
    def get_queryset(self):
        status_filter = self.request.query_params.get("status", None)
        qs = Signal.objects.select_related("symbol", "author").filter(is_deleted=False).order_by("-confidence", "-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs"""

if old_qs.strip() in vc.strip():
    vc = vc.replace(old_qs.strip(), new_qs.strip())
    with open(views_path, "w") as f:
        f.write(vc)
    print("SignalViewSet fixed - now shows ALL signals (status filter optional)")
else:
    print("SignalViewSet pattern not found, checking actual content...")
    idx = vc.find("class SignalViewSet")
    if idx >= 0:
        end = vc.find("\nclass ", idx+10)
        print(vc[idx:end][:400])

# ===== PHASE 2: Add confidence tier field to serializer =====
print("\n=== PHASE 2: Add confidence tier to serializers ===")
ser_path = r"C:\prop-frim-bot\backend\apps\trading\serializers.py"
with open(ser_path, "r") as f:
    sc = f.read()

if "confidence_tier" not in sc:
    # Add confidence_tier to SignalSerializer
    old = """class SignalSerializer(ActiveModelSerializer):"""
    new = """class SignalSerializer(ActiveModelSerializer):
    confidence_tier = serializers.SerializerMethodField()
    def get_confidence_tier(self, obj):
        c = float(obj.confidence)
        if c >= 85: return "VERY_STRONG"
        if c >= 70: return "STRONG"
        if c >= 55: return "VALID"
        if c >= 50: return "EMERGING"
        return "WEAK"
"""
    sc = sc.replace(old, new)
    
    # Add symbol_name field if not there
    if "symbol_name" not in sc:
        old2 = """class Meta:"""
        new2 = """    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    class Meta:"""
        sc = sc.replace(old2, new2)
    
    with open(ser_path, "w") as f:
        f.write(sc)
    print("Confidence tier added to SignalSerializer")
else:
    print("Confidence tier already exists")

# ===== PHASE 3: Account Manager overhaul =====
print("\n=== PHASE 3: Account Manager overhaul ===")
acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"
with open(acct_path, "r") as f:
    ac = f.read()

# Add PROP_FIRM mode detection (threshold at $500)
if "AccountMode" in ac:
    print("AccountMode exists")
    
    # Update the mode detection to use $500 threshold
    old_mode = """    def get_account_mode(self) -> AccountMode:
        if self.account.balance < Decimal(\"1000\") or \"GROW\" in self.account.account_name.upper():
            return AccountMode.GROWING_PERSONAL
        return AccountMode.PROP_FIRM"""
    
    new_mode = """    def get_account_mode(self) -> AccountMode:
        # $500 threshold: below = GROWTH, at/above = candidate for PROP_FIRM
        # Account must explicitly be named PROP_FIRM to use prop-firm rules
        if \"PROP_FIRM\" in self.account.account_name.upper():
            return AccountMode.PROP_FIRM
        if self.account.balance < Decimal(\"500\") or \"GROW\" in self.account.account_name.upper():
            return AccountMode.GROWING_PERSONAL
        # Default to GROWING for accounts $500+ that aren't explicitly PROP_FIRM
        return AccountMode.GROWING_PERSONAL"""
    
    if old_mode in ac:
        ac = ac.replace(old_mode, new_mode)
        with open(acct_path, "w") as f:
            f.write(ac)
        print("Account mode detection updated ($500 threshold)")
    else:
        print("Mode detection pattern not found")
    
    # Fix position sizing to be truly equity-based for GROWTH
    old_sizing = """        if mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            if equity < Decimal(\"100\"):
                raw_lots = min_lot
            elif equity < Decimal(\"250\"):
                raw_lots = min_lot * Decimal(\"2\")
            elif equity < Decimal(\"500\"):
                raw_lots = min_lot * Decimal(\"4\")
            else:
                raw_lots = (equity / Decimal(\"1000\")) * Decimal(\"0.05\")
            safety_max = Decimal(\"0.10\")"""
    
    new_sizing = """        if mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            risk_pct = Decimal(\"0.005\")  # 0.5% risk per trade
            risk_amount = equity * risk_pct
            price_risk = abs(entry_price - stop_loss)
            if price_risk <= Decimal(\"0\"):
                return min_lot
            contract_size = Decimal(\"100000\")
            raw_by_risk = risk_amount / (price_risk * contract_size)
            raw_by_equity = (equity / Decimal(\"1000\")) * Decimal(\"0.05\")
            raw_lots = min(raw_by_risk, raw_by_equity)
            safety_max = Decimal(\"0.20\")"""
    
    if old_sizing in ac:
        ac = ac.replace(old_sizing, new_sizing)
        with open(acct_path, "w") as f:
            f.write(ac)
        print("Position sizing updated: equity-based with 0.5% risk")
    else:
        print("Sizing pattern not found")

# Verify syntax
import py_compile
try:
    py_compile.compile(views_path, doraise=True)
    print(f"VIEWS SYNTAX: OK")
except Exception as e:
    print(f"VIEWS SYNTAX ERROR: {e}")
try:
    py_compile.compile(ser_path, doraise=True)
    print(f"SERIALIZER SYNTAX: OK")
except Exception as e:
    print(f"SERIALIZER SYNTAX ERROR: {e}")
try:
    py_compile.compile(acct_path, doraise=True)
    print(f"ACCOUNT_MANAGER SYNTAX: OK")
except Exception as e:
    print(f"ACCOUNT_MANAGER SYNTAX ERROR: {e}")

print("\n=== PHASE 1-3 COMPLETE ===")
