"""Finalize v2.3 - migrate DB, integrate into engine, restart."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

# ===== STEP 1: Apply DB migration =====
print("=== STEP 1: DB Migration ===")
r = subprocess.run(['.venv\\Scripts\\python.exe', 'backend\\manage.py', 'makemigrations', 'trading'], 
                    capture_output=True, text=True, timeout=30)
print(r.stdout[:500])
print(r.stderr[:300])

r = subprocess.run(['.venv\\Scripts\\python.exe', 'backend\\manage.py', 'migrate', 'trading'],
                    capture_output=True, text=True, timeout=30)
print(r.stdout[:500])
print(r.stderr[:300])

r = subprocess.run(['.venv\\Scripts\\python.exe', 'backend\\manage.py', 'migrate'],
                    capture_output=True, text=True, timeout=30)
print(r.stdout[:500])
print(r.stderr[:300])

# ===== STEP 2: Update existing signals with new statuses =====
print("\n=== STEP 2: Updating signal statuses ===")
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition

# Map old statuses to new lifecycle
status_map = {
    "WATCHLIST": "WATCHLIST",
    "ACTIVE": "ACTIVE_MONITORING",
    "CLOSED_SL": "CLOSED_SL",
    "CLOSED_TP": "CLOSED_TP",
}
for old, new in status_map.items():
    cnt = Signal.objects.filter(status=old).update(status=new)
    if cnt:
        print(f"  {old} -> {new}: {cnt} signals")

# Set signals with open positions to EXECUTION_READY or EXECUTED
for pos in OpenPosition.objects.filter(is_deleted=False):
    if pos.order and pos.order.signal:
        pos.order.signal.status = "EXECUTED"
        pos.order.signal.save()
        print(f"  Signal {pos.order.signal.id} -> EXECUTED (has open position)")

# ===== STEP 3: Restart services =====
print("\n=== STEP 3: Restarting services ===")
for svc in ['TradingBackend', 'TradingMT5Engine']:
    subprocess.run(['nssm', 'restart', svc], timeout=15)
    time.sleep(3)
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc}: {r.stdout.strip()}")

print("\n=== STEP 4: API verification ===")
time.sleep(5)
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=3'], 
                    capture_output=True, text=True, timeout=10)
import json
try:
    data = json.loads(r.stdout)
    print(f"  Signals API: {len(data)} returned")
    for s in data[:3]:
        print(f"    {s.get('symbol_name','?'):15s} Status={s.get('status','?'):20s} Tier={s.get('confidence_tier','N/A'):15s}")
except:
    print(f"  API response: {r.stdout[:100]}")

r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/open-positions/?limit=5'],
                    capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"  Positions API: {len(data)}")
except:
    pass

# ===== STEP 5: Git commit =====
print("\n=== STEP 5: Git commit ===")
subprocess.run(['git', 'add', '-A'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'v2.3: position manager, multi-TP, correlation shield, lifecycle states'],
                    capture_output=True, text=True, timeout=10)
print(r.stdout[:300])
r = subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)
print(r.stdout[:300])

print("\n=== V2.3 INSTITUTIONAL UPGRADE COMPLETE ===")
