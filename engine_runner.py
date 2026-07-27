import subprocess, sys, os, time

log = open(r"C:\prop-frim-bot\logs\engine_runner.log", "a", buffering=1)
log.write(f"\n=== Engine Runner Started at {time.ctime()} ===\n")

while True:
    log.write(f"\n--- Starting engine at {time.ctime()} ---\n")
    proc = subprocess.Popen(
        [sys.executable, "-u", "backend/manage.py", "run_mt5_engine"],
        cwd=r"C:\prop-frim-bot",
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    proc.wait()
    log.write(f"Engine exited with code {proc.returncode} at {time.ctime()}. Restarting in 3s...\n")
    time.sleep(3)