import os, sys
os.chdir("C:/prop-frim-bot")

print("=== FILE SIZE ===")
print(os.path.getsize("backend/apps/trading/management/commands/run_mt5_engine.py"), "bytes")

with open("backend/apps/trading/management/commands/run_mt5_engine.py", "rb") as f:
    c = f.read()

# Check for the critical section  
idx = c.find(b"if not recent:")
print(f"\n'if not recent:' at byte {idx}")

if idx > 0:
    # Show 2000 bytes from this point
    print("\n=== SIGNAL CREATION SECTION ===")
    print(c[idx:idx+2000].decode("latin-1", errors="replace"))

# Check syntax
import py_compile
try:
    py_compile.compile("backend/apps/trading/management/commands/run_mt5_engine.py", doraise=True)
    print("\n=== SYNTAX OK ===")
except py_compile.PyCompileError as e:
    print(f"\n=== SYNTAX ERROR: {e} ===")

# Check log tail
log_path = "logs/TradingMT5Engine.log"
log_size = os.path.getsize(log_path)
with open(log_path, "rb") as f:
    f.seek(max(0, log_size - 10000))
    data = f.read().decode("latin-1")
lines = [l for l in data.split("\n") if l.strip()]
print(f"\n=== LOG TAIL ({len(lines)} lines of {log_size} byte file) ===")
for l in lines[-10:]:
    print(l[:150])

# Check for any signal/scoring/error related content
for term in ["NEW SIGNAL", "SCAN ERROR", "score", "Error inside", "for sym", "TRADE EXECUTED"]:
    matches = [l for l in lines if term in l]
    if matches:
        print(f"\n=== '{term}' ({len(matches)} occurrences) ===")
        for m in matches[-3:]:
            print(m[:150])

