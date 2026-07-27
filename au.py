import os, sys
os.chdir("C:/prop-frim-bot")

with open("backend/apps/trading/management/commands/run_mt5_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== EXECUTION PIPELINE AUDIT ===\n")

# 1. Signal creation
print("--- SIGNAL CREATION ---")
for i, l in enumerate(lines):
    if "sig = Signal.objects.create(" in l:
        for j in range(i, min(len(lines), i+14)):
            print(f"  L{j+1}: {lines[j].rstrip()[:130]}")
        break

print("\n--- STATUS & SCORE THRESHOLDS ---")
for i, l in enumerate(lines):
    if 'status="ACTIVE"' in l and 'WATCHLIST' in l:
        print(f"  L{i+1}: {l.rstrip()[:130]}")
    if 'is_high_conf =' in l:
        print(f"  L{i+1}: {l.rstrip()[:130]}")
    if 'is_executable' in l:
        print(f"  L{i+1}: {l.rstrip()[:130]}")

print("\n--- EXECUTION GATE BLOCK ---")
for i, l in enumerate(lines):
    if 'if is_high_conf and broker_setting.enable_autotrading' in l:
        print(f"  L{i+1}: GATE ENTRY -> {l.rstrip()[:130]}")
        for j in range(i+1, min(len(lines), i+80)):
            s = lines[j].rstrip()
            if not s or s.startswith("#"):
                continue
            if any(x in s for x in ["eat_status", "news_engine", "brain_passed", "eval_result", 
                                     "duplicate_pos", "passed_gate", "lot_size", "order_res",
                                     "EXECUTING", "TRADE EXECUTED", "retcode", "continue",
                                     "except", "BLOCKED", "REJECTED", "SKIPPED"]):
                print(f"  L{j+1}: {s[:150]}")
            if "try:" in s:
                continue
        break

print("\n--- LOG: LAST EXECUTION EVENTS ---")
log_path = "logs/TradingMT5Engine.log"
if os.path.exists(log_path):
    with open(log_path, "rb") as f:
        f.seek(max(0, os.fstat(f.fileno()).st_size - 30000))
        data = f.read().decode("latin-1")
    log_lines = [l for l in data.split("\n") if l.strip()]
    for term in ["EXECUTING CRT", "TRADE EXECUTED", "BLOCKED", "REJECTED"]:
        matches = [l for l in log_lines if term in l]
        print(f"\n{term}: {len(matches)} events")
        for m in matches[-5:]:
            print(f"  {m[:150]}")
else:
    print("Log file not found on VPS")
