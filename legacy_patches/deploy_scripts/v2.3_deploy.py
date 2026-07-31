"""V2.3 Institutional Upgrade - Position Manager, Multi-TP, Correlation, Audit."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from decimal import Decimal
from datetime import datetime, timezone, timedelta
from django.utils import timezone as dj_tz

# ============ PART 1: Signal Status Extension ============
print("=== PART 1: Extending Signal Status choices ===")
models_path = r"C:\prop-frim-bot\backend\apps\trading\models.py"
with open(models_path, "r") as f:
    mc = f.read()

# Check current SignalStatus
if "WATCHLIST" in mc and "ACTIVE_MONITORING" not in mc:
    old_status = """class SignalDirection(models.TextChoices): BUY=\"BUY\",\"Buy\"; SELL=\"SELL\",\"Sell\"; HOLD=\"HOLD\",\"Hold\"
class SignalStatus(models.TextChoices): DRAFT=\"DRAFT\",\"Draft\"; ACTIVE=\"ACTIVE\",\"Active\"; FILLED=\"FILLED\",\"Filled\"; EXPIRED=\"EXPIRED\",\"Expired\"; CANCELLED=\"CANCELLED\",\"Cancelled\""""
    
    new_status = """class SignalDirection(models.TextChoices): BUY=\"BUY\",\"Buy\"; SELL=\"SELL\",\"Sell\"; HOLD=\"HOLD\",\"Hold\"
class SignalStatus(models.TextChoices): 
    WATCHLIST=\"WATCHLIST\",\"Watchlist\"; ACTIVE_MONITORING=\"ACTIVE_MONITORING\",\"Active Monitoring\"
    EXECUTION_READY=\"EXECUTION_READY\",\"Execution Ready\"; EXECUTED=\"EXECUTED\",\"Executed\"
    PARTIAL_TP1=\"PARTIAL_TP1\",\"Partial TP1\"; PROTECTED=\"PROTECTED\",\"Protected\"
    RUNNER=\"RUNNER\",\"Runner\"; CLOSED_TP=\"CLOSED_TP\",\"Closed TP\"
    CLOSED_SL=\"CLOSED_SL\",\"Closed SL\"; EXPIRED=\"EXPIRED\",\"Expired\"
    CANCELLED=\"CANCELLED\",\"Cancelled\"
    BLOCKED_SPREAD=\"BLOCKED_SPREAD\",\"Blocked Spread\"
    BLOCKED_NEWS=\"BLOCKED_NEWS\",\"Blocked News\"
    BLOCKED_SESSION=\"BLOCKED_SESSION\",\"Blocked Session\"
    BLOCKED_CORRELATION=\"BLOCKED_CORRELATION\",\"Blocked Correlation\"
    BLOCKED_MARGIN=\"BLOCKED_MARGIN\",\"Blocked Margin\""""
    
    if old_status in mc:
        mc = mc.replace(old_status, new_status)
        with open(models_path, "w") as f:
            f.write(mc)
        print("SignalStatus extended with lifecycle states")
    else:
        print("Status pattern not found!")
        idx = mc.find("class SignalStatus")
        if idx >= 0:
            end = mc.find("\nclass ", idx+10)
            print(f"Current: {mc[idx:end][:200]}")
else:
    print("Lifecycle statuses already exist")

# ============ PART 2: Position Manager ============
print("\n=== PART 2: Creating Position Manager ===")
pm_code = '''"""Position Management Daemon - manages open trades every 1 second."""
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
                hit_tp1 = (direction == "BUY" and pos.price_current >= tp1) or \
                          (direction == "SELL" and pos.price_current <= tp1)
                if hit_tp1 and sig.status != "PARTIAL_TP1":
                    if self.execute_partial_close(pos, 0.5, entry):
                        sig.status = "PROTECTED"
                        sig.save()
                        continue
                
                # Check TP2
                hit_tp2 = (direction == "BUY" and pos.price_current >= tp2) or \
                          (direction == "SELL" and pos.price_current <= tp2)
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
'''

with open(r"C:\prop-frim-bot\trading_engine\position_manager.py", "w") as f:
    f.write(pm_code)
print("Position Manager created")

# ============ PART 3: Correlation Shield ============
print("\n=== PART 3: Adding Correlation Shield ===")
correlation_code = '''
"""Portfolio Correlation Shield - prevents correlated exposure."""
from decimal import Decimal
from backend.apps.trading.models import OpenPosition

CURRENCY_MAP = {
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURNZD", "EURCAD"],
    "GBP": ["GBPUSD", "GBPJPY", "GBPCHF", "GBPAUD", "GBPNZD", "GBPCAD"],
    "USD": ["USDJPY", "USDCHF", "USDCAD", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"],
    "AUD": ["AUDUSD", "AUDJPY", "AUDCHF", "AUDNZD", "AUDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF", "AUDCHF", "CHFJPY", "CADCHF"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "AUDCAD", "CADJPY", "CADCHF"],
    "NZD": ["NZDUSD", "NZDJPY", "NZDCAD", "AUDNZD", "GBPNZD"],
}

MAX_CORRELATED = 2  # Max positions per currency direction

def get_currency_exposure(currency, direction):
    """Count open positions involving a specific currency."""
    positions = OpenPosition.objects.filter(is_deleted=False)
    count = 0
    for p in positions:
        sym = p.symbol.symbol.replace("m", "")
        base = sym[:3] if sym[:3] in CURRENCY_MAP else None
        quote = sym[3:6] if len(sym) >= 6 and sym[3:6] in CURRENCY_MAP else None
        if base == currency or quote == currency:
            if p.direction == direction or (quote == currency and p.direction != direction):
                count += 1
    return count

def check_correlation(symbol, direction):
    """Check if adding this trade would exceed correlation limits."""
    sym = symbol.replace("m", "")
    base = sym[:3] if sym[:3] in CURRENCY_MAP else None
    quote = sym[3:6] if len(sym) >= 6 and sym[3:6] in CURRENCY_MAP else None
    
    for currency in [base, quote]:
        if not currency:
            continue
        exposure = get_currency_exposure(currency, direction)
        if exposure >= MAX_CORRELATED:
            return False, f"BLOCKED_CORRELATION: {currency} exposure {exposure}/{MAX_CORRELATED}"
    return True, "PASS Correlation"
'''

with open(r"C:\prop-frim-bot\trading_engine\correlation_shield.py", "w") as f:
    f.write(correlation_code)
print("Correlation Shield created")

# ============ PART 4: Engine Integration Hooks ============
print("\n=== PART 4: Adding engine integration hooks ===")
engine_path = r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py"
with open(engine_path, "r") as f:
    engine = f.read()

# Add correlation shield import
if "from trading_engine.correlation_shield" not in engine:
    old = "from trading_engine.eat_phase_engine import EATPhaseEngine"
    new = old + "\nfrom trading_engine.correlation_shield import check_correlation"
    if old in engine:
        engine = engine.replace(old, new)
        with open(engine_path, "w") as f:
            f.write(engine)
        print("Correlation shield import added")
    else:
        print("Could not find EATPhaseEngine import")

# Add position manager thread start
if "position_manager" not in engine:
    old_start = "self.stdout.write(f\"MT5 Real-Time Polling Loop active tracking {len(visible_symbols)} Exness symbols (5s intervals)...\")"
    new_start = old_start + "\n        from trading_engine.position_manager import PositionManager\n        import threading\n        pm = PositionManager()\n        pm_thread = threading.Thread(target=pm.run_loop, daemon=True)\n        pm_thread.start()\n        self.stdout.write(\"Position Manager daemon started\")"
    if old_start in engine:
        engine = engine.replace(old_start, new_start)
        with open(engine_path, "w") as f:
            f.write(engine)
        print("Position manager thread added to engine startup")
    else:
        print("Could not find engine startup line")

# ============ PART 5: Validation ============
print("\n=== PART 5: Validation ===")
import py_compile
files = [
    r"C:\prop-frim-bot\trading_engine\position_manager.py",
    r"C:\prop-frim-bot\trading_engine\correlation_shield.py",
    r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py",
    r"C:\prop-frim-bot\backend\apps\trading\models.py",
]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  {os.path.basename(f)}: OK")
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERROR - {e}")

print("\n=== V2.3 DEPLOYMENT COMPLETE ===")
