
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    lines = f.readlines()

print("Lines 524-535:")
for i, line in enumerate(lines[523:535], start=524):
    print(f"  {i}: {repr(line[:100])}")

# Fix the else body - line 526 should be "lifecycle_status = "WATCHLIST"" at indent 52
# Currently it might be empty or wrong indent
for i in range(len(lines)):
    if 'else:' in lines[i] and i+1 < len(lines):
        next_line = lines[i+1].lstrip()
        # If next line after else: is not properly indented body
        current_indent = len(lines[i+1]) - len(lines[i+1].lstrip())
        if current_indent < 52 and next_line and not next_line.startswith("#"):
            lines[i+1] = "                                                    " + next_line  # 52 spaces
            print(f"Fixed line {i+2}: indent->52")
        elif not next_line.strip():
            # Empty line after else: - insert the body
            # Find the lifecycle_status line that should be here
            # It might have been moved
            pass

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
    f.writelines(lines)

# Check syntax
import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("Syntax: OK!")
except py_compile.PyCompileError as e:
    print(f"Syntax ERROR: {e}")
