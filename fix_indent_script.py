
import re

with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    content = f.read()

# Fix: the line "tier2 = score.total >= ..." lost its indentation
# Find it and add proper indentation
lines = content.split("\n")
fixed = False
for i, line in enumerate(lines):
    # Look for the line that starts with 'tier2 =' and has no leading whitespace (or very little)
    stripped = line.lstrip()
    if stripped.startswith("tier2 = score.total >= Decimal") and not line.startswith(" "):
        # This line lost its indentation - fix it
        # Find how much indentation the line before has
        if i > 0:
            prev_line = lines[i-1]
            indent = len(prev_line) - len(prev_line.lstrip())
            lines[i] = " " * indent + stripped
            fixed = True
            print(f"Fixed line {i}: added {indent} spaces indent")

if fixed:
    with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
        f.write("\n".join(lines))
    print("File written successfully!")
else:
    print("No fix needed or line not found!")
    # Debug: show tier2 lines
    for i, line in enumerate(lines):
        if "tier2" in line:
            print(f"  [{i}] repr: {repr(line)}")
