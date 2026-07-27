import os
os.chdir("C:/prop-frim-bot/logs")
with open("TradingMT5Engine.log", "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 30000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]
print(f"Last {len(lines)} lines of log:")
for l in lines[-10:]:
    print(l[:150])

print("\n=== KEY EVENTS ===")
for term in ["NEW SIGNAL", "TRADE EXECUTED", "BLOCKED", "EXECUTING", "SCAN ERROR", "Error inside"]:
    matches = [l for l in lines if term in l]
    if matches:
        print(f"\n{term}: {len(matches)}")
        for m in matches[-3:]:
            print(f"  {m[:150]}")

