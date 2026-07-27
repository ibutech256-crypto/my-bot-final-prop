import os
os.chdir("C:/prop-frim-bot")
p = "backend/apps/trading/management/commands/run_mt5_engine.py"
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Fix line 458 (index 457): remove extra indentation
old_line = '                                            htf_ok = True  # HTF alignment, checked via htf_biases later\n'
new_line = '                                    htf_ok = True  # HTF alignment, checked via htf_biases later\n'

if lines[457] == old_line:
    lines[457] = new_line
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("FIXED: Corrected indentation on line 458")
else:
    print(f"Expected: {repr(old_line)}")
    print(f"Found:    {repr(lines[457])}")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
