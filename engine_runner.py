"""V3.0 Engine Runner - Self-Healing Institutional Platform.
Launches: MT5 Engine, Position Sync, Health Daemon, Signal Freshness, Event Bus."""
import os, sys, time, threading, signal
from datetime import datetime, timezone

BASE = r"C:\prop-frim-bot"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)
os.chdir(BASE)
sys.path.insert(0, BASE)

signal.signal(signal.SIGINT, signal.SIG_IGN)

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(LOGS, "runner_v3.log"), "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")

def run_mt5_engine():
    """MT5 engine with auto-restart."""
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

# Position sync is integrated into the MT5 engine main loop.
# Running it as a separate thread causes MT5 IPC conflicts.
def run_position_sync():
    """Position sync disabled - integrated into MT5 engine loop."""
    while True:
        time.sleep(60)

def run_health_daemon():
    """System health daemon."""
    while True:
        try:
            from system.health_daemon import HealthDaemon
            daemon = HealthDaemon()
            daemon.run()
        except Exception as e:
            log(f"Health daemon error: {e}, restarting in 5s...")
            time.sleep(5)

def run_ai_diagnostics():
    """AI diagnostics every 5 minutes."""
    while True:
        try:
            from system.ai_diagnostics import AIDiagnostics
            diag = AIDiagnostics()
            report = diag.analyze()
            if report["health_score"] < 70:
                log(f"AI Diagnostics: Score={report['health_score']}% ({report['severity']})")
                for p in report["problems"][:3]:
                    log(f"  Problem: {p}")
                for r in report["recommendations"][:3]:
                    log(f"  Suggestion: {r}")
            time.sleep(300)  # 5 minutes
        except Exception as e:
            log(f"AI diagnostics error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    import subprocess
    
    log("=" * 50)
    log("V3.0 SELF-HEALING ENGINE RUNNER STARTED")
    log("=" * 50)
    
    threads = [
        threading.Thread(target=run_mt5_engine, daemon=True, name="MT5-Engine"),
        threading.Thread(target=run_position_sync, daemon=True, name="Position-Sync"),
        threading.Thread(target=run_health_daemon, daemon=True, name="Health-Daemon"),
        threading.Thread(target=run_ai_diagnostics, daemon=True, name="AI-Diagnostics"),
    ]
    
    for t in threads:
        t.start()
        log(f"Thread '{t.name}' started")
    
    # Monitor threads
    try:
        while True:
            time.sleep(30)
            for t in threads:
                if not t.is_alive():
                    log(f"Thread '{t.name}' died, cannot restart (daemon)")
    except KeyboardInterrupt:
        log("Engine Runner stopped by signal")
