import os, py_compile
os.chdir("C:/prop-frim-bot")
p = "broker_engine/mt5_client.py"
lines = open(p, "r").readlines()
for i, l in enumerate(lines):
    if 'order_type: str = "MARKET"' in l and 'expiration' not in lines[min(i+1, len(lines)-1)]:
        # Add expiration after this line
        indent = l[:len(l) - len(l.lstrip())]
        lines.insert(i+1, f'{indent}expiration: int | None = None\n')
        lines.insert(i+2, f'{indent}is_pit_open: bool | None = None\n')
        break
open(p, "w").writelines(lines)
print("FIXED: Added expiration + is_pit_open to BrokerOrderRequest")

try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")
