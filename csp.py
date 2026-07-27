import os
os.chdir("C:/prop-frim-bot")
with open("trading_engine/account_manager.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
print("=== SPREAD GATE LOGIC ===")
for i, l in enumerate(lines):
    if any(x in l for x in ["spread", "pip", "point", "Spread"]):
        print(f"  L{i+1}: {l.rstrip()[:140]}")
