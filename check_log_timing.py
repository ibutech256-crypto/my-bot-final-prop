import subprocess, sys

result = subprocess.run(
    [r"C:\prop-frim-bot\.venv\Scripts\python.exe", "-c", """
import os
log_path = r"C:\\prop-frim-bot\\logs\\TradingMT5Engine.log"
with open(log_path, "r", errors="replace") as f:
    lines = f.readlines()

# Check when the fix was deployed - find lines with "score.passed"
for i, l in enumerate(lines):
    if "score.passed" in l or "is_high_conf =" in l:
        print(f"Line {i}: {l.strip()[:200]}")

# Check the last 20 lines with timestamps or sequence
print("\\n=== Last 30 lines ===")
for l in lines[-30:]:
    print(l.strip()[:200])

# Check for ANY line indicating the fix took effect
print("\\n=== Looking for fix-related messages ===")
for i, l in enumerate(lines):
    if "score.passed" in l or "FIX" in l or "is_high_conf" in l:
        print(f"  Line {i}: {l.strip()[:150]}")
        break
else:
    print("  No fix messages found in log")
    
# How many times was engine restarted?
starts = [i for i, l in enumerate(lines) if "Starting MT5" in l]
print(f"\\nEngine restarted {len(starts)} times at lines: {starts[-5:] if len(starts)>=5 else starts}")
"""],
    capture_output=True, text=True, timeout=30
)
print(result.stdout[:3000])
if result.stderr:
    print("STDERR:", result.stderr[:500])
