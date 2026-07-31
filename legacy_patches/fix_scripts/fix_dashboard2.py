"""Final dashboard fix - sync position and signals."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from backend.apps.trading.models import OpenPosition, TradingAccount, TradingSymbol, Signal

# STEP 1: Fix OpenPositionViewSet
print("=== STEP 1: Fix view queryset ===")
views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    vc = f.read()

old_qs = "class OpenPositionViewSet(ActiveModelViewSet): queryset=OpenPosition.objects.all();"
new_qs = "class OpenPositionViewSet(ActiveModelViewSet): queryset=OpenPosition.objects.filter(is_deleted=False);"

if old_qs in vc:
    vc = vc.replace(old_qs, new_qs)
    with open(views_path, "w") as f:
        f.write(vc)
    print("✅ OpenPositionViewSet fixed: filters is_deleted=False")
else:
    print("⚠️ Pattern not found, checking current definition...")
    idx = vc.find("OpenPositionViewSet")
    if idx >= 0:
        end = vc.find(";", idx+50)
        print(f"  Current: {vc[idx:end+1]}")

# STEP 2: Sync MT5 position to DB
print("\n=== STEP 2: Sync MT5 position ===")
import MetaTrader5 as mt5
login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)
positions = mt5.positions_get() or []
acct = TradingAccount.objects.first()

for pos in positions:
    ticket = str(pos.ticket)
    sym_obj, _ = TradingSymbol.objects.get_or_create(symbol=pos.symbol)
    direction = "BUY" if pos.type == 0 else "SELL"
    
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
    print(f"  SYNCED: {pos.symbol} ticket={ticket} profit={pos.profit:.2f}")

mt5.shutdown()

# STEP 3: Re-mark old KOD=False ACTIVE signals to WATCHLIST
print("\n=== STEP 3: Clean old KOD=False ACTIVE signals ===")
old_active = Signal.objects.filter(status="ACTIVE", rationale__icontains="KOD=False")
print(f"Old KOD=False ACTIVE signals: {old_active.count()}")
count = old_active.update(status="WATCHLIST")
print(f"  {count} moved to WATCHLIST")

# STEP 4: Verify final state
print("\n=== STEP 4: Final DB state ===")
db_pos = OpenPosition.objects.filter(is_deleted=False)
print(f"OpenPositions: {db_pos.count()}")
for p in db_pos:
    print(f"  {p.symbol.symbol} {p.direction} ticket={p.broker_ticket} pnl={p.unrealized_profit}")

recent = Signal.objects.filter(created_at__gte=datetime.now(timezone.utc)-timedelta(hours=6))
print(f"\nRecent signals (6hr): {recent.count()}")
print(f"  ACTIVE: {recent.filter(status='ACTIVE').count()}")
new_actives = recent.filter(status='ACTIVE')
for s in new_actives:
    has_kod = "KOD=True" in (s.rationale or "")
    print(f"  ID={s.id} {s.symbol.symbol} Score={s.confidence} KOD={has_kod}")

print("\n✅ DASHBOARD SYNC COMPLETE")
