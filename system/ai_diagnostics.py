"""AI Diagnostics - analyzes system health, detects patterns, recommends fixes."""
import os, sys, json, time
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import django; django.setup()
from backend.apps.trading.models import Signal, OpenPosition, Order

class AIDiagnostics:
    """Analyzes system state every 5 minutes, produces health report."""
    
    def __init__(self):
        self.report_count = 0
    
    def analyze(self):
        """Full system diagnostic."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": 100.0,
            "problems": [],
            "recommendations": [],
            "auto_fixes_applied": [],
            "pending_issues": [],
        }
        deductions = 0
        
        # 1. Check signal staleness
        try:
            from django.utils import timezone as dj_tz
            recent = Signal.objects.filter(
                created_at__gte=dj_tz.now() - timedelta(hours=2)
            ).count()
            total = Signal.objects.count()
            active = Signal.objects.filter(
                status__in=["WATCHLIST", "ACTIVE_MONITORING", "EXECUTION_READY"]
            ).count()
            old_active = Signal.objects.filter(
                status="WATCHLIST",
                created_at__lt=dj_tz.now() - timedelta(hours=4)
            ).count()
            
            if old_active > 10:
                report["problems"].append(f"{old_active} stale WATCHLIST signals >4hrs old")
                report["recommendations"].append("Run SignalFreshnessValidator.archive_stale()")
                deductions += 10
            
            report["signals"] = {
                "total": total,
                "recent_2hr": recent,
                "active": active,
                "stale": old_active,
            }
        except Exception as e:
            report["problems"].append(f"Signal check failed: {e}")
            deductions += 15
        
        # 2. Check position sync
        try:
            mt5_pos = 0
            db_pos = OpenPosition.objects.filter(is_deleted=False).count()
            try:
                import MetaTrader5 as mt5
                login = int(os.getenv("MT5_LOGIN", "436005794"))
                password = os.getenv("MT5_PASSWORD", "1234#Dt@")
                server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
                if mt5.initialize() and mt5.login(login, password, server):
                    mt5_pos = len(mt5.positions_get() or [])
                    mt5.shutdown()
            except:
                pass
            
            if mt5_pos != db_pos:
                report["problems"].append(f"Position mismatch: MT5={mt5_pos} DB={db_pos}")
                report["recommendations"].append("Run PositionSyncEngine.sync_once()")
                deductions += 20
            
            report["positions"] = {"mt5": mt5_pos, "db": db_pos}
        except Exception as e:
            report["problems"].append(f"Position check failed: {e}")
            deductions += 10
        
        # 3. Check for duplicate signals
        try:
            from django.db.models import Count
            dupes = Signal.objects.values(
                "symbol_id", "direction", "strategy_name"
            ).annotate(cnt=Count("id")).filter(cnt__gt=1, is_deleted=False)
            dupe_count = sum(d["cnt"] - 1 for d in dupes) if dupes else 0
            
            if dupe_count > 0:
                report["problems"].append(f"{dupe_count} duplicate signals detected")
                report["recommendations"].append("Run deduplication: keep newest per symbol/direction/timeframe")
                deductions += 5
            
            report["duplicates"] = dupe_count
        except Exception as e:
            report["problems"].append(f"Duplicate check failed: {e}")
        
        # 4. Check execution failures
        try:
            recent_orders = Order.objects.filter(
                created_at__gte=dj_tz.now() - timedelta(hours=24)
            )
            rejected = recent_orders.filter(status="REJECTED").count()
            filled = recent_orders.filter(status="FILLED").count()
            
            if rejected > filled and rejected > 3:
                report["problems"].append(f"High rejection rate: {rejected} rejected, {filled} filled")
                report["recommendations"].append("Check MT5 order settings, margin, and symbol specifications")
                deductions += 15
            
            report["orders"] = {"rejected": rejected, "filled": filled}
        except Exception as e:
            report["problems"].append(f"Order check failed: {e}")
        
        # 5. Calculate health score
        report["health_score"] = max(0, 100 - deductions)
        
        # 6. Generate severity
        if report["health_score"] >= 90:
            report["severity"] = "HEALTHY"
        elif report["health_score"] >= 70:
            report["severity"] = "DEGRADED"
        else:
            report["severity"] = "CRITICAL"
        
        self.report_count += 1
        return report

if __name__ == "__main__":
    diag = AIDiagnostics()
    report = diag.analyze()
    print(json.dumps(report, indent=2, default=str))
