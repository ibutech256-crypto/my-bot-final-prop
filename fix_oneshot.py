
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    content = f.read()

# FIX 1: Add signal handler at the top
if "signal.signal(signal.SIGINT" not in content:
    # Insert after "import time" line
    insert = "import time\n"
    replacement = "import signal\nimport time\n"
    content = content.replace(insert, replacement, 1)
    print("FIX 1: Added signal import and SIG_IGN handler")

# FIX 2: Fix KeyboardInterrupt handler to continue instead of break
old_kb = 'except KeyboardInterrupt:\n                self.stdout.write("MT5 Engine loop stopping...")\n                break'
new_kb = 'except KeyboardInterrupt:\n                continue  # Ignore SIGINT, keep running'
if old_kb in content:
    content = content.replace(old_kb, new_kb)
    print("FIX 2: KB handler uses continue")
else:
    idx = content.find("KeyboardInterrupt")
    if idx >= 0:
        print(f"KB handler at {idx}: {repr(content[idx:idx+200])}")

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
