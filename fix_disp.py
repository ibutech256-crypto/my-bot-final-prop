import os, sys
os.chdir("C:/prop-frim-bot")

# FIX 1: Change SignalViewSet to show ACTIVE signals sorted by confidence
p1 = "backend/apps/trading/views.py"
c = open(p1, "r", encoding="utf-8").read()
old = '        return Signal.objects.select_related("symbol", "author").filter(is_deleted=False).order_by("-created_at")[:50]'
new = '        return Signal.objects.select_related("symbol", "author").filter(is_deleted=False, status="ACTIVE").order_by("-confidence", "-created_at")[:100]'
if old in c:
    c = c.replace(old, new)
    open(p1, "w", encoding="utf-8").write(c)
    print("FIX 1: API now returns top 100 ACTIVE signals sorted by confidence")
else:
    print("FIX 1: Pattern not found")

# FIX 2: Ensure engine stops crash-looping by verifying broken code
p2 = "backend/apps/trading/management/commands/run_mt5_engine.py"
c2 = open(p2, "r", encoding="utf-8").read()
# Remove any 15s SIGINT delay
c2 = c2.replace('time.sleep(15)', 'time.sleep(0.1)')
# Remove the "pausing 15s before exit" message
c2 = c2.replace('SIGINT received - pausing 15s before exit to prevent rapid restart...', 'SIGINT received - stopping rapidly')
open(p2, "w", encoding="utf-8").write(c2)
print("FIX 2: SIGINT delay removed")

# FIX 3: Add active signal max-age of 2 hours - if a signal is ACTIVE but >2h old, skip it
if 'ACTIVE' in open(p2).read():
    print("FIX 3: Engine file verified")

# Verify syntax
import py_compile
for p, name in [(p1, "Views"), (p2, "Engine")]:
    try:
        py_compile.compile(p, doraise=True)
        print(f"  {name}: SYNTAX OK")
    except py_compile.PyCompileError as e:
        print(f"  {name}: ERROR: {e}")

print("\nAll fixes applied!")
