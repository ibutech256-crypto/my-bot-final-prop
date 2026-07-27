import os
os.chdir("C:/prop-frim-bot")
p = "broker_engine/mt5_client.py"
c = open(p, "r", encoding="utf-8").read()

old = '    order_type: str = "MARKET"  # MARKET, LIMIT'
new = '    order_type: str = "MARKET"\n    expiration: int | None = None\n    is_pit_open: bool | None = None'

if old in c:
    c = c.replace(old, new)
    open(p, "w", encoding="utf-8").write(c)
    print("FIXED: Added expiration and is_pit_open to BrokerOrderRequest")
else:
    print("Pattern not found - checking file...")
    for i, l in enumerate(c.split('\n')):
        if 'order_type' in l and 'class BrokerOrderRequest' in str(c[:c.find(l)]):
            print(f"  L{i}: {l}")

import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("SYNTAX OK!")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")
