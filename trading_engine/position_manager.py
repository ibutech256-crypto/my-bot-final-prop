"""Position Management Daemon - manages open trades every 1 second."""
import os, sys, time, json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
import MetaTrader5 as mt5

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import django; django.setup()
from django.utils import timezone as dj_tz
from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol, Signal, Order

class PositionManager:
    def __init__(self):
        self.running = False
        self.last_check = {}
    
    def connect_mt5(self):
        login = int(os.getenv("MT5_LOGIN", "436005794"))
        password = os.getenv("MT5_PASSWORD", "1234#Dt@")
        server = os.getenv("MT5_SERVER", "Exness-MT5Trial9")
        if not mt5.initialize():
            return False
        if not mt5.login(login, password, server):
            mt5.shutdown()
            return False
        return True
    
    def check_tp1(self, pos, entry, sl, tp1, tp2, tp3, direction):
        """Check if TP1 (1:1) has been hit - close 50%, move SL to breakeven."""
        current = pos.price_current
        if direction == "BUY" and current >= float(tp1):
            return self.execute_partial_close(pos, 0.5, entry)
        elif direction == "SELL" and current <= float(tp1):
            return self.execute_partial_close(pos, 0.5, entry)
        return False
    
    def execute_partial_close(self, pos, fraction, entry_price):
        """Close a fraction of position, move SL to breakeven."""
        close_vol = round(pos.volume * fraction, 2)
        if close_vol < 0.01:
            return False
        
        is_buy = pos.type == 0
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return False
        
        close_price = tick.bid if is_buy else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_vol,
            "type": close_type,
            "position": pos.ticket,
            "price": float(close_price),
            "deviation": 20,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result and result.retcode in (10008, 10009):
            remaining = pos.volume - close_vol
            if remaining >= 0.01:
                sl_mod = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": pos.ticket,
                    "sl": float(entry_price),
                    "tp": pos.tp,
                }
                mt5.order_send(sl_mod)
            
            # Update DB
            db_pos = OpenPosition.objects.filter(broker_ticket=str(pos.ticket)).first()
            if db_pos:
                db_pos.volume = Decimal(str(remaining))
                if fraction >= 0.5:
                    db_pos.stop_loss = Decimal(str(entry_price))
                db_pos.save()
                
                # Update signal
                if db_pos.order and db_pos.order.signal:
                    db_pos.order.signal.status = "PROTECTED" if fraction >= 0.5 else "PARTIAL_TP1"
                    db_pos.order.signal.save()
            return True
        return False
    
    def check_tp2(self, pos, entry, tp2):
        """Check if TP2 has been hit - close remaining."""
        current = pos.price_current
        direction = "BUY" if pos.type == 0 else "SELL"
        if direction == "BUY" and current >= float(tp2):
            return self.close_full_position(pos)
        elif direction == "SELL" and current <= float(tp2):
            return self.close_full_position(pos)
        return False
    
    def close_full_position(self, pos):
        is_buy = pos.type == 0
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return False
        close_price = tick.bid if is_buy else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
            "volume": pos.volume, "type": close_type, "position": pos.ticket,
            "price": float(close_price), "deviation": 20,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result and result.retcode in (10008, 10009):
            db_pos = OpenPosition.objects.filter(broker_ticket=str(pos.ticket)).first()
            if db_pos and db_pos.order and db_pos.order.signal:
                db_pos.order.signal.status = "CLOSED_TP"
                db_pos.order.signal.save()
            if db_pos:
                db_pos.is_deleted = True
                db_pos.save()
            return True
        return False
    
    def check_sl_hit(self, pos):
        """Check if SL hit - update status."""
        # MT5 closes positions automatically on SL hit
        # We just need to sync the status
        db_pos = OpenPosition.objects.filter(broker_ticket=str(pos.ticket)).first()
        if not db_pos:
            return
        if db_pos.order and db_pos.order.signal:
            db_pos.order.signal.status = "CLOSED_SL"
            db_pos.order.signal.save()
        db_pos.is_deleted = True
        db_pos.save()
    
    def run_once(self):
        """Single check cycle."""
        if not self.connect_mt5():
            return
        positions = mt5.positions_get() or []
        db_positions = OpenPosition.objects.filter(is_deleted=False)
        db_tickets = set(p.broker_ticket for p in db_positions)
        mt5_tickets = set(str(p.ticket) for p in positions)
        
        # Remove stale DB positions
        for dbp in db_positions:
            if dbp.broker_ticket not in mt5_tickets:
                self.check_sl_hit(None)
                dbp.is_deleted = True
                dbp.save()
        
        # Check each position for TP targets
        for pos in positions:
            ticket = str(pos.ticket)
            dbp = OpenPosition.objects.filter(broker_ticket=ticket).first()
            if not dbp:
                continue
            
            dbp.current_price = Decimal(str(pos.price_current))
            dbp.unrealized_profit = Decimal(str(pos.profit))
            dbp.save()
            
            if not dbp.order or not dbp.order.signal:
                continue
                
            sig = dbp.order.signal
            entry = float(dbp.entry_price)
            sl = float(dbp.stop_loss)
            tp1 = entry + abs(entry - sl) * 1.0 if dbp.direction == "BUY" else entry - abs(entry - sl) * 1.0
            tp2 = entry + abs(entry - sl) * 2.0 if dbp.direction == "BUY" else entry - abs(entry - sl) * 2.0
            direction = dbp.direction
            
            if sig.status not in ["PROTECTED", "RUNNER", "CLOSED_TP", "CLOSED_SL"]:
                # Check TP1
                hit_tp1 = (direction == "BUY" and pos.price_current >= tp1) or                           (direction == "SELL" and pos.price_current <= tp1)
                if hit_tp1 and sig.status != "PARTIAL_TP1":
                    if self.execute_partial_close(pos, 0.5, entry):
                        sig.status = "PROTECTED"
                        sig.save()
                        continue
                
                # Check TP2
                hit_tp2 = (direction == "BUY" and pos.price_current >= tp2) or                           (direction == "SELL" and pos.price_current <= tp2)
                if hit_tp2:
                    if self.close_full_position(pos):
                        continue
        
        mt5.shutdown()
    
    def run_loop(self):
        self.running = True
        while self.running:
            try:
                self.run_once()
                time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                time.sleep(5)

if __name__ == "__main__":
    pm = PositionManager()
    pm.run_loop()
