"""Fix lifecycle block indent with \\r\\n line endings."""
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "rb").read()

# Pattern with \r\n endings
wrong = b'                                            # v2.2: Lifecycle states based on score tier\r\n                                        lifecycle_status = "WATCHLIST"\r\n                                        if score.total >= Decimal("85"):\r\n                                            lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring\r\n                                        elif score.total >= Decimal("70"):\r\n                                            lifecycle_status = "EXECUTION_READY"\r\n                                        elif score.total >= Decimal("55"):\r\n                                            lifecycle_status = "ACTIVE_MONITORING"\r\n                                        else:\r\n                                            lifecycle_status = "WATCHLIST"\r\n                                        sig = Signal.objects.create('

correct = b'                                            # v2.2: Lifecycle states based on score tier\r\n                                            lifecycle_status = "WATCHLIST"\r\n                                            if score.total >= Decimal("85"):\r\n                                                lifecycle_status = "EXECUTION_READY"  # Priority - skip monitoring\r\n                                            elif score.total >= Decimal("70"):\r\n                                                lifecycle_status = "EXECUTION_READY"\r\n                                            elif score.total >= Decimal("55"):\r\n                                                lifecycle_status = "ACTIVE_MONITORING"\r\n                                            else:\r\n                                                lifecycle_status = "WATCHLIST"\r\n                                            sig = Signal.objects.create('

if wrong in content:
    content = content.replace(wrong, correct)
    open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "wb").write(content)
    print("Fixed lifecycle block indent (40->44)!")
else:
    print("Pattern not found!")
    idx = content.find(b"Lifecycle states based on score tier")
    if idx >= 0:
        print("Found at", idx)
        print(repr(content[idx:idx+450]))

# Check syntax
import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
