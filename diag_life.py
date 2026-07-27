
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p, "r").readlines()
print("Lines containing lifecycle_status:")
for i, line in enumerate(lines):
    if "lifecycle_status" in line:
        stripped = line.lstrip()
        ai = len(line) - len(line.lstrip())
        print(f"  {i+1}: indent={ai:3d} |{stripped[:80]}")
print()
# Show context around the lifecycle block
for i, line in enumerate(lines):
    if "Lifecycle states" in line:
        for j in range(max(0,i-1), min(len(lines), i+15)):
            stripped = lines[j].lstrip()
            ai = len(lines[j]) - len(lines[j].lstrip())
            print(f"  {j+1}: indent={ai:3d} |{stripped[:100]}")
        break
