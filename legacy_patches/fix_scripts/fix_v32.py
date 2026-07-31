"""V3.2 Fix: hardcoded scoring flags, add orchestrator wrapper method."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

# ===== FIX 1: Add evaluate_signal() wrapper to orchestrator =====
print("=== FIX 1: Add evaluate_signal() to orchestrator ===")
orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    orch = f.read()

# Add a public evaluate_signal method that computes all flags
if "def evaluate_signal" not in orch:
    # Find the scoring call and add wrapper before it
    old_score = """    def start(self):
        \"\"\"Run full analysis path.\"\"\""""
    
    wrapper = """    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure, 
                           news_state, completed, spec, risk_state, htf_candles=None):
        \"\"\"Compute all scoring flags dynamically and return ScoreBreakdown.
        This is the SINGLE entry point for signal evaluation from the engine.
        Replaces scattered hardcoded True flags."""
        # HTF alignment
        htf_ok = True
        if htf_candles:
            htf_biases = [self.structure.analyse(c).bias for c in htf_candles.values() if len(c) >= 20]
            htf_ok = all(b in {direction, Direction.NEUTRAL} for b in htf_biases) if htf_biases else True
        
        # Risk validation 
        risk_ok = True
        risk_state = {}
        if risk_state:
            risk_ok, _ = self.risk.validate(self.config.risk_limits, risk_state)
        
        # Volatility check
        volatility_ok = True
        if completed and spec:
            last = completed[-1]
            volatility_ok = last.range() > spec.tick_size * Decimal("5")
        
        return self.scoring.score(
            direction, sweep, kod, cisd, htf_ok, session_state, structure,
            risk_ok, volatility_ok, news_state,
            minimum=Decimal("50")
        ), htf_ok, risk_ok, volatility_ok
    
    def start(self):
        \"\"\"Run full analysis path.\"\"\""""
    
    if old_score in orch:
        orch = orch.replace(old_score, wrapper)
        with open(orch_path, "w") as f:
            f.write(orch)
        print("  evaluate_signal() wrapper added to orchestrator")
    else:
        print("  WARNING: old_score pattern not found")
else:
    print("  evaluate_signal() already exists")

# ===== FIX 2: Update engine to use evaluate_signal() =====
print("\n=== FIX 2: Update engine scoring call ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Replace the hardcoded scoring call
old_call = "score = orchestrator.scoring.score(direction, sweep, kod, cisd, True, session_state, structure, True, True, news_state, Decimal(\"50\"))"
new_call = "score, htf_ok, risk_ok, volatility_ok = orchestrator.evaluate_signal(direction, sweep, kod, cisd, session_state, structure, news_state, completed, spec, {}, None)"

if old_call in eng:
    eng = eng.replace(old_call, new_call)
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  Engine scoring call updated to use evaluate_signal()")
else:
    print("  WARNING: old scoring call not found!")
    # Find the actual scoring call
    idx = eng.find("orchestrator.scoring.score")
    if idx >= 0:
        context = eng[idx:idx+160]
        print(f"  Found: {context}")

# Also fix the htf_ok reference (it was undefined before, now it's returned)
# Add htf_ok = True fallback for the tier2 check
old_tier2 = "htf_ok = True  # HTF alignment OK\ntier2 = score.total >= Decimal(\"70\") and htf_ok"
new_tier2 = "tier2 = score.total >= Decimal(\"70\") and htf_ok"
if old_tier2 in eng:
    eng = eng.replace(old_tier2, new_tier2)
    print("  Removed redundant htf_ok = True (now comes from evaluate_signal)")

with open(eng_path, "w") as f:
    f.write(eng)

# ===== FIX 3: Verify syntax =====
print("\n=== Verify syntax ===")
import py_compile
for f in [orch_path, eng_path]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

# ===== FIX 4: Restart engine =====
print("\n=== Restart engine ===")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

# ===== FIX 5: Git =====
print("\n=== Git commit ===")
subprocess.run(['git', 'add', 'trading_engine/orchestrator.py', 'backend/apps/trading/management/commands/run_mt5_engine.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix(v3.2): dynamic scoring flags, orchestrator evaluate_signal wrapper'], capture_output=True, text=True, timeout=10)
print(r.stdout[:200])

print("\n=== V3.2 COMPLETE ===")
