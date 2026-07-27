"""Signal Freshness Validator - archives stale/expired signals automatically."""
import os, sys, time, json
from datetime import datetime, timezone, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import django; django.setup()
from django.utils import timezone as dj_tz
from backend.apps.trading.models import Signal, TradingSymbol
from decimal import Decimal

class SignalFreshnessValidator:
    """Validates signal freshness every 30 seconds. Archives stale signals."""
    
    MAX_SIGNAL_AGE_MINUTES = 120  # 2 hours max for any signal
    SESSION_TIMEOUTS = {
        "ASIAN": 60,
        "LONDON": 120,
        "NEW_YORK": 120,
        "CLOSED": 30,
    }
    
    def __init__(self):
        self.archived_count = 0
        self.last_check = None
    
    def validate_all(self):
        """Check all non-closed signals for freshness."""
        now = datetime.now(timezone.utc)
        results = {"archived": 0, "stale_found": 0, "errors": []}
        
        # Get all signals that are still considered "live" (not closed)
        live_statuses = [
            "WATCHLIST", "ACTIVE_MONITORING", "EXECUTION_READY",
            "EXECUTED", "PARTIAL_TP1", "PROTECTED", "RUNNER"
        ]
        signals = Signal.objects.filter(status__in=live_statuses, is_deleted=False)
        
        for sig in signals:
            try:
                age_minutes = (now - sig.created_at).total_seconds() / 60
                should_archive = False
                reason = None
                
                # 1. Age check - hard limit
                if age_minutes > self.MAX_SIGNAL_AGE_MINUTES:
                    should_archive = True
                    reason = f"EXCEEDED_MAX_AGE ({age_minutes:.0f}/{self.MAX_SIGNAL_AGE_MINUTES} min)"
                
                # 2. Price moved significantly from entry
                if not should_archive and sig.entry_price:
                    try:
                        import MetaTrader5 as mt5
                        login = int(os.getenv("MT5_LOGIN", "436005794"))
                        password = os.getenv("MT5_PASSWORD", "1234#Dt@")
                        server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
                        mt5.initialize()
                        mt5.login(login, password, server)
                        tick = mt5.symbol_info_tick(sig.symbol.symbol)
                        mt5.shutdown()
                        if tick:
                            current = Decimal(str(tick.bid))
                            entry = sig.entry_price
                            risk = abs(entry - sig.stop_loss) if sig.stop_loss else Decimal("0.001")
                            if risk > 0:
                                move_pct = abs(current - entry) / risk * 100
                                if move_pct > 200:  # Price moved more than 2x the SL distance
                                    should_archive = True
                                    reason = f"PRICE_MOVED {move_pct:.0f}% OF SL DISTANCE"
                    except:
                        pass
                
                if should_archive:
                    sig.status = "EXPIRED"
                    sig.rationale = (sig.rationale or "") + f" [ARCHIVED: {reason}]"
                    sig.save()
                    results["archived"] += 1
                    self.archived_count += 1
                    
            except Exception as e:
                results["errors"].append(f"Signal {sig.id}: {e}")
        
        self.last_check = now
        return results

if __name__ == "__main__":
    validator = SignalFreshnessValidator()
    results = validator.validate_all()
    print(f"Archived {results['archived']} stale signals")
