import os, py_compile
os.chdir("C:/prop-frim-bot")

# Fix 1: Add expiration field to BrokerOrderRequest
p = "broker_engine/mt5_client.py"
c = open(p, "r", encoding="utf-8").read()
old = "    order_type: str = \"MARKET\"  # MARKET, LIMIT"
new = "    order_type: str = \"MARKET\"  # MARKET, LIMIT\n    expiration: int | None = None"
if old in c:
    c = c.replace(old, new)
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("✅ Added expiration field to BrokerOrderRequest")
else:
    print("⚠️ Pattern not found")

# Fix 2: Add expiration, is_pit_open to BrokerOrderRequest (engine uses both)
if "is_pit_open: bool | None = None" not in c:
    c = c.replace('expiration: int | None = None', 'expiration: int | None = None\n    is_pit_open: bool | None = None')
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)
    print("✅ Added is_pit_open field to BrokerOrderRequest")

# Verify syntax
try:
    py_compile.compile(p, doraise=True)
    print("✅ Broker syntax OK")
except py_compile.PyCompileError as e:
    print(f"❌ Error: {e}")
