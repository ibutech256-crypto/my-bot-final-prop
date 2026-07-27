import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
c = open(p).read()

# THE ONE-LINE FIX: replace the obsolete hardcoded cutoff with score.passed
old = 'is_high_conf = score.total >= Decimal("75")'
new = 'is_high_conf = score.passed'

if old in c:
    c = c.replace(old, new)
    open(p, "w").write(c)
    print("FIX APPLIED: is_high_conf = score.passed")
else:
    print("Pattern not found!")
    # Check what's actually there
    idx = c.find("is_high_conf = ")
    if idx >= 0:
        print("Found:", repr(c[idx:idx+60]))

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")

# Verify
c2 = open(p).read()
if "score.passed" in c2:
    print("VERIFIED: score.passed is in engine file")
