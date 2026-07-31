import os
os.chdir("C:/prop-frim-bot")
with open("backend/apps/trading/management/commands/run_mt5_engine.py", "r") as f:
    l = f.readlines()
for i in range(460, min(520, len(l))):
    print(f"L{i+1}: {l[i].rstrip()[:130]}")

