
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(p) as f:
    content = f.read()

# Replace the bad lifecycle block
bad = '# v2.2: Lifecycle states based on score tier\n                                            lifecycle_status = "WATCHLIST"\n                                            if score.total >= Decimal("85"):\n                                                lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring\n                                            elif score.total >= Decimal("70"):\n                                                lifecycle_status = "EXECUTION_READY"\n                                            elif score.total >= Decimal("55"):\n                                                lifecycle_status = "ACTIVE_MONITORING"\n                                            else:\n                                                lifecycle_status = "WATCHLIST"'

good = '# v2.2: Lifecycle states\n                                            lifecycle_status = "WATCHLIST"\n                                            if score.total >= Decimal("85"):\n                                                lifecycle_status = "EXECUTION_READY"\n                                            elif score.total >= Decimal("70"):\n                                                lifecycle_status = "EXECUTION_READY"\n                                            elif score.total >= Decimal("55"):\n                                                lifecycle_status = "ACTIVE_MONITORING"\n                                            else:\n                                                lifecycle_status = "WATCHLIST"'

if bad in content:
    content = content.replace(bad, good)
    with open(p, "w") as f:
        f.write(content)
    print("Lifecycle block fixed!")
else:
    print("Bad pattern not found!")
    if "# v2.2: Lifecycle" in content:
        print("Found lifecycle comment")
        idx = content.find("# v2.2: Lifecycle")
        print(repr(content[idx:idx+500]))
    else:
        print("Lifecycle comment not found!")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
