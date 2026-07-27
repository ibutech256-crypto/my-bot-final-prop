"""Fix dashboard sync - positions and signals display."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol, Signal

# ===== STEP 1: Sync MT5 positions to DB =====
print("=== STEP 1: Sync MT5->DB ===")
import MetaTrader5 as mt5
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

if not mt5.initialize():
    print("MT5 INIT FAILED")
else:
    mt5.login(login, pw, sv)
    
    positions = mt5.positions_get() or []
    print(f"MT5 positions: {len(positions)}")
    
    acct = TradingAccount.objects.first()
    if not acct:
        print("No TradingAccount found!")
    else:
        for pos in positions:
            ticket = str(pos.ticket)
            sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
            direction = "BUY" if pos.type == 0 else "SELL"
            
            # Mark all existing positions for this symbol as deleted first
            OpenPosition.objects.filter(account=acct, symbol=sym_obj).update(is_deleted=True)
            
            # Create/update current position
            OpenPosition.objects.update_or_create(
                account=acct,
                broker_ticket=ticket,
                defaults={
                    "symbol": sym_obj,
                    "direction": direction,
                    "volume": Decimal(str(pos.volume)),
                    "entry_price": Decimal(str(pos.price_open)),
                    "current_price": Decimal(str(pos.price_current)),
                    "stop_loss": Decimal(str(pos.sl)) if pos.sl else None,
                    "take_profit": Decimal(str(pos.tp)) if pos.tp else None,
                    "unrealized_profit": Decimal(str(pos.profit)),
                    "opened_at": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                    "is_deleted": False,
                }
            )
            print(f"  SYNCED: {pos.symbol} ticket={ticket} vol={pos.volume} pnl={pos.profit:.2f}")
    
    mt5.shutdown()

# ===== STEP 2: Verify API returns positions correctly =====
print("\n=== STEP 2: OpenPosition DB state ===")
acct = TradingAccount.objects.first()
db_pos = OpenPosition.objects.filter(is_deleted=False)
print(f"Active OpenPositions in DB: {db_pos.count()}")
for p in db_pos:
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} entry={p.entry_price} pnl={p.unrealized_profit}")

# ===== STEP 3: Check signals display =====
print("\n=== STEP 3: Signal status check ===")
recent = Signal.objects.filter(created_at__gte=datetime.now(timezone.utc)-timedelta(hours=6))
print(f"Signals last 6hrs: {recent.count()}")
print(f"  ACTIVE: {recent.filter(status='ACTIVE').count()}")
print(f"  WATCHLIST: {recent.filter(status='WATCHLIST').count()}")

print("\nACTIVE signals:")
for s in recent.filter(status='ACTIVE'):
    has_kod = "KOD=True" in (s.rationale or "")
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} KOD={has_kod}")

# ===== STEP 4: Make sure the OpenPositionViewSet excludes deleted =====
print("\n=== STEP 4: ViewSet filter check ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

idx = vc.find("class OpenPositionViewSet")
if idx >= 0:
    end = vc.find("\nclass ", idx+1)
    section = vc[idx:end] if end > idx else vc[idx:idx+500]
    print(f"Current OpenPositionViewSet:\n{section[:400]}")
    
    if "is_deleted" not in section:
        print("\n⚠️ OpenPositionViewSet missing is_deleted=False filter!")
        # Check if it has a custom queryset or uses default
        if "queryset" in section:
            # Already has queryset, check if we need to modify
            qs_line = [l for l in section.split('\n') if 'queryset' in l][0]
            print(f"  Current queryset: {qs_line.strip()}")

print("\n✅ DONE")
