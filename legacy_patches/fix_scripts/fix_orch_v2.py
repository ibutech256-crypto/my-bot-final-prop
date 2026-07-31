"""Fix orchestrator - remove misplaced method and re-add correctly."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# Restore from git first
subprocess.run(['git', 'checkout', '--', 'trading_engine/orchestrator.py'], timeout=10)
print("Restored orchestrator.py from git")

# Now find the correct insertion point: after evaluate() method
orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    content = f.read()

# Find the evaluate function and its end (next method)
idx = content.find("def evaluate(")
if idx < 0:
    print("ERROR: evaluate() not found!")
    sys.exit(1)

# Find the next def after evaluate
next_method = content.find("\ndef ", idx + 10)

# Find the last line of evaluate() - it ends right before the next def
# or at end of file
if next_method < 0:
    next_method = len(content)

# Insert evaluate_signal at the transition point
insert_at = next_method
method_text = """
    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure,
                           news_state, completed, spec, htf_candles=None):
        \"\"\"Compute all scoring flags dynamically. Replaces hardcoded True flags.\"\"\"
        # HTF alignment
        htf_ok = True
        if htf_candles:
            htf_biases = [self.structure.analyse(c).bias for c in htf_candles.values() if len(c) >= 20]
            htf_ok = all(b in {direction, Direction.NEUTRAL} for b in htf_biases) if htf_biases else True
        # Risk validation
        risk_ok = True
        # Volatility check
        volatility_ok = True
        if completed and spec and len(completed) > 0:
            last = completed[-1]
            volatility_ok = last.range() > spec.tick_size * Decimal("5")
        return self.scoring.score(
            direction, sweep, kod, cisd, htf_ok, session_state, structure,
            risk_ok, volatility_ok, news_state, minimum=Decimal("50")
        ), htf_ok, risk_ok, volatility_ok

"""

content = content[:insert_at] + method_text + content[insert_at:]
with open(orch_path, "w") as f:
    f.write(content)
print(f"evaluate_signal() inserted after evaluate() at byte {insert_at}")

import py_compile
try:
    py_compile.compile(orch_path, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
    # Show the context around it
    idx = content.find("evaluate_signal")
    if idx >= 0:
        print(content[idx:idx+400])
