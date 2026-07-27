"""Self-healing Engine Runner - spawns and monitors all platform components."""
import os, sys, time, subprocess, threading, signal
from datetime import datetime, timezone

BASE = r"C:\prop-frim-bot"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)

signal.signal(signal.SIGINT, signal.SIG_IGN)

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(LOGS, "runner.log"), "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")

def run_engine():
    """Run the MT5 engine and auto-restart on crash."""
    while True:
        log("Starting MT5 Engine...")
        proc = subprocess.Popen(
            [sys.executable, "-u", "backend/manage.py", "run_mt5_engine"],
            cwd=BASE,
            stdout=open(os.path.join(LOGS, "TradingMT5Engine.log"), "a"),
            stderr=subprocess.STDOUT,
        )
        proc.wait()
        log(f"MT5 Engine exited (code {proc.returncode}), restarting in 3s...")
        time.sleep(3)

def run_position_sync():
    """Run position sync daemon."""
    while True:
        try:
            from trading_engine.position_sync import PositionSyncEngine
            sync = PositionSyncEngine()
            sync.run_loop()
        except Exception as e:
            log(f"Position sync error: {e}, restarting in 5s...")
            time.sleep(5)

def run_health_monitor():
    """Run health checks every 30 seconds."""
    sys.path.insert(0, BASE)
    while True:
        try:
            from trading_engine.platform_health import PlatformHealth
            ph = PlatformHealth()
            report = ph.run_all_checks()
            log(f"Health: {report['health_score']}% ({report['healthy']}/{report['total']} healthy)")
            # Auto-repair: restart any down services
            for name, check in report['checks'].items():
                if check.get('status') in ('DOWN', 'CRITICAL'):
                    svc_name = name.replace("NSSM:", "")
                    log(f"Attempting restart of {svc_name}...")
                    subprocess.run(['nssm', 'restart', svc_name], timeout=15, capture_output=True)
        except Exception as e:
            log(f"Health check error: {e}")
        time.sleep(30)

if __name__ == "__main__":
    log("=" * 50)
    log("ENGINE RUNNER V2 STARTED")
    log("=" * 50)
    
    threads = [
        threading.Thread(target=run_engine, daemon=True),
        threading.Thread(target=run_position_sync, daemon=True),
        threading.Thread(target=run_health_monitor, daemon=True),
    ]
    
    for t in threads:
        t.start()
        log(f"Thread {t.name} started")
    
    # Keep alive
    try:
        while True:
            time.sleep(10)
            # Check if threads are alive
            for t in threads:
                if not t.is_alive():
                    log(f"Thread {t.name} died, restarting...")
                    t = threading.Thread(target={
                        0: run_engine, 1: run_position_sync, 2: run_health_monitor
                    }[threads.index(t)], daemon=True)
                    t.start()
    except KeyboardInterrupt:
        log("Engine Runner stopped")
