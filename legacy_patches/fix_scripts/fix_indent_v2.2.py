
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()
lines = content.split("\n")
fixed = False
for i, line in enumerate(lines):
    if "# v2.2: Lifecycle states based on score tier" in line:
        # Current indent is 44 spaces, needs to be 48 (same as the lines around it)
        for j in range(i, i+10):
            if j >= len(lines):
                break
            stripped = lines[j].lstrip()
            if not stripped:
                continue
            current_indent = len(lines[j]) - len(stripped)
            # If indent is 44, change to 48
            if current_indent == 44:
                lines[j] = " " * 48 + stripped
                print(f"Fixed line {j+1}: indent 44->48")
                fixed = True
        break

if fixed:
    open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write("\n".join(lines))
    print("File saved!")
else:
    print("No fix needed")
