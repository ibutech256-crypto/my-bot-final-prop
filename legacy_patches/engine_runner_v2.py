
import os, sys, signal, time

signal.signal(signal.SIGINT, signal.SIG_IGN)
os.chdir(r"C:\prop-frim-bot")

while True:
    log = open(r"C:\prop-frim-bot\logs\engine_runner.log", "a")
    log.write(f"[{time.ctime()}] Starting engine...\n")
    log.close()
    
    ret = os.system('.venv\\Scripts\\python.exe -u backend\\manage.py run_mt5_engine >> logs\\engine_runner.log 2>&1')
    
    log = open(r"C:\prop-frim-bot\logs\engine_runner.log", "a")
    log.write(f"[{time.ctime()}] Engine exited (code {ret}). Restarting in 5s...\n")
    log.close()
    time.sleep(5)
