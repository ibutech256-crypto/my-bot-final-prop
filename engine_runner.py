"""Self-healing Engine Runner - auto-restarts failed services."""
import os, sys, time, subprocess, json, threading
from datetime import datetime, timezone

BASE = r"C:\prop-frim-bot"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)

class EngineRunner:
    def __init__(self):
        self.services = [
            ("Memurai", "Memurai.exe", 10),
            ("TradingBackend", "python.exe -m daphne -b 0.0.0.0 -p 8000 backend.config.asgi:application", 15),
            ("TradingWorker", "celery.exe -A backend.config worker -l INFO --concurrency=4 -P threads", 10),
            ("TradingBeat", "celery.exe -A backend.config beat -l INFO", 10),
            ("TradingFrontend", "next start", 10),
            ("TradingMT5Engine", "python.exe -u backend\\manage.py run_mt5_engine", 5),
        ]
        self.failures = {s[0]: 0 for s in self.services}
        self.recoveries = {s[0]: 0 for s in self.services}
        self.running = True
    
    def log(self, msg):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(LOGS, "runner.log"), "a") as f:
            f.write(f"[{ts}] {msg}\n")
        print(f"[{ts}] {msg}")
    
    def check_service(self, name):
        r = subprocess.run(['nssm', 'status', name], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    
    def start_service(self, name):
        self.log(f"Starting {name}...")
        r = subprocess.run(['nssm', 'start', name], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            self.recoveries[name] += 1
            self.log(f"  {name} started successfully")
            return True
        self.log(f"  {name} start failed: {r.stderr[:100]}")
        return False
    
    def run_health_loop(self):
        """Check services every 30 seconds, restart failed ones."""
        while self.running:
            for name, cmd, timeout in self.services:
                try:
                    status = self.check_service(name)
                    if status != "SERVICE_RUNNING":
                        self.failures[name] += 1
                        self.log(f"WARNING: {name} is {status} (failure #{self.failures[name]})")
                        if self.failures[name] >= 2:
                            self.start_service(name)
                            if self.check_service(name) == "SERVICE_RUNNING":
                                self.failures[name] = 0
                    else:
                        self.failures[name] = 0
                except Exception as e:
                    self.log(f"ERROR checking {name}: {e}")
            time.sleep(30)
    
    def start(self):
        self.log("=" * 50)
        self.log("ENGINE RUNNER STARTED")
        self.log("=" * 50)
        
        # Start health monitor thread
        t = threading.Thread(target=self.run_health_loop, daemon=True)
        t.start()
        
        # Keep alive
        try:
            while self.running:
                time.sleep(10)
        except KeyboardInterrupt:
            self.running = False
            self.log("Engine Runner stopped")

if __name__ == "__main__":
    runner = EngineRunner()
    runner.start()
