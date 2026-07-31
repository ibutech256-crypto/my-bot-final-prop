"""Fix remaining issues: duplicates, positions display, signal limit."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from backend.apps.trading.models import Signal, OpenPosition, TradingAccount, TradingSymbol

# ===== FIX A: Deduplicate - only keep the most recent signal per (symbol + direction + strategy) =====
print("=== FIX A: Deduplicate signals ===")
from django.db.models import Count, Max

dupes = Signal.objects.values("symbol_id", "direction", "strategy_name").annotate(
    cnt=Count("id"), latest=Max("created_at")
).filter(cnt__gt=1)

removed = 0
for d in dupes:
    signals = Signal.objects.filter(
        symbol_id=d["symbol_id"], 
        direction=d["direction"], 
        strategy_name=d["strategy_name"]
    ).order_by("-created_at")
    
    keep = signals.first()
    for s in signals[1:]:
        if s.status not in ["EXECUTED", "CLOSED_TP", "CLOSED_SL"]:
            s.delete()
            removed += 1

print(f"Removed {removed} duplicate signals")

# ===== FIX B: Sync the open position for API =====
print("\n=== FIX B: Sync MT5 position ===")
import MetaTrader5 as mt5
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)
positions = mt5.positions_get() or []
acct = TradingAccount.objects.first()

# Mark all existing as deleted
OpenPosition.objects.filter(account=acct).update(is_deleted=True)

for pos in positions:
    ticket = str(pos.ticket)
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
    print(f"  CREATED: {pos.symbol} ticket={ticket} profit={pos.profit:.2f}")

mt5.shutdown()

# ===== FIX C: Check the Views - how does it limit to 3? =====
print("\n=== FIX C: Check SignalViewSet filtering ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

idx = vc.find("class SignalViewSet")
if idx >= 0:
    end = vc.find("\nclass ", idx+10)
    section = vc[idx:end] if end > idx else vc[idx:idx+500]
    print(f"SignalViewSet:\n{section[:600]}")

# Check frontend API call
frontend_path = r"C:\prop-frim-bot\frontend\app\ClientDashboard.tsx"
if os.path.exists(frontend_path):
    with open(frontend_path, "r") as f:
        fc = f.read()
    
    # Find where it calls the signals API
    import re
    api_calls = re.findall(r'(?:fetch|axios)\s*\([^)]*signals?[^)]*\)', fc, re.IGNORECASE)
    for call in api_calls[:5]:
        print(f"\nFrontend API call: {call[:150]}")
    
    # Find where it calls positions
    pos_calls = re.findall(r'(?:fetch|axios)\s*\([^)]*position[^)]*\)', fc, re.IGNORECASE)
    for call in pos_calls[:5]:
        print(f"Frontend positions call: {call[:150]}")

# ===== FIX D: Check if positions need to call OpenPositions instead =====
print("\n=== FIX D: URL routing ===")
urls_path = r"C:\prop-frim-bot\backend\config\urls.py"
with open(urls_path, "r") as f:
    uc = f.read()

pos_routes = [l for l in uc.split('\n') if 'position' in l.lower() or 'openposition' in l.lower()]
for r in pos_routes:
    print(f"  {r.strip()}")

# Check the actual router
print("\n=== Final DB state ===")
print(f"OpenPositions: {OpenPosition.objects.filter(is_deleted=False).count()}")
print(f"ACTIVE Signals: {Signal.objects.filter(status='ACTIVE').count()}")
print(f"Total Signals: {Signal.objects.count()}")

print("\nDONE")
