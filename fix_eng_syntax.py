"""Fix the remaining syntax error in the engine file by restoring from git
and re-applying only the minimal fix."""
import os, sys, signal, subprocess, py_compile
signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

# Restore from git to get a clean version
print("Restoring clean engine from git...")
subprocess.run(['git', 'checkout', '--', 
    'backend/apps/trading/management/commands/run_mt5_engine.py'], timeout=10)

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Apply the MINIMAL fix: replace update_or_create with filter+first pattern
# This prevents the 'get() returned more than one' crash while being syntactically safe

old = """                    OpenPosition.objects.update_or_create(
                        account=account,
                        broker_ticket=ticket,
                        defaults={
                            \"symbol\": sym_obj,
                            \"direction\": SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,
                            \"volume\": Decimal(str(pos.volume)),
                            \"entry_price\": Decimal(str(pos.price_open)),
                            \"current_price\": Decimal(str(pos.price_current)),
                            \"stop_loss\": Decimal(str(pos.sl)) if pos.sl else None,
                            \"take_profit\": Decimal(str(pos.tp)) if pos.tp else None,
                            \"unrealized_profit\": Decimal(str(pos.profit)),
                            \"opened_at\": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                        }
                    )"""

new = """                    # Safe upsert: delete duplicates first, then create
                    OpenPosition.objects.filter(account=account, broker_ticket=ticket).delete()
                    OpenPosition.objects.create(
                        account=account,
                        broker_ticket=ticket,
                        symbol=sym_obj,
                        direction=SignalDirection.BUY if pos.type == client.mt5.ORDER_TYPE_BUY else SignalDirection.SELL,
                        volume=Decimal(str(pos.volume)),
                        entry_price=Decimal(str(pos.price_open)),
                        current_price=Decimal(str(pos.price_current)),
                        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,
                        take_profit=Decimal(str(pos.tp)) if pos.tp else None,
                        unrealized_profit=Decimal(str(pos.profit)),
                        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),
                    )"""

if old in eng:
    eng = eng.replace(old, new)
    with open(eng_path, "w") as f:
        f.write(eng)
    print("Position sync fixed: delete+create pattern")
else:
    print("Pattern not found! Let me find what's actually there...")
    idx = eng.find("OpenPosition.objects.update_or_create")
    if idx >= 0:
        # Show the full block
        print(f"Found at {idx}")
        print(eng[idx:idx+600])

try:
    py_compile.compile(eng_path, doraise=True)
    print("\nSyntax: OK")
    subprocess.run(['nssm', 'start', 'TradingMT5Engine'], timeout=10)
    import time; time.sleep(5)
    r = subprocess.run(['nssm', 'status', 'TradingMT5Engine'], capture_output=True, text=True, timeout=5)
    print(f"Engine: {r.stdout.strip()}")
except py_compile.PyCompileError as e:
    print(f"\nSyntax ERROR: {e}")
    # Show the problematic area
    with open(eng_path, "r") as f:
        lines = f.readlines()
    err_line = int(str(e).split("line ")[1].split(",")[0]) if "line " in str(e) else 0
    for i in range(max(0, err_line-3), min(len(lines), err_line+3)):
        print(f"  {i+1}: {lines[i][:100]}")
