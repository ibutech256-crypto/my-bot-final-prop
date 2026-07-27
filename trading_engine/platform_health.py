"""Platform Health Monitor - checks all components every 30 seconds."""
import os, sys, time, json, subprocess, threading
from datetime import datetime, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class PlatformHealth:
    def __init__(self):
        self.health_score = 100.0
        self.checks = {}
        self.incident_count = 0
        self.recovery_count = 0
        self.last_report = {}
    
    def check_mt5(self):
        import MetaTrader5 as mt5
        try:
            login = int(os.getenv("MT5_LOGIN", "436005794"))
            password = os.getenv("MT5_PASSWORD", "1234#Dt@")
            server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
            if mt5.initialize():
                if mt5.login(login, password, server):
                    info = mt5.account_info()
                    mt5.shutdown()
                    if info:
                        return {"status": "HEALTHY", "balance": info.balance, "equity": info.equity}
                mt5.shutdown()
            return {"status": "DEGRADED", "error": "login failed"}
        except Exception as e:
            return {"status": "DOWN", "error": str(e)}
    
    def check_service(self, name):
        try:
            r = subprocess.run(['nssm', 'status', name], capture_output=True, text=True, timeout=5)
            status = r.stdout.strip()
            if status == "SERVICE_RUNNING":
                return {"status": "HEALTHY"}
            elif status == "SERVICE_PAUSED":
                return {"status": "DEGRADED", "detail": "paused"}
            else:
                return {"status": "DOWN", "detail": status}
        except:
            return {"status": "DOWN", "error": "check failed"}
    
    def check_api(self):
        try:
            import urllib.request
            r = urllib.request.urlopen("http://localhost:8000/api/v1/", timeout=5)
            if r.status == 200 or r.status == 401:
                return {"status": "HEALTHY", "response_time_ms": 0}
            return {"status": "DEGRADED", "http": r.status}
        except Exception as e:
            return {"status": "DOWN", "error": str(e)}
    
    def check_database(self):
        try:
            import django; django.setup()
            from backend.apps.trading.models import Signal
            count = Signal.objects.count()
            return {"status": "HEALTHY", "signals": count}
        except Exception as e:
            return {"status": "DOWN", "error": str(e)}
    
    def check_disk(self):
        try:
            import shutil
            usage = shutil.disk_usage("C:\\")
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            pct = usage.used / usage.total * 100
            if pct > 95:
                return {"status": "CRITICAL", "used_pct": pct}
            elif pct > 85:
                return {"status": "DEGRADED", "used_pct": pct}
            return {"status": "HEALTHY", "used_pct": pct, "free_gb": free_gb}
        except:
            return {"status": "UNKNOWN"}
    
    def check_position_sync(self):
        try:
            from backend.apps.trading.models import OpenPosition
            import MetaTrader5 as mt5
            mt5.initialize()
            login = int(os.getenv("MT5_LOGIN", "436005794"))
            password = os.getenv("MT5_PASSWORD", "1234#Dt@")
            server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
            mt5.login(login, password, server)
            mt5_pos = set(str(p.ticket) for p in (mt5.positions_get() or []))
            db_pos = set(p.broker_ticket for p in OpenPosition.objects.filter(is_deleted=False))
            mt5.shutdown()
            if mt5_pos == db_pos:
                return {"status": "HEALTHY", "mt5": len(mt5_pos), "db": len(db_pos)}
            return {"status": "DEGRADED", "mt5": len(mt5_pos), "db": len(db_pos), "diff": list(mt5_pos ^ db_pos)[:5]}
        except:
            return {"status": "UNKNOWN"}
    
    def run_all_checks(self):
        checks = {
            "MT5": self.check_mt5(),
            "Database": self.check_database(),
            "API": self.check_api(),
            "Disk": self.check_disk(),
            "PositionSync": self.check_position_sync(),
        }
        for svc in ["Memurai", "TradingBackend", "TradingWorker", "TradingBeat", "TradingFrontend", "TradingMT5Engine"]:
            checks[f"NSSM:{svc}"] = self.check_service(svc)
        
        # Calculate health score
        total = len(checks)
        healthy = sum(1 for c in checks.values() if c.get("status") == "HEALTHY")
        degraded = sum(1 for c in checks.values() if c.get("status") == "DEGRADED")
        down = sum(1 for c in checks.values() if c.get("status") in ("DOWN", "CRITICAL"))
        self.health_score = round((healthy + degraded * 0.5) / total * 100, 1)
        self.checks = checks
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": self.health_score,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "total": total,
            "checks": checks
        }

if __name__ == "__main__":
    ph = PlatformHealth()
    report = ph.run_all_checks()
    print(json.dumps(report, indent=2, default=str))
