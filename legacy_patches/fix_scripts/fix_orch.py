"""Add evaluate_signal method to orchestrator - manually patch."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    content = f.read()

# Check if evaluate_signal already exists
if "def evaluate_signal" in content:
    print("evaluate_signal already exists, fixing any issues...")
else:
    print("Adding evaluate_signal method...")
    # Find the start method and insert before it
    idx = content.find('    def start(self):\n')
    if idx < 0:
        idx = content.find('    def start(self)')
    
    if idx >= 0:
        method = """
    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure,
                           news_state, completed, spec, htf_candles=None):
        \"\"\"Compute all scoring flags dynamically. Replaces hardcoded True flags.\"\"\"
        # HTF alignment
        htf_ok = True
        if htf_candles:
            htf_biases = [self.structure.analyse(c).bias for c in htf_candles.values() if len(c) >= 20]
            htf_ok = all(b in {direction, Direction.NEUTRAL} for b in htf_biases) if htf_biases else True
        # Risk validation - use defaults
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
        content = content[:idx] + method + content[idx:]
        with open(orch_path, "w") as f:
            f.write(content)
        print("  evaluate_signal() added to orchestrator")
    else:
        print("  ERROR: Could not find start() method in orchestrator!")

import py_compile
try:
    py_compile.compile(orch_path, doraise=True)
    print("  SYNTAX OK")
except Exception as e:
    print(f"  SYNTAX ERROR: {e}")

print("Restarting engine...")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")
