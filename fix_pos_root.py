"""Fix the root cause: engine's OpenPosition.get() fails with duplicates.
Replace get() with filter().first() or update_or_create()."""
import os, sys, signal, py_compile
signal.signal(signal.SIGINT, signal.SIG_IGN)

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Count how many times get() is used on OpenPosition
import re
gets = re.findall(r'OpenPosition\.objects\.get\(', eng)
print(f"OpenPosition.objects.get() calls: {len(gets)}")

# Replace all OpenPosition.objects.get() with OpenPosition.objects.filter().first()
# This prevents the "get() returned more than one" crash
old = "OpenPosition.objects.get("
new = "OpenPosition.objects.filter("
# We need to be careful - replace only the ones that end with .get( 
# Actually let me find the exact patterns

# Pattern 1: sym_obj = TradingSymbol.objects.get_or_create
# Pattern 2: OpenPosition.objects.update_or_create (already safe)
# Pattern 3: OpenPosition.objects.get(account=account, broker_ticket=ticket) -> .filter(...).first()

# Find only OpenPosition.objects.get( lines
for i, line in enumerate(eng.split('\n')):
    if 'OpenPosition.objects.get(' in line and 'update_or_create' not in line and 'get_or_create' not in line:
        print(f"  Line {i+1}: {line.strip()[:100]}")

# Replace all unsafe OpenPosition.objects.get() with filter().first()
# Only when it's a standalone get (not get_or_create or update_or_create)
import re
pattern = r'OpenPosition\.objects\.get\(([^)]+)\)'
matches = list(re.finditer(pattern, eng))
print(f"\nOpenPosition.objects.get() instances: {len(matches)}")

for m in matches:
    # Check if this is part of get_or_create or update_or_create
    start = max(0, m.start() - 30)
    context = eng[start:m.end()+10]
    if 'get_or_create' not in context and 'update_or_create' not in context and 'filter' not in context:
        args = m.group(1)
        replacement = f'OpenPosition.objects.filter({args}).first()'
        eng = eng[:m.start()] + replacement + eng[m.end():]
        print(f"  Fixed: OpenPosition.objects.get() -> filter().first()")

with open(eng_path, "w") as f:
    f.write(eng)

try:
    py_compile.compile(eng_path, doraise=True)
    print("\nSyntax: OK")
except Exception as e:
    print(f"\nSyntax ERROR: {e}")

print("\nDONE")
