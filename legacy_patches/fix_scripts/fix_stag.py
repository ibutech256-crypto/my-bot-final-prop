import os
os.chdir("C:/prop-frim-bot")
p = "trading_engine/account_manager.py"
c = open(p, "r", encoding="utf-8").read()

if "stagnant" in c:
    idx = c.find("stagnant")
    print(f"First 'stagnant' at {idx}:")
    print(c[idx:idx+200])
    
    # Find and disable the stagnation check
    old = 'is_stagnant = atr_14 / current_price > Decimal("0.003")'
    new = 'is_stagnant = False  # Disabled: atr_14 / current_price > Decimal("0.003")'
    
    if old in c:
        c = c.replace(old, new)
        open(p, "w", encoding="utf-8").write(c)
        print("? Stagnation gate DISABLED")
    else:
        # Try different pattern
        lines = c.split("\n")
        for i, l in enumerate(lines):
            if "stagnant" in l:
                print(f"L{i}: {l}")

