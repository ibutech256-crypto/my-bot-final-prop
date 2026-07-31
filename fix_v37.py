"""Final fix: add IPC retry logic to engine loop."""
import os, sys
os.chdir(r"C:\prop-frim-bot")

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Add retry wrapper around account_info()
old = "                info = client.account_info()\n                account.balance = Decimal(str(info[\"balance\"]))\n                account.equity = Decimal(str(info[\"equity\"]))\n                account.margin = Decimal(str(info[\"margin\"]))\n                account.save()"

new = """                # IPC-safe account_info with retry
                info = None
                for _retry_cnt in range(3):
                    try:
                        info = client.account_info()
                        if info is not None:
                            break
                    except:
                        pass
                    import time as _retry_time
                    _retry_time.sleep(2)
                if info is None:
                    import time as _retry_time
                    _retry_time.sleep(5)
                    continue
                account.balance = Decimal(str(info["balance"]))
                account.equity = Decimal(str(info["equity"]))
                account.margin = Decimal(str(info["margin"]))
                account.save()"""

if old in eng:
    eng = eng.replace(old, new, 1)
    print("FIX: IPC-safe account_info with retry (3 attempts, 2s apart)")
else:
    print("FIX: Pattern not found!")
    # Find what's there
    idx = eng.find("info = client.account_info()")
    if idx >= 0:
        print(f"Found at {idx}: {eng[idx:idx+80]}")

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
