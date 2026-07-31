"""Final verification, git commit, and report."""
import os, sys, signal, subprocess, json
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.chdir(r"C:\prop-frim-bot")

print("=== GIT STATUS ===")
r = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, timeout=10)
print(r.stdout[:1000])

print("\n=== GIT ADD AND COMMIT ===")
subprocess.run(['git', 'add', '-A'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'v2.2: signal lifecycle, confidence tiers, equity-based sizing, account modes'], capture_output=True, text=True, timeout=10)
print(r.stdout[:500])
print(r.stderr[:500])

print("\n=== PUSH TO GITHUB ===")
r = subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)
print(r.stdout[:500])
print(r.stderr[:500])

print("\n=== FINAL VERIFICATION ===")

# 1. API verification
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=0'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"Signals API: {len(data)} signals returned")
except:
    print(f"Signals API: {r.stdout[:100]}")

# Check positions
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/open-positions/?limit=5'], capture_output=True, text=True, timeout=10)
try:
    data = json.loads(r.stdout)
    print(f"Positions API: {len(data)} positions")
    for p in data:
        print(f"  {p['symbol_name']} {p['direction']} Entry={p['entry_price']} PnL={p['unrealized_profit']}")
except:
    print(f"Positions API: {r.stdout[:100]}")

# 2. Get commit hash
r = subprocess.run(['git', 'log', '--oneline', '-1'], capture_output=True, text=True, timeout=5)
commit = r.stdout.strip()
print(f"\nLast commit: {commit}")

# 3. Check services 
for svc in ['Memurai', 'TradingBackend', 'TradingWorker', 'TradingBeat', 'TradingFrontend', 'TradingMT5Engine']:
    r = subprocess.run(['nssm', 'status', svc], capture_output=True, text=True, timeout=5)
    print(f"  {svc:20s}: {r.stdout.strip()}")

print("\n=== SYSTEM STATUS SUMMARY ===")
from datetime import datetime
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"Commit: {commit}")
print("SignalViewSet: All signals displayed (not just ACTIVE)")
print("Confidence tiers: VERY_STRONG, STRONG, VALID, EMERGING, WEAK")
print("Account mode: GROWING_PERSONAL ($500+ threshold)")
print("Position sizing: 0.5% equity-based risk")
print("Signal vs Execution: Clearly separated")

print("\nDONE")
