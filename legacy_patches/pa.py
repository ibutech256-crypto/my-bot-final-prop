
import os, sys
os.chdir("C:/prop-frim-bot")

with open("backend/apps/trading/management/commands/run_mt5_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== SIGNAL CREATION & STATUS ===")
for i, l in enumerate(lines):
    if "sig = Signal.objects.create(" in l:
        for j in range(i, min(len(lines), i+14)):
            print(f"  L{j+1}: {lines[j].rstrip()[:120]}")
        break
for i, l in enumerate(lines):
    if 'status="ACTIVE"' in l and 'WATCHLIST' in l:
        print(f"
STATUS at L{i+1}: {l.rstrip()[:140]}")
    if 'is_high_conf =' in l:
        print(f"
HIGH_CONF at L{i+1}: {l.rstrip()[:140]}")

print("

=== EXECUTION GATES (in order) ===")
for i, l in enumerate(lines):
    if 'if is_high_conf and' in l:
        print(f"
MAIN GATE L{i+1}: {l.rstrip()[:120]}")
        for j in range(i, min(len(lines), i+80)):
            s = lines[j].rstrip()
            if any(x in s for x in ["eat_status", "news_engine", "brain_passed", 
                                     "eval_result", "duplicate_pos", "passed_gate",
                                     "mt5_tick", "mt5_spec", "lot_size", "order_res",
                                     "retcode", "EXECUTING", "TRADE EXECUTED"]):
                print(f"  L{j+1}: {s[:140]}")
        break

print("

=== LAST LOG EVENTS ===")
with open("logs/TradingMT5Engine.log", "rb") as f:
    f.seek(max(0, os.fstat(f.fileno()).st_size - 30000))
    data = f.read().decode("latin-1")
log_lines = [l for l in data.split("
") if l.strip()]

for term in ["EXECUTING CRT", "TRADE EXECUTED", "BLOCKED", "REJECTED", "EXECUTION SKIPPED"]:
    matches = [l for l in log_lines if term in l]
    if matches:
        print(f"
{term}: {len(matches)}")
        for m in matches[-3:]:
            print(f"  {m[:160]}")

stops = [l for l in log_lines if "loop stopping" in l]
print(f"
Loop stops: {len(stops)}")
