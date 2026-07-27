import subprocess, sys

# Read the log file for execution audit entries
result = subprocess.run(
    [r"C:\prop-frim-bot\.venv\Scripts\python.exe", "-c", """
import os
log_path = r"C:\\prop-frim-bot\\logs\\TradingMT5Engine.log"
if not os.path.exists(log_path):
    print("LOG NOT FOUND")
    sys.exit(1)
with open(log_path, "r", errors="replace") as f:
    lines = f.readlines()

audit_lines = [l for l in lines if "EXEC-AUDIT" in l]
print(f"Total EXEC-AUDIT lines: {len(audit_lines)}")
for l in audit_lines[-30:]:
    print(l.strip()[:250])

print("\\n=== Last 5 NEW SIGNAL lines ===")
sig_lines = [l for l in lines if "NEW SIGNAL" in l]
for l in sig_lines[-5:]:
    print(l.strip()[:200])

print("\\n=== Last 10 EXECUTION/TRADE lines ===")
exec_lines = [l for l in lines if any(x in l for x in ["TRADE EXECUTED", "EXECUTING CRT", "EXECUTION SKIPPED", "EXECUTION BLOCKED", "EXECUTION REJECTED"])]
for l in exec_lines[-10:]:
    print(l.strip()[:250])
"""],
    capture_output=True, text=True, timeout=30
)
print(result.stdout[:3000])
if result.stderr:
    print("STDERR:", result.stderr[:500])
