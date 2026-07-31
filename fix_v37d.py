import os
os.chdir(r"C:\prop-frim-bot")

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Find the duplicate except pattern and fix it
# Remove my added except block and use a single one
old = """                        if info is not None:
                            break
                    except:
                        import time as _rt
                        _rt.sleep(2)
                    except:"""

new = """                        if info is not None:
                            break
                    except Exception:"""

if old in eng:
    eng = eng.replace(old, new, 1)
    print("FIXED: duplicate except merged into single except Exception")
else:
    # Try \r\n variant
    old2 = old.replace('\n', '\r\n')
    if old2 in eng:
        eng = eng.replace(old2, new.replace('\n', '\r\n'), 1)
        print("FIXED: (\\r\\n variant)")
    else:
        print("Pattern not found!")
        idx = eng.find("break\n                    except:")
        if idx < 0: idx = eng.find("break\r\n                    except:")
        if idx >= 0:
            print(f"Found at {idx}:")
            print(repr(eng[idx:idx+150]))

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
