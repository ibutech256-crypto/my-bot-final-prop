import os
os.chdir(r"C:\prop-frim-bot")

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Fix: replace bare `except:` with `except Exception:`
eng = eng.replace('                    except:\n                        import time as _rt\n                        _rt.sleep(2)\n\n', '                    except Exception:\n                        import time as _rt\n                        _rt.sleep(2)\n\n')

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
    # Find the error line
    import re
    m = re.search(r'line (\d+)', str(e))
    if m:
        line_num = int(m.group(1))
        with open(eng_path) as f:
            lines = f.readlines()
        for i in range(max(0, line_num-3), min(len(lines), line_num+3)):
            print(f"  {i+1}: {lines[i][:100]}")
