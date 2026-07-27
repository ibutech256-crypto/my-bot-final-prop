"""Fix doubled indent - handle windows line endings."""
content = open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "rb").read()

# Find and fix the doubled indent
old = b'                                        else:\r\n                                            lifecycle_status = "WATCHLIST"\r\n                                                                                sig = Signal.objects.create('
new = b'                                        else:\r\n                                            lifecycle_status = "WATCHLIST"\r\n                                        sig = Signal.objects.create('

if old in content:
    content = content.replace(old, new)
    open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "wb").write(content)
    print("✅ Fixed doubled indent!")
else:
    print("⚠️ Pattern not found!")
    # Search for partial patterns
    if b'sig = Signal.objects.create' in content:
        print("Found 'sig = Signal.objects.create' in file")
        # Show context
        idx = content.find(b'sig = Signal.objects.create')
        print(f"At byte offset {idx}")
        print(repr(content[idx-100:idx+50]))

import py_compile
try:
    py_compile.compile(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", doraise=True)
    print("✅ SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"❌ SYNTAX ERROR: {e}")
