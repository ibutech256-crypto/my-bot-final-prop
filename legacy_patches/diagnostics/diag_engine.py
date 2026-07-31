
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p, "r").readlines()
print(f"Total lines: {len(lines)}")
print("Lines 530-545:")
for i in range(529, min(545, len(lines))):
    ai = len(lines[i]) - len(lines[i].lstrip())
    print(f"  {i+1}: indent={ai:3d} |{lines[i][:100]}")
