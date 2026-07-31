"""Fix both update_or_create calls, clear cache, restart engine."""
import os, sys, subprocess, time
os.chdir(r"C:\prop-frim-bot")

# Fix the engine file
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    content = f.read()

# Fix 1: First update_or_create (position sync loop)
old1 = 'OpenPosition.objects.update_or_create(\n                        account=account,\n                        broker_ticket=ticket,\n                        defaults={\n                            "symbol": sym_obj,\n                            "direction": SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,\n                            "volume": Decimal(str(pos.volume)),\n                            "entry_price": Decimal(str(pos.price_open)),\n                            "current_price": Decimal(str(pos.price_current)),\n                            "stop_loss": Decimal(str(pos.sl)) if pos.sl else None,\n                            "take_profit": Decimal(str(pos.tp)) if pos.tp else None,\n                            "unrealized_profit": Decimal(str(pos.profit)),\n                            "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),\n                        }\n                    )'
new1 = 'OpenPosition.objects.filter(account=account, broker_ticket=ticket).delete()\n                    OpenPosition.objects.create(\n                        account=account,\n                        broker_ticket=ticket,\n                        symbol=sym_obj,\n                        direction=SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,\n                        volume=Decimal(str(pos.volume)),\n                        entry_price=Decimal(str(pos.price_open)),\n                        current_price=Decimal(str(pos.price_current)),\n                        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,\n                        take_profit=Decimal(str(pos.tp)) if pos.tp else None,\n                        unrealized_profit=Decimal(str(pos.profit)),\n                        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),\n                    )'

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("FIX 1: First update_or_create -> delete+create")
else:
    print("FIX 1: Pattern not found (already fixed or different indentation)")

# Fix 2: Second update_or_create (execution pipeline)
old2 = 'OpenPosition.objects.update_or_create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                defaults={\n                                                                                    "symbol": symbol_obj,\n                                                                                    "direction": SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                    "volume": lot_size,\n                                                                                    "entry_price": filled_price,\n                                                                                    "current_price": filled_price,\n                                                                                    "stop_loss": exec_sl,\n                                                                                    "take_profit": exec_tp,\n                                                                                    "unrealized_profit": Decimal("0.00"),\n                                                                                    "opened_at": django_tz.now(),\n                                                                                }\n                                                                            )'
new2 = 'OpenPosition.objects.filter(account=account, broker_ticket=ticket_str).delete()\n                                                                            OpenPosition.objects.create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                symbol=symbol_obj,\n                                                                                direction=SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                volume=lot_size,\n                                                                                entry_price=filled_price,\n                                                                                current_price=filled_price,\n                                                                                stop_loss=exec_sl,\n                                                                                take_profit=exec_tp,\n                                                                                unrealized_profit=Decimal("0.00"),\n                                                                                opened_at=django_tz.now(),\n                                                                            )'

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("FIX 2: Second update_or_create -> delete+create")
else:
    print("FIX 2: Pattern not found (already fixed or different format)")
    # Find what's there
    idx = content.find("update_or_create", content.find("ticket_str"))
    if idx >= 0:
        # Show context
        line_num = content[:idx].count('\n') + 1
        print(f"  Found at line {line_num}")
        for i in range(max(0, line_num-2), min(content.count('\n')+1, line_num+18)):
            l = content.split('\n')[i-1]
            print(f"    {i}: {l.rstrip()[:100]}")

with open(eng_path, "w") as f:
    f.write(content)

# Syntax check
import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("\nSYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"\nSYNTAX ERROR: {e}")

# Clean restart
print("\n=== Clean restart ===")
subprocess.run(['taskkill', '/f', '/im', 'python.exe'], timeout=10)
time.sleep(3)
subprocess.run(['powershell', '-Command',
    'Get-ChildItem C:\\prop-frim-bot -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue'],
    timeout=30)
time.sleep(2)
subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
time.sleep(8)

r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
print(f"Engine: {r.stdout.strip()}")

# Git
subprocess.run(['git', 'add', 'backend/apps/trading/management/commands/run_mt5_engine.py'], timeout=10)
r = subprocess.run(['git', 'commit', '-m', 'fix: replace both OpenPosition.update_or_create with safe delete+create'], capture_output=True, text=True, timeout=10)
print(r.stdout[:200])
subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, text=True, timeout=30)

# Wait and verify
print("\n=== Monitoring (45s) ===")
time.sleep(45)

r = subprocess.run(['powershell', '-Command',
    'if(Test-Path C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log){Get-Content C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log -Tail 3; (Get-ChildItem C:\\prop-frim-bot\\logs\\TradingMT5Engine.err.log).Length} else {echo "No err log"}'],
    capture_output=True, text=True, timeout=5)
print(f"Errors: {r.stdout[:300]}")

import json
r = subprocess.run(['curl', '-s', 'http://194.37.80.107:8000/api/v1/signals/?limit=100'], capture_output=True, text=True, timeout=15)
try:
    data = json.loads(r.stdout)
    from collections import Counter
    syms = Counter(s['symbol_name'] for s in data)
    print(f"\nSignals: {len(data)}, Unique: {len(syms)}")
    for s, c in sorted(syms.items()):
        print(f"  {s}: {c}")
except:
    print(f"API: {r.stdout[:200]}")

print("\nDONE")
