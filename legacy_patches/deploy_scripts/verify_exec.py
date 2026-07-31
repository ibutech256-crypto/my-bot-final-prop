import os, subprocess
os.chdir("C:/prop-frim-bot/logs")

print("=== ENGINE EXECUTION VERIFICATION ===\n")

# Count events in last 10000 bytes
with open("TradingMT5Engine.log", "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 50000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]

events = {}
for t in ["NEW SIGNAL RECORDED", "TRADE EXECUTED", "EXECUTION REJECTED", "BLOCKED BY", "EXECUTING CRT", "loop stopping", "Error inside"]:
    events[t] = [l for l in lines if t in l]
    print(f"{t}: {len(events[t])}")
    if events[t]:
        for m in events[t][-2:]:
            print(f"  {m[:150]}")

# Check if engine is stable (vs crash-looping)
stops = events.get("loop stopping", [])
print(f"\nLoop stops in sample: {len(stops)}")
if len(stops) <= 1:
    print("? ENGINE STABLE - no crash loop")
else:
    print(f"?? Engine stopped {len(stops)} times in this sample")

# Check for successful trades
trades = events.get("TRADE EXECUTED", [])
if trades:
    print(f"\n? TRADES EXECUTED: {len(trades)}")
    for t in trades[-3:]:
        print(f"  {t[:150]}")
else:
    print("\n? No trades executed in sample")

# Check rejections
rejects = events.get("EXECUTION REJECTED", [])
if rejects:
    print(f"\nRejections: {len(rejects)}")
    for r in rejects[-3:]:
        print(f"  {r[:150]}")

