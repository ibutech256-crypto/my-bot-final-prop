import os, sys
os.chdir("C:/prop-frim-bot")

# Check views.py was fixed
lines = open("backend/apps/trading/views.py", "r").readlines()
for i, l in enumerate(lines):
    if "order_by" in l and "Signal" in l:
        print(f"Views.py L{i+1}: {l.rstrip()}")

# Check if the engine SIGINT delay was removed
c = open("backend/apps/trading/management/commands/run_mt5_engine.py", "r").read()
if "time.sleep(15)" in c:
    print("WARNING: SIGINT 15s delay still present!")
else:
    print("OK: SIGINT delay removed")

# Quick DB check
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, "C:/prop-frim-bot/backend")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order

print(f"\nACTIVE signals: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Open Positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
print(f"Orders: {Order.objects.count()}")

# Check last engine log for execution activity
log = "logs/TradingMT5Engine.log"
if os.path.exists(log):
    with open(log, "rb") as f:
        f.seek(max(0, os.fstat(f.fileno()).st_size - 10000))
        data = f.read().decode("latin-1")
    lines = [l for l in data.split("\n") if l.strip()]
    for term in ["TRADE EXECUTED", "EXECUTING CRT", "BLOCKED", "REJECTED", "loop stopping"]:
        matches = [l for l in lines if term in l]
        if matches:
            print(f"\n{term}: {len(matches)}")
            for m in matches[-2:]:
                print(f"  {m[:150]}")

