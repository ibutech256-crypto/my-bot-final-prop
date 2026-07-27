"""Fix the health endpoint URL route - it's outside urlpatterns list."""
import os, sys, signal, subprocess, time
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

urls_path = r"C:\prop-frim-bot\backend\apps\common\api_urls.py"
with open(urls_path, "r") as f:
    content = f.read()

# The mt5-health route was appended AFTER urlpatterns, not inside it
# Need to move it inside
old = """urlpatterns=[path("auth/token/",TokenObtainPairView.as_view()),path("auth/token/refresh/",TokenRefreshView.as_view()),path("auth/token/verify/",TokenVerifyView.as_view()),path("",include(router.urls))]
path('mt5-health/', MT5HealthView.as_view(), name='mt5-health'),"""

new = """urlpatterns=[path("auth/token/",TokenObtainPairView.as_view()),path("auth/token/refresh/",TokenRefreshView.as_view()),path("auth/token/verify/",TokenVerifyView.as_view()),path("mt5-health/",MT5HealthView.as_view(),name="mt5-health"),path("",include(router.urls))]"""

if old in content:
    content = content.replace(old, new)
    with open(urls_path, "w") as f:
        f.write(content)
    print("URL route fixed - mt5-health now inside urlpatterns")
else:
    print("Pattern not found. Checking actual state...")
    idx = content.find("mt5-health")
    if idx >= 0:
        print(f"Found mt5-health at {idx}:")
        print(content[idx-30:idx+80])
    else:
        print("mt5-health not found at all!")

import py_compile
try:
    py_compile.compile(urls_path, doraise=True)
    print("Syntax: OK")
except Exception as e:
    print(f"Syntax ERROR: {e}")

# Restart backend
subprocess.run(['nssm', 'restart', 'TradingBackend'], timeout=15)
time.sleep(5)
r = subprocess.run(['nssm', 'status', 'TradingBackend'], capture_output=True, text=True, timeout=5)
print(f"Backend: {r.stdout.strip()}")

# Test endpoint
time.sleep(3)
import json
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/mt5-health/'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"\nHealth: MT5={data.get('mt5','?')} Balance=${data.get('balance',0)} Positions={data.get('positions',0)}")
except:
    print(f"Health response: {r.stdout[:200]}")
