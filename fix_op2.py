"""Fix the remaining OpenPosition.update_or_create via exact line replacement."""
import os, sys

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Count occurrences
import re
matches = list(re.finditer(r'OpenPosition\.objects\.update_or_create\(', eng))
print(f"Found {len(matches)} occurrences")

for m in matches:
    pos = m.start()
    line_num = eng[:pos].count('\n') + 1
    print(f"  Line {line_num}: {m.group()[:80]}")

# Replace the second one (line 753, which should be the execution block one)
# Find by position - it's the one with 'broker_ticket=ticket_str'
idx = eng.find("update_or_create(", eng.find("broker_ticket=ticket_str"))
if idx > 0:
    # Find the matching closing paren
    depth = 0
    start = eng.rfind('\n', 0, idx) + 1
    start_line = eng[:start].count('\n') + 1
    
    # Find the end of this block
    end = eng.find(')', idx)
    while end > 0:
        depth = eng[idx:end].count('(') - eng[idx:end].count(')')
        if depth <= 0:
            break
        next_end = eng.find(')', end + 1)
        if next_end < 0:
            break
        end = next_end
    
    # Extend to include the closing paren and next newline
    end = eng.find('\n', end) + 1
    
    block = eng[start:end]
    print(f"\nBlock lines {start_line}-{eng[:end].count(chr(10))+1}:")
    print(block[:200])
    
    # Build replacement
    # Extract the field values from the defaults dict
    indent = ' ' * 76
    inner_indent = ' ' * 80
    
    new_block = indent + 'OpenPosition.objects.filter(account=account, broker_ticket=ticket_str).delete()\n'
    new_block += indent + 'OpenPosition.objects.create(\n'
    new_block += inner_indent + 'account=account,\n'
    new_block += inner_indent + 'broker_ticket=ticket_str,\n'
    new_block += inner_indent + 'symbol=symbol_obj,\n'
    
    # Copy the direction and other fields from the defaults
    for line in block.split('\n'):
        stripped = line.strip()
        if '"direction"' in stripped:
            new_block += inner_indent + stripped.replace('"direction":', 'direction=') + '\n'
        elif '"volume"' in stripped:
            new_block += inner_indent + stripped.replace('"volume":', 'volume=') + '\n'
        elif '"entry_price"' in stripped:
            new_block += inner_indent + stripped.replace('"entry_price":', 'entry_price=') + '\n'
        elif '"current_price"' in stripped:
            new_block += inner_indent + stripped.replace('"current_price":', 'current_price=') + '\n'
        elif '"stop_loss"' in stripped:
            new_block += inner_indent + stripped.replace('"stop_loss":', 'stop_loss=') + '\n'
        elif '"take_profit"' in stripped:
            new_block += inner_indent + stripped.replace('"take_profit":', 'take_profit=') + '\n'
        elif '"unrealized_profit"' in stripped:
            new_block += inner_indent + stripped.replace('"unrealized_profit":', 'unrealized_profit=') + '\n'
        elif '"opened_at"' in stripped:
            new_block += inner_indent + stripped.replace('"opened_at":', 'opened_at=') + '\n'
    
    new_block += indent + ')\n'
    
    eng = eng[:start] + new_block + eng[end:]
    with open(eng_path, "w") as f:
        f.write(eng)
    print(f"\nReplaced with delete+create pattern")
else:
    print("Could not find the right block")

# Final verification
matches2 = list(re.finditer(r'OpenPosition\.objects\.update_or_create\(', eng))
print(f"\nRemaining occurrences: {len(matches2)}")
for m in matches2:
    line_num = eng[:m.start()].count('\n') + 1
    print(f"  Still at line {line_num}")

import py_compile
try:
    py_compile.compile(eng_path, doraise=True)
    print("Syntax: OK")
except Exception as e:
    print(f"Syntax ERROR: {e}")
