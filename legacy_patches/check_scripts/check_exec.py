import os, subprocess
os.chdir("C:/prop-frim-bot/logs")
r = subprocess.run(["findstr", "/C:", "TRADE EXECUTED", "TradingMT5Engine.log"], capture_output=True, text=True)
lines = [l for l in r.stdout.split("\n") if "TRADE EXECUTED" in l]
print(f"Total trades: {len(lines)}")
for l in lines[-5:]:
    print(l[:150])

