import os
os.chdir("C:/prop-frim-bot")
p = "trading_engine/account_manager.py"
c = open(p, "r", encoding="utf-8").read()

# Find the volatility gate check
lines = c.split("\n")
for i, l in enumerate(lines):
    if "Volatility Gate" in l or "atr_ratio" in l or "too stagnant" in l:
        print(f"L{i}: {l}")
        # Print next few lines
        for j in range(i+1, min(len(lines), i+5)):
            print(f"L{j}: {lines[j]}")
        print("---")

