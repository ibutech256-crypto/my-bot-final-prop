import os
os.chdir("C:/prop-frim-bot")
p = "backend/apps/trading/management/commands/run_mt5_engine.py"
c = open(p, "r", encoding="utf-8").read()

# Add auto-expiry of stale ACTIVE signals
old = "        while True:"
new = """        # Auto-expire stale ACTIVE signals (>4 hours old)
        _cutoff = django_tz.now() - django_tz.timedelta(hours=4)
        _expired = Signal.objects.filter(status="ACTIVE", created_at__lt=_cutoff).update(status="CLOSED_SL")
        if _expired:
            self.stdout.write(f"AUTO-EXPIRED {_expired} stale ACTIVE signals (>4h)")
        
        while True:"""

if old in c:
    c = c.replace(old, new, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("AUTO-EXPIRY: Added stale signal purging before main loop")
else:
    print("Pattern not found")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")
