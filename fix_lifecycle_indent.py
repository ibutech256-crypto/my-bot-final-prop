
import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)
p = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
lines = open(p, "r").readlines()

# Find lifecycle block and fix indentation
in_lifecycle = False
for i, line in enumerate(lines):
    if "# v2.2: Lifecycle states" in line:
        in_lifecycle = True
        # Fix the initial lifecycle_status line
        lines[i+1] = "                                            lifecycle_status = "WATCHLIST"\n"
        # The if line  
        lines[i+2] = "                                            if score.total >= Decimal("85"):\n"
        lines[i+3] = "                                                lifecycle_status = "EXECUTION_READY"\n"
        lines[i+4] = "                                            elif score.total >= Decimal("70"):\n"
        lines[i+5] = "                                                lifecycle_status = "EXECUTION_READY"\n"
        lines[i+6] = "                                            elif score.total >= Decimal("55"):\n"
        lines[i+7] = "                                                lifecycle_status = "ACTIVE_MONITORING"\n"
        lines[i+8] = "                                            else:\n"
        lines[i+9] = "                                                lifecycle_status = "WATCHLIST"\n"
        print(f"Fixed lifecycle block at line {i+1}")
        break

if not in_lifecycle:
    print("Lifecycle block not found!")
else:
    open(p, "w").writelines(lines)
    import py_compile
    try:
        py_compile.compile(p, doraise=True)
        print("SYNTAX OK")
    except Exception as e:
        print(f"SYNTAX ERROR: {e}")

    # Verify 
    lines2 = open(p).readlines()
    for i, line in enumerate(lines2):
        if "lifecycle_status" in line and "WATCHLIST" in line:
            ai = len(line) - len(line.lstrip())
            print(f"  Line {i+1}: indent={ai} (expect 44 or 52)")
