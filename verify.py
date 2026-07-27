"""Verify changes and restart services."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

# Verify the views change works
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

if "is_deleted=False, status=\"ACTIVE\"" in vc:
    print("STILL HAS status=ACTIVE filter!")
else:
    print("SignalViewSet filter removed correctly")

if "is_deleted=False).order_by" in vc:
    print("SignalViewSet shows ALL signals")

# Verify serializers
ser_path = r"C:\prop-frim-bot\backend\apps\trading\serializers.py"
with open(ser_path, "r") as f:
    sc = f.read()
if "confidence_tier" in sc:
    print("Confidence tier serializer present")

# Verify account manager
acct_path = r"C:\prop-frim-bot\trading_engine\account_manager.py"
with open(acct_path, "r") as f:
    ac = f.read()
if "risk_amount = equity * Decimal" in ac:
    print("Account manager: equity-based sizing present")

# Restart backend
print("\n=== Restarting services ===")
import subprocess
subprocess.run(['nssm', 'restart', 'TradingBackend'], timeout=15)
subprocess.run(['nssm', 'restart', 'TradingMT5Engine'], timeout=15)

print("Restart commands sent. Verifying in 10s...")

import time
time.sleep(10)

for svc in ['TradingBackend', 'TradingMT5Engine']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    status = r.stdout.strip()
    print(f"  {svc}: {status}")

# Test the API
print("\n=== API test ===")
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=5'], capture_output=True, text=True, timeout=10)
print(f"Signals API status: {r.returncode}")
if r.stdout:
    import json
    data = json.loads(r.stdout)
    print(f"  Returned {len(data)} signals")
    for s in data[:5]:
        tier = s.get('confidence_tier', 'N/A')
        print(f"  {s['symbol_name']:15s} Score={s['confidence']:>6s} Tier={tier:15s} Status={s['status']:20s}")

print("\nDONE")
