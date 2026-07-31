import os
os.chdir("C:/prop-frim-bot/logs")
with open("TradingMT5Engine.log", "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 50000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]
print(f"Analyzing last {len(lines)} lines of log")

# Find most recent restart
for i, l in enumerate(lines):
    if "Starting MT5 Real-Time" in l:
        print(f"\nLast restart: {l[:100]}")
        # Show what happened after restart
        for j in range(i, min(len(lines), i+30)):
            ll = lines[j]
            if any(x in ll for x in ["NEW SIGNAL", "BLOCKED", "EXECUTING", "TRADE EXECUTED", "Error", "SCAN", "lot_size", "qualif"]):
                print(f"  {ll[:150]}")
        break
else:
    print("No restart found in last 50k bytes")

# Count key events in the last 50k bytes
for term in ["NEW SIGNAL", "BLOCKED", "EXECUTING", "TRADE EXECUTED", "Error inside", "enable_autotrading", "is_high_conf"]:
    cnt = sum(1 for l in lines if term in l)
    if cnt > 0:
        print(f"\n{term}: {cnt}")
        for m in [l for l in lines if term in l][-2:]:
            print(f"  {m[:150]}")

