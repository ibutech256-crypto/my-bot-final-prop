import re
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    c = f.read()
old = 'except KeyboardInterrupt:\n                self.stdout.write("MT5 Engine loop stopping...")\n                break'
new = 'except KeyboardInterrupt:\n                self.stdout.write("MT5 Engine interrupted, continuing...")\n                continue'
if old in c:
    c = c.replace(old, new)
    with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "w") as f:
        f.write(c)
    print("FIXED: break -> continue")
else:
    print("Pattern not found!")
    idx = c.find("KeyboardInterrupt")
    if idx >= 0:
        print("Found KB at", idx)
        print(repr(c[idx:idx+200]))

