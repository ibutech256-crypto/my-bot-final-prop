
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p, "r").readlines()
for i, line in enumerate(lines):
    if "NEW SIGNAL RECORDED" in line and i > 0:
        prev = lines[i-1]
        indent = len(prev) - len(prev.lstrip())
        lines[i] = " " * indent + line.lstrip() + "\n"
        print(f"Fixed line {i+1}: indent={indent}")
        break
open(p, "w").writelines(lines)
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
