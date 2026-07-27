
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p, "r").readlines()

# Fix blank lines with stray spaces (indent=1)
for i, line in enumerate(lines):
    stripped = line.strip()
    ai = len(line) - len(line.lstrip())
    if ai == 1 and not stripped:
        lines[i] = "\n"
        print(f"Fixed blank line {i+1}")

# Also check for the lifecycle if blocks - make sure body lines are at indent 48
prev_was_if = False
for i, line in enumerate(lines):
    stripped = line.strip()
    ai = len(line) - len(line.lstrip())
    if stripped.startswith("lifecycle_status = "):
        # Should follow the if/elif/else indent
        if "EXECUTION_READY" in stripped or "ACTIVE_MONITORING" in stripped or ("WATCHLIST" in stripped and i > 0 and lines[i-1].strip() == "else:"):
            pass  # already correct
        # Fix lines that might have wrong indent

open(p, "w").writelines(lines)
print(f"Total lines: {len(lines)}")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
