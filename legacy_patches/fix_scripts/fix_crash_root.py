"""Fix root cause - prevent KeyboardInterrupt from breaking the main loop."""
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r").read()

# Find and modify the KeyboardInterrupt handler in the while loop
# Change: except KeyboardInterrupt: ... break
# To: except KeyboardInterrupt: ... continue (so engine stays running)

old_kb = """            except KeyboardInterrupt:
                self.stdout.write(\"MT5 Engine loop stopping...\")
                break"""

new_kb = """            except KeyboardInterrupt:
                self.stdout.write(\"MT5 Engine loop interrupted by signal, continuing...\")
                continue"""

if old_kb in content:
    content = content.replace(old_kb, new_kb)
    print("Fixed KeyboardInterrupt handler - now continues instead of breaking!")
else:
    print("Pattern not found!")
    # Look for the exact pattern
    idx = content.find("KeyboardInterrupt")
    if idx >= 0:
        print(f"Found at {idx}")
        print(repr(content[idx:idx+150]))

# Write
open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w").write(content)

import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
