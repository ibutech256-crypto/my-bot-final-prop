import os, sys, re

os.chdir(r"C:\prop-frim-bot")
eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"

with open(eng_path, "r") as f:
    content = f.read()

# Find all OpenPosition.objects.update_or_create occurrences
count_before = content.count("OpenPosition.objects.update_or_create")
print(f"Found {count_before} occurrences of OpenPosition.objects.update_or_create")

# Find the one that starts with 76 spaces (the deeply indented one in the execution block)
# Pattern: it has 'broker_ticket=ticket_str' and 'defaults={'
old = 'OpenPosition.objects.update_or_create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                defaults={\n                                                                                    "symbol": symbol_obj,\n                                                                                    "direction": SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                    "volume": lot_size,\n                                                                                    "entry_price": filled_price,\n                                                                                    "current_price": filled_price,\n                                                                                    "stop_loss": exec_sl,\n                                                                                    "take_profit": exec_tp,\n                                                                                    "unrealized_profit": Decimal("0.00"),\n                                                                                    "opened_at": django_tz.now(),\n                                                                                }\n                                                                            )'

new = 'OpenPosition.objects.filter(account=account, broker_ticket=ticket_str).delete()\n                                                                            OpenPosition.objects.create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str,\n                                                                                symbol=symbol_obj,\n                                                                                direction=SignalDirection.BUY if sig.direction == "BUY" else SignalDirection.SELL,\n                                                                                volume=lot_size,\n                                                                                entry_price=filled_price,\n                                                                                current_price=filled_price,\n                                                                                stop_loss=exec_sl,\n                                                                                take_profit=exec_tp,\n                                                                                unrealized_profit=Decimal("0.00"),\n                                                                                opened_at=django_tz.now(),\n                                                                            )'

if old in content:
    content = content.replace(old, new)
    print("Second update_or_create replaced with delete+create")
else:
    print("Second pattern not found - trying extended search...")
    # Try with different indentation
    idx = content.find('update_or_create(\n                                                                                account=account,\n                                                                                broker_ticket=ticket_str')
    if idx >= 0:
        print(f"Found at byte {idx}")
        # Find the matching close paren
        end = content.find(')', idx)
        while end > 0:
            depth = content[idx:end].count('(') - content[idx:end].count(')')
            if depth <= 0:
                break
            nxt = content.find(')', end+1)
            if nxt < 0: break
            end = nxt
        print(f"Block ends at byte {end}")
        print(repr(content[idx:end+1][:200]))

# Also find first update_or_create if it exists 
idx_first = content.find('OpenPosition.objects.update_or_create(\n                        account=account,\n                        broker_ticket=ticket,\n                        defaults=')
if idx_first >= 0:
    print(f"\nFirst update_or_create also still at byte {idx_first}")

count_after = content.count("OpenPosition.objects.update_or_create")
print(f"\nRemaining: {count_after}")

with open(eng_path, "w") as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("SYNTAX: OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
