"""Position Synchronization Engine - MT5 is the single source of truth.
Runs every second, keeps DB/API/WS in sync with MT5."""
import os, sys, time, json, threading
from decimal import Decimal
from datetime import datetime, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import django; django.setup()
from django.utils import timezone as dj_tz
from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol, Signal, Order

import MetaTrader5 as mt5

class PositionSyncEngine:
    def __init__(self):
        self.running = False
        self.sync_count = 0
        self.last_sync_time = None
        self.repair_count = 0
        self.mt5_connected = False
    
    def connect_mt5(self):
        login = int(os.getenv("MT5_LOGIN", "436005794"))
        password = os.getenv("MT5_PASSWORD", "1234#Dt@")
        server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
        if not mt5.initialize():
            return False
        if not mt5.login(login, password, server):
            mt5.shutdown()
            return False
        self.mt5_connected = True
        return True
    
    def sync_once(self):
        """Single synchronization cycle."""
        sync_log = {"timestamp": datetime.now(timezone.utc).isoformat(), "actions": []}
        
        if not self.connect_mt5():
            sync_log["error"] = "MT5 connection failed"
            return sync_log
        
        try:
            # 1. Get all MT5 positions
            mt5_positions = mt5.positions_get() or []
            mt5_tickets = set(str(p.ticket) for p in mt5_positions)
            
            # 2. Get all DB positions
            db_positions = OpenPosition.objects.filter(is_deleted=False)
            db_tickets = set(p.broker_ticket for p in db_positions)
            
            # 3. Find orphans (in DB but not in MT5)
            orphans = db_tickets - mt5_tickets
            for ticket in orphans:
                dbp = OpenPosition.objects.filter(broker_ticket=ticket).first()
                if dbp:
                    if dbp.order and dbp.order.signal:
                        dbp.order.signal.status = "CLOSED_SL"
                        dbp.order.signal.save()
                    dbp.is_deleted = True
                    dbp.save()
                    sync_log["actions"].append(f"ORPHAN_CLOSED:{ticket}:{dbp.symbol.symbol}")
                    self.repair_count += 1
            
            # 4. Find missing (in MT5 but not in DB)
            missing = mt5_tickets - db_tickets
            for ticket in missing:
                pos = next((p for p in mt5_positions if str(p.ticket) == ticket), None)
                if pos:
                    acct = TradingAccount.objects.first()
                    sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
                    direction = "BUY" if pos.type == 0 else "SELL"
                    OpenPosition.objects.create(
                        account=acct,
                        symbol=sym_obj,
                        direction=direction,
                        volume=Decimal(str(pos.volume)),
                        entry_price=Decimal(str(pos.price_open)),
                        current_price=Decimal(str(pos.price_current)),
                        stop_loss=Decimal(str(pos.sl)) if pos.sl else None,
                        take_profit=Decimal(str(pos.tp)) if pos.tp else None,
                        unrealized_profit=Decimal(str(pos.profit)),
                        opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),
                        broker_ticket=ticket,
                    )
                    sync_log["actions"].append(f"MISSING_CREATED:{ticket}:{pos.symbol}")
                    self.repair_count += 1
            
            # 5. Update existing positions (SL/TP/price/profit sync)
            for pos in mt5_positions:
                ticket = str(pos.ticket)
                dbp = OpenPosition.objects.filter(broker_ticket=ticket).first()
                if not dbp:
                    continue
                changed = []
                new_current = Decimal(str(pos.price_current))
                if dbp.current_price != new_current:
                    dbp.current_price = new_current
                    changed.append("price")
                new_profit = Decimal(str(pos.profit))
                if dbp.unrealized_profit != new_profit:
                    dbp.unrealized_profit = new_profit
                    changed.append("profit")
                new_sl = Decimal(str(pos.sl)) if pos.sl else None
                if dbp.stop_loss != new_sl:
                    dbp.stop_loss = new_sl
                    changed.append("sl")
                new_tp = Decimal(str(pos.tp)) if pos.tp else None
                if dbp.take_profit != new_tp:
                    dbp.take_profit = new_tp
                    changed.append("tp")
                new_vol = Decimal(str(pos.volume))
                if dbp.volume != new_vol:
                    dbp.volume = new_vol
                    changed.append("volume")
                if changed:
                    dbp.save()
                    sync_log["actions"].append(f"SYNCED:{ticket}:{','.join(changed)}")
            
            # 6. Update account info
            acct_info = mt5.account_info()
            if acct_info:
                acct = TradingAccount.objects.first()
                if acct:
                    new_bal = Decimal(str(acct_info.balance))
                    new_eq = Decimal(str(acct_info.equity))
                    new_margin = Decimal(str(acct_info.margin))
                    if acct.balance != new_bal or acct.equity != new_eq:
                        acct.balance = new_bal
                        acct.equity = new_eq
                        acct.margin = new_margin
                        acct.save()
            
            self.sync_count += 1
            self.last_sync_time = time.time()
            
        except Exception as e:
            sync_log["error"] = str(e)
        finally:
            mt5.shutdown()
        
        return sync_log
    
    def run_loop(self):
        self.running = True
        while self.running:
            try:
                self.sync_once()
                time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
            except:
                time.sleep(5)

if __name__ == "__main__":
    sync = PositionSyncEngine()
    sync.run_loop()
