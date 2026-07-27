"""Remove PositionManager thread from engine - it causes MT5 IPC conflicts."""
import os, sys, signal, py_compile
signal.signal(signal.SIGINT, signal.SIG_IGN)

eng_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(eng_path, "r") as f:
    eng = f.read()

# Remove the PositionManager import and thread start
if "PositionManager" in eng:
    # Remove the import
    eng = eng.replace("from trading_engine.position_manager import PositionManager\n        import threading\n        pm = PositionManager()\n        pm_thread = threading.Thread(target=pm.run_loop, daemon=True)\n        pm_thread.start()\n        self.stdout.write(\"Position Manager daemon started\")", "")
    # Also remove from top imports
    eng = eng.replace("from trading_engine.position_manager import PositionManager\n", "")
    
    with open(eng_path, "w") as f:
        f.write(eng)
    print("PositionManager removed from engine file")
else:
    print("PositionManager not found in engine")

# Verify clean
with open(eng_path, "r") as f:
    eng = f.read()
if "PositionManager" not in eng:
    print("  Verified: No PositionManager references remain")
    
if "ensure_connected" not in eng:
    print("  Verified: No ensure_connected references remain")

try:
    py_compile.compile(eng_path, doraise=True)
    print("Syntax: OK")
except Exception as e:
    print(f"Syntax ERROR: {e}")
