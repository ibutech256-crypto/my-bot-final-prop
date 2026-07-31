import os
os.chdir(r"C:\prop-frim-bot")

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# The exact line is: "info = client.account_info()"
# Need to replace the block from that line through the save
old = '                info = client.account_info()\n                        if info is not None:\n                            break'

new = '                info = client.account_info()\n                        if info is not None:\n                            break\n                    except:\n                        import time as _rt\n                        _rt.sleep(2)'

if old in eng:
    eng = eng.replace(old, new, 1)
    print("FIX: IPC retry added")
else:
    print("Pattern not found!")
    idx = eng.find("info = client.account_info()")
    if idx >= 0:
        print(eng[idx:idx+150])

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
