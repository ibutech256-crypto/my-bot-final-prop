
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()

# Fix: else: body should be indent 52, not 48
old = "                                                else:\n                                                lifecycle_status = \"WATCHLIST\""
new = "                                                else:\n                                                    lifecycle_status = \"WATCHLIST\""

if old in content:
    content = content.replace(old, new)
    open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(content)
    print("Fixed else body indentation!")
else:
    print("Pattern not found!")
    # Show the exact content around else
    idx = content.find("else:")
    if idx >= 0:
        print(repr(content[idx:idx+100]))

# Check syntax
import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("Syntax: OK!")
except py_compile.PyCompileError as e:
    print(f"Syntax ERROR: {e}")
