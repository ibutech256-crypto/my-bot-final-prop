"""System Health Daemon - runs every 10 seconds, monitors and repairs all subsystems.
Integrates: position sync, signal freshness, event bus, AI diagnostics, auto-recovery."""
import os, sys, time, json, threading, subprocess
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

import django; django.setup()
from django.utils import timezone as dj_tz

class HealthDaemon:
    def __init__(self):
        self.services = [
            "Memurai", "TradingBackend", "TradingWorker", 
            "TradingBeat", "TradingFrontend", "TradingMT5Engine"
        ]
        self.health = {s: {"status": "UNKNOWN", "failures": 0, "last_ok": None} for s in self.services}
        self.health["MT5"] = {"status": "UNKNOWN", "failures": 0}
        self.health["Database"] = {"status": "UNKNOWN", "failures": 0}
        self.health["PositionSync"] = {"status": "UNKNOWN", "failures": 0}
        self.recovery_count = 0
        self.max_retries = 3
    
    def log(self, msg, severity="INFO"):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{severity}] {msg}"
        print(line)
        log_dir = os.path.join(BASE, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "health_daemon.log"), "a") as f:
            f.write(line + "\n")
        
        # Also emit to event bus
        try:
            from system.event_bus import bus
            bus.emit("HEALTH_CHECK", "HealthDaemon", severity, message=msg)
        except:
            pass
    
    def check_nssm(self, name):
        try:
            r = subprocess.run(['nssm', 'status', name], capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        except:
            return "UNKNOWN"
    
    def check_mt5(self):
        try:
            import MetaTrader5 as mt5
            login = int(os.getenv("MT5_LOGIN", "436005794"))
            password = os.getenv("MT5_PASSWORD", "1234#Dt@")
            server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
            if mt5.initialize():
                if mt5.login(login, password, server):
                    info = mt5.account_info()
                    mt5.shutdown()
                    if info and info.balance > 0:
                        return "HEALTHY", f"Balance=${info.balance}"
                mt5.shutdown()
            return "DEGRADED", "login failed"
        except Exception as e:
            return "DOWN", str(e)
    
    def check_database(self):
        try:
            from backend.apps.trading.models import Signal
            count = Signal.objects.count()
            return "HEALTHY", f"{count} signals"
        except Exception as e:
            return "DOWN", str(e)
    
    def check_position_sync(self):
        try:
            from backend.apps.trading.models import OpenPosition
            import MetaTrader5 as mt5
            login = int(os.getenv("MT5_LOGIN", "436005794"))
            password = os.getenv("MT5_PASSWORD", "1234#Dt@")
            server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
            mt5.initialize()
            mt5.login(login, password, server)
            mt5_pos = set(str(p.ticket) for p in (mt5.positions_get() or []))
            db_pos = set(p.broker_ticket for p in OpenPosition.objects.filter(is_deleted=False))
            mt5.shutdown()
            if mt5_pos == db_pos:
                return "HEALTHY", f"MT5={len(mt5_pos)} DB={len(db_pos)}"
            return "DEGRADED", f"MT5={len(mt5_pos)} DB={len(db_pos)} mismatch"
        except:
            return "UNKNOWN", "check failed"
    
    def run_signal_freshness_check(self):
        """Archive stale signals."""
        try:
            from system.signal_freshness import SignalFreshnessValidator
            v = SignalFreshnessValidator()
            r = v.validate_all()
            if r["archived"] > 0:
                self.log(f"Archived {r['archived']} stale signals", "INFO")
            return r
        except Exception as e:
            self.log(f"Signal freshness check failed: {e}", "WARNING")
            return {"archived": 0}
    
    def attempt_recovery(self, service_name, current_status):
        """Attempt to recover a failed service."""
        if current_status in ("HEALTHY",):
            return True
        
        info = self.health.get(service_name, self.health.get("MT5", {}))
        
        if service_name in self.services:
            # NSSM service - try restart
            self.log(f"Attempting restart of {service_name}...", "WARNING")
            subprocess.run(['nssm', 'restart', service_name], timeout=15, capture_output=True)
            time.sleep(3)
            new_status = self.check_nssm(service_name)
            if new_status == "SERVICE_RUNNING":
                self.recovery_count += 1
                self.log(f"{service_name} recovered successfully", "INFO")
                return True
            else:
                self.log(f"{service_name} restart failed (status={new_status})", "ERROR")
                return False
        
        elif service_name == "MT5":
            # MT5 auto-reconnect happens in engine
            self.log("MT5 reconnection handled by engine", "INFO")
            return True
        
        return False
    
    def run_once(self):
        """Single health check cycle."""
        now = datetime.now(timezone.utc)
        
        # 1. Check all NSSM services
        for svc in self.services:
            status = self.check_nssm(svc)
            was_healthy = self.health[svc]["status"] == "SERVICE_RUNNING"
            self.health[svc]["status"] = status
            self.health[svc]["last_ok"] = now if status == "SERVICE_RUNNING" else self.health[svc]["last_ok"]
            
            if status != "SERVICE_RUNNING":
                self.health[svc]["failures"] += 1
                if self.health[svc]["failures"] >= 2:
                    self.log(f"{svc} is {status} (failures={self.health[svc]['failures']})", "ERROR")
                    self.attempt_recovery(svc, status)
            else:
                self.health[svc]["failures"] = 0
                if not was_healthy:
                    self.log(f"{svc} recovered", "INFO")
        
        # 2. Check MT5
        mt5_status, mt5_detail = self.check_mt5()
        self.health["MT5"]["status"] = mt5_status
        if mt5_status != "HEALTHY":
            self.log(f"MT5: {mt5_status} - {mt5_detail}", "WARNING")
        
        # 3. Check Database
        db_status, db_detail = self.check_database()
        self.health["Database"]["status"] = db_status
        if db_status != "HEALTHY":
            self.log(f"Database: {db_status} - {db_detail}", "ERROR")
        
        # 4. Check Position Sync
        ps_status, ps_detail = self.check_position_sync()
        self.health["PositionSync"]["status"] = ps_status
        if ps_status != "HEALTHY":
            self.log(f"PositionSync: {ps_status} - {ps_detail}", "WARNING")
        
        # 5. Run signal freshness check every 5 cycles (50 seconds)
        if hasattr(self, '_freshness_counter'):
            self._freshness_counter += 1
        else:
            self._freshness_counter = 0
        if self._freshness_counter % 5 == 0:
            self.run_signal_freshness_check()
        
        # 6. Calculate overall health
        healthy = sum(1 for v in self.health.values() if v.get("status") in ("SERVICE_RUNNING", "HEALTHY"))
        total = len(self.health)
        score = round(healthy / total * 100, 1)
        
        # Log summary every 30 cycles (5 minutes)
        if self._freshness_counter % 30 == 0:
            self.log(f"Health: {score}% ({healthy}/{total} healthy, {self.recovery_count} recoveries)", "INFO")
    
    def run(self):
        self.log("Health Daemon started", "INFO")
        counter = 0
        while True:
            try:
                self.run_once()
                counter += 1
                time.sleep(10)
            except KeyboardInterrupt:
                self.log("Health Daemon stopped", "INFO")
                break
            except Exception as e:
                self.log(f"Health daemon error: {e}", "ERROR")
                time.sleep(30)

if __name__ == "__main__":
    daemon = HealthDaemon()
    daemon.run()
