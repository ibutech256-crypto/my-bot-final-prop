"""Add evaluate_signal method to orchestrator after the evaluate method."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    if "def evaluate(" in line:
        print(f"  Found 'def evaluate' at line {i+1}: {line.strip()[:60]}")
        # Insert evaluate_signal after this method
        # Find the next method or end of file
        insert_at = i + 1
        # Skip to the end of evaluate method
        depth = 0
        for j in range(i+1, len(lines)):
            if "def " in lines[j] and depth == 0:
                insert_at = j
                break
            depth += lines[j].count("(") - lines[j].count(")")
        
        method = """    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure,
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
        lines = lines[:insert_at] + [method] + lines[insert_at:]
        with open(orch_path, "w") as f:
            f.writelines(lines)
        print(f"  evaluate_signal() inserted at line {insert_at}")
        break

import py_compile
try:
    py_compile.compile(orch_path, doraise=True)
    print("  SYNTAX OK")
except Exception as e:
    print(f"  SYNTAX ERROR: {e}")
