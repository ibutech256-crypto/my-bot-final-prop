
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p).read().split("\n")
print(f"Total lines: {len(lines)}")

# Fix line 540 - or find the offending indentation
for i, line in enumerate(lines):
    if "NEW SIGNAL RECORDED" in line:
        print(f"Line {i+1}: indent={len(line)-len(line.lstrip())} text={line[:80]}")
        # Fix indentation to match surrounding code
        if i > 0:
            prev = lines[i-1]
            prev_indent = len(prev) - len(prev.lstrip())
            lines[i] = " " * prev_indent + line.lstrip()
            print(f"  Fixed to indent {prev_indent}")
            break

open(p, "w").write("\n".join(lines))
print("File written")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
