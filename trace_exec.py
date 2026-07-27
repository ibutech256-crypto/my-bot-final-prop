import os
os.chdir("C:/prop-frim-bot")
with open("backend/apps/trading/management/commands/run_mt5_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== EXECUTION PIPELINE ANALYSIS ===")

# Find all the key sections
key_lines = {}
for i, line in enumerate(lines):
    l = line.strip()
    if 'if is_high_conf and broker_setting.enable_autotrading:' in l:
        key_lines['execution_gate'] = i
    if 'TradeExecutionGate.evaluate' in l:
        key_lines['execution_gate_eval'] = i
    if 'enable_autotrading' in l and 'if' in l:
        key_lines[f'autotrading_check_{i}'] = i
    if 'lot_size =' in l and 'calculate_position_size' in l:
        key_lines['position_sizing'] = i
    if 'order_res = client.place_market_order' in l:
        key_lines['order_placement'] = i

for name, idx in sorted(key_lines.items(), key=lambda x: x[1]):
    print(f"\n{name} at line {idx+1}:")
    for j in range(max(0, idx-1), min(len(lines), idx+3)):
        print(f"  L{j+1}: {lines[j].rstrip()[:160]}")

# Check what's between the active_sig loop and the execution gate
print("\n\n=== EXECUTION FLOW IN BACKTESTING LOOP ===")
for i, l in enumerate(lines):
    if 'for active_sig' in l and '[:10]' in l:
        start = i
        for j in range(start, min(len(lines), start+60)):
            line = lines[j].rstrip()
            if 'enable_autotrading' in line and 'if' in line:
                print(f"L{j+1}: FOUND GATE -> {line[:120]}")
            if 'TradeExecutionGate' in line:
                print(f"L{j+1}: GATE EVAL -> {line[:120]}")
            if 'order_res =' in line and 'place_market_order' in line:
                print(f"L{j+1}: ORDER PLACEMENT -> {line[:120]}")
            if j > start + 50:
                break
        break

