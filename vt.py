import os
os.chdir("C:/prop-frim-bot/logs")
with open("TradingMT5Engine.log", "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 50000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]

print("=== EXECUTION VERIFICATION ===\n")
for term in ["EXECUTING CRT", "TRADE EXECUTED", "BLOCKED BY", "EXECUTION REJECTED", "NEW SIGNAL RECORDED", "loop stopping"]:
    matches = [l for l in lines if term in l]
    if matches:
        print(f"{term}: {len(matches)}")
        for m in matches[-5:]:
            print(f"  {m[:160]}")
    else:
        print(f"{term}: 0")

stops = [l for l in lines if "loop stopping" in l]
print(f"\nEngine stability: {len(stops)} stops in sample")
