"""Fix IPC crash loop: wrap account_info in retry logic, handle IPC errors gracefully."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Fix 1: Wrap the account_info call in retry logic
old = "                info = client.account_info()"
new = """                # MT5 IPC retry: transient errors (-10004) should not crash the loop
                info = None
                for _retry in range(3):
                    try:
                        info = client.account_info()
                        if info is not None:
                            break
                    except Exception as _ipc_err:
                        if _retry < 2:
                            import time as _t
                            _t.sleep(1)
                            continue
                        self.stderr.write(f"MT5 IPC error (retry {_retry+1}/3): {_ipc_err}")
                if info is None:
                    self.stderr.write("MT5 account_info failed after 3 retries, continuing cycle...")
                    continue"""

if old in eng:
    eng = eng.replace(old, new, 1)
    print("IPC retry logic added around account_info()")
else:
    print("account_info pattern not found - checking...")
    cnt = eng.count("info = client.account_info()")
    print(f"  Found {cnt} occurrences")

with open(eng_path, "w") as f:
    f.write(eng)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("Syntax: OK")
except Exception as e:
    print(f"Syntax ERROR: {e}")
