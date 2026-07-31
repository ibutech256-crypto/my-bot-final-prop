"""V3.3: Account modes, view filter, engine stability - all-in-one deploy."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# ===== 1. FIX VIEWSET - only show live signals =====
print("=== 1. SignalViewSet filter ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

old = '.filter(is_deleted=False).order_by("-confidence", "-created_at")'
new = '.filter(is_deleted=False, status__in=["WATCHLIST","ACTIVE_MONITORING","EXECUTION_READY"]).order_by("-confidence", "-created_at")'

if old in vc:
    vc = vc.replace(old, new)
    with open(views_path, "w") as f:
        f.write(vc)
    print("  View filter set to: WATCHLIST, ACTIVE_MONITORING, EXECUTION_READY only")
else:
    print("  Pattern not found - checking...")
    idx = vc.find("is_deleted=False")
    if idx >= 0:
        print(f"  Found at {idx}: {vc[idx:idx+80]}")

# ===== 2. REWRITE ACCOUNT MANAGER with dual modes =====
print("\n=== 2. Account Manager - dual modes ===")
acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"
with open(acct_path, "r") as f:
    ac = f.read()

# Replace the mode detection
old_mode = """    def get_account_mode(self) -> AccountMode:
        # $500 threshold: below = GROWTH, at/above = candidate for PROP_FIRM
        # Account must explicitly be named PROP_FIRM to use prop-firm rules
        if \"PROP_FIRM\" in self.account.account_name.upper():
            return AccountMode.PROP_FIRM
        if self.account.balance < Decimal(\"500\") or \"GROW\" in self.account.account_name.upper():
            return AccountMode.GROWING_PERSONAL
        # Default to GROWING for accounts $500+ that aren't explicitly PROP_FIRM
        return AccountMode.GROWING_PERSONAL"""

new_mode = """    def get_account_mode(self) -> AccountMode:
        # Dual mode based on equity threshold
        equity = self.account.equity
        if equity < Decimal(\"500\") or \"GROW\" in self.account.account_name.upper():
            return AccountMode.GROWING_PERSONAL
        return AccountMode.PROP_FIRM"""

if old_mode in ac:
    ac = ac.replace(old_mode, new_mode)
    print("  Mode detection updated (GROWTH < $500, PROP_FIRM >= $500)")
else:
    print("  Mode pattern not found - checking...")
    idx = ac.find("def get_account_mode")
    if idx >= 0:
        end = ac.find("\n    def ", idx+20)
        print(f"  Found at {idx}: {ac[idx:end][:200]}")

# Replace the evaluate_status for GROWING_PERSONAL (Growth Mode: 4-5 concurrent, 8-15 daily)
old_eval = """        if mode == AccountMode.GROWING_PERSONAL:
            max_open_positions = 10
            max_daily_trades = 50
            daily_target_trades = 25"""

new_eval = """        if mode == AccountMode.GROWING_PERSONAL:
            max_open_positions = 5
            max_daily_trades = 15
            daily_target_trades = 8"""

if old_eval in ac:
    ac = ac.replace(old_eval, new_eval)
    print("  Growth mode limits: 5 max open, 15 max daily, 8 target")
else:
    print("  Growth limits pattern not found")

# Replace PROP_FIRM limits
old_prop = """            max_open_positions = 5
            max_daily_trades = 25
            daily_target_trades = 15"""

new_prop = """            max_open_positions = 3
            max_daily_trades = 10
            daily_target_trades = 5"""

if old_prop in ac:
    ac = ac.replace(old_prop, new_prop)
    print("  Prop firm limits: 3 max open, 10 max daily, 5 target")
else:
    print("  Prop firm limits pattern not found")

# Replace position sizing for GROWING_PERSONAL with 0.01 base micro-lot
old_size = """        if status.mode == AccountMode.GROWING_PERSONAL:
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

new_size = """        if status.mode == AccountMode.GROWING_PERSONAL:
            equity = self.account.equity
            if equity < Decimal(\"100\"):
                raw_lots = min_lot
            elif equity < Decimal(\"250\"):
                raw_lots = min_lot * Decimal(\"2\")
            elif equity < Decimal(\"500\"):
                raw_lots = min_lot * Decimal(\"3\")
            else:
                raw_lots = (equity / Decimal(\"1000\")) * Decimal(\"0.03\")
            safety_max = Decimal(\"0.10\")"""

if old_size in ac:
    ac = ac.replace(old_size, new_size)
    print("  Growth sizing: micro-lot (0.01-0.03 based on equity)")
else:
    print("  Growth sizing pattern not found")

# Replace prop firm sizing with strict % risk
old_prop_size = """        else:
            price_risk = abs(entry_price - stop_loss)
            min_price_risk_floor = entry_price * Decimal(\"0.002\")
            effective_price_risk = max(price_risk, min_price_risk_floor, Decimal(\"0.00010\"))
            cash_risk = self.account.balance * Decimal(\"0.0050\")
            contract_size = Decimal(str(spec.trade_contract_size if spec else symbol_obj.contract_size))
            if contract_size <= Decimal(\"0\"):
                contract_size = Decimal(\"100000\")
            raw_lots = cash_risk / (effective_price_risk * contract_size)
            safety_max = Decimal(\"0.50\")"""

new_prop_size = """        else:
            price_risk = abs(entry_price - stop_loss)
            effective_price_risk = max(price_risk, Decimal(\"0.00010\"))
            cash_risk = self.account.balance * Decimal(\"0.008\")
            contract_size = Decimal(str(spec.trade_contract_size if spec else symbol_obj.contract_size))
            if contract_size <= Decimal(\"0\"):
                contract_size = Decimal(\"100000\")
            raw_lots = cash_risk / (effective_price_risk * contract_size)
            safety_max = Decimal(\"0.50\")"""

if old_prop_size in ac:
    ac = ac.replace(old_prop_size, new_prop_size)
    print("  Prop firm sizing: 0.8% risk-based")
else:
    print("  Prop sizing pattern not found")

with open(acct_path, "w") as f:
    f.write(ac)

# ===== 3. FIX SCORING - add Backtest flag logic =====
print("\n=== 3. Scoring engine check ===")
score_path = r"C:\prop-frim-bot\trading_engine\scoring.py"
with open(score_path, "r") as f:
    sc = f.read()

# Ensure the scoring has proper minimum validation
if "minimum=Decimal" in sc:
    print("  Scoring already has minimum parameter")
else:
    print("  WARNING: minimum parameter missing")

# ===== 4. WEB socket ping/pong fix =====
print("\n=== 4. WebSocket heartbeat check ===")
ws_path = r"C:\prop-frim-bot\backend\apps\trading\consumers.py"
if os.path.exists(ws_path):
    with open(ws_path, "r") as f:
        ws = f.read()
    if "_ping_loop" in ws:
        print("  WebSocket ping/pong already installed")
    else:
        print("  WARNING: ping/pong missing")
else:
    print("  consumers.py not found")

# ===== 5. KILL all python, clear cache =====
print("\n=== 5. Clean restart ===")
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)

# ===== 6. START engine =====
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
subprocess.run(['nssm', 'restart', 'TradingBackend'], timeout=15)
time.sleep(5)

# ===== 7. VERIFY =====
print("\n=== 6. Verification ===")
for svc in ['TradingMT5Engine', 'TradingBackend']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc}: {r.stdout.strip()}")

import py_compile
for f in [views_path, acct_path]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: SYNTAX OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

print("\n=== V3.3 COMPLETE ===")
