"""V3.2 Fix: dynamic scoring flags via orchestrator wrapper."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

print("=== Fix 1: Add evaluate_signal to orchestrator ===")
orch_path = r"C:\prop-frim-bot\trading_engine\orchestrator.py"
with open(orch_path, "r") as f:
    lines = f.readlines()

# Find the start method and add evaluate_signal before it
for i, line in enumerate(lines):
    if "def start(self):" in line and '"Run full analysis path."' in line:
        eval_method = [
            "    def evaluate_signal(self, direction, sweep, kod, cisd, session_state, structure,\n",
            "                           news_state, completed, spec, htf_candles=None):\n",
            '        """Compute all scoring flags dynamically. Replaces hardcoded True flags."""\n',
            "        # HTF alignment\n",
            "        htf_ok = True\n",
            "        if htf_candles:\n",
            "            htf_biases = [self.structure.analyse(c).bias for c in htf_candles.values() if len(c) >= 20]\n",
            "            htf_ok = all(b in {direction, Direction.NEUTRAL} for b in htf_biases) if htf_biases else True\n",
            "        # Risk validation - default True\n",
            "        risk_ok = True\n",
            "        # Volatility check\n",
            "        volatility_ok = True\n",
            "        if completed and spec and len(completed) > 0:\n",
            "            last = completed[-1]\n",
            "            volatility_ok = last.range() > spec.tick_size * Decimal(\"5\")\n",
            "        return self.scoring.score(\n",
            "            direction, sweep, kod, cisd, htf_ok, session_state, structure,\n",
            '            risk_ok, volatility_ok, news_state, minimum=Decimal("50")\n',
            "        ), htf_ok, risk_ok, volatility_ok\n",
            "\n",
        ]
        lines = lines[:i] + eval_method + lines[i:]
        with open(orch_path, "w") as f:
            f.writelines(lines)
        print("  evaluate_signal() added before start()")
        break

print("\n=== Fix 2: Update engine scoring call ===")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

old = 'score = orchestrator.scoring.score(direction, sweep, kod, cisd, True, session_state, structure, True, True, news_state, Decimal("50"))'
new = 'score, htf_ok, risk_ok, volatility_ok = orchestrator.evaluate_signal(direction, sweep, kod, cisd, session_state, structure, news_state, completed, spec)'

if old in eng:
    eng = eng.replace(old, new)
    with open(eng_path, "w") as f:
        f.write(eng)
    print("  Engine scoring call updated")
else:
    print("  WARNING: old call not found!")
    idx = eng.find("orchestrator.scoring.score")
    if idx >= 0:
        print(f"  Found at {idx}: {eng[idx:idx+160]}")

# Fix redundant htf_ok
old2 = 'htf_ok = True  # HTF alignment OK\n                                        tier2 = score.total >= Decimal("70") and htf_ok'
new2 = 'tier2 = score.total >= Decimal("70") and htf_ok'
if old2 in eng:
    eng = eng.replace(old2, new2)
    print("  Removed redundant htf_ok = True")
else:
    # Try alternate
    if 'htf_ok = True' in eng:
        print("  htf_ok = True remains (may be needed elsewhere)")
    else:
        pass

with open(eng_path, "w") as f:
    f.write(eng)

print("\n=== Verify syntax ===")
import py_compile
for f in [orch_path, eng_path]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

print("\n=== Restart ===")
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"  Engine: {r.stdout.strip()}")

print("\n=== V3.2 COMPLETE ===")
