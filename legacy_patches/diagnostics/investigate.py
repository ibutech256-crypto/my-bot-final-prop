"""Investigate why EURNZDm (ACTIVE, KOD=True, Score=88) is NOT executing."""
import os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, ".")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta, datetime
from backend.apps.trading.models import Signal, OpenPosition, Order, TradingAccount
from decimal import Decimal

# ===== 1. Check EURNZDm signal =====
print("=== EURNZDm SIGNAL ===")
eurnzd = Signal.objects.filter(symbol__symbol="EURNZDm", status="ACTIVE").order_by("-created_at").first()
if eurnzd:
    print(f"ID={eurnzd.id}")
    print(f"Direction: {eurnzd.direction}")
    print(f"Score: {eurnzd.confidence}")
    print(f"Entry: {eurnzd.entry_price}")
    print(f"SL: {eurnzd.stop_loss}")
    print(f"TP: {eurnzd.take_profit}")
    print(f"Status: {eurnzd.status}")
    print(f"Created: {eurnzd.created_at}")
    print(f"Strategy: {eurnzd.strategy_name}")
    print(f"Expires at: {eurnzd.expires_at}")
    print(f"Symbol tradeable: {eurnzd.symbol.is_tradeable}")
else:
    print("No ACTIVE EURNZDm signal found")

# ===== 2. Check if there are already orders for EURNZDm =====
print("\n=== EURNZDm ORDERS ===")
orders = Order.objects.filter(symbol__symbol="EURNZDm").order_by("-created_at")[:5]
print(f"Total orders: {orders.count()}")
for o in orders:
    print(f"  ID={o.id} Status={o.status} Type={o.order_type} Vol={o.requested_volume} Price={o.requested_price}")
    print(f"    BrokerTicket={o.broker_ticket} Rejection={o.rejection_reason}")
    print(f"    Created={o.created_at}")
    if o.signal:
        print(f"    SignalID={o.signal.id}")

# ===== 3. Check engine log for EURNZDm =====
print("\n=== Checking engine log (last 200 lines) ===")
log_path = r"C:\prop-frim-bot\logs\TradingMT5Engine.log"
try:
    with open(log_path, "r", errors="replace") as f:
        lines = f.readlines()
    eurnzd_lines = [l for l in lines if "EURNZD" in l]
    for l in eurnzd_lines[-20:]:
        print(f"  {l.strip()[:200]}")
except FileNotFoundError:
    print("Log file not found")

# ===== 4. Check all ACTIVE signals and scores =====
print("\n=== All ACTIVE signals (from DB) ===")
for s in Signal.objects.filter(status="ACTIVE").order_by("-created_at"):
    print(f"  ID={s.id} {s.symbol.symbol} {s.direction} Score={s.confidence} Created={s.created_at} Expires={s.expires_at}")

# ===== 5. Check if signal is stale/expired =====
if eurnzd:
    age = (datetime.now(timezone.utc) - eurnzd.created_at).total_seconds()
    print(f"\nSignal age: {age/60:.1f} minutes")
    # Check if it should have been processed
    if eurnzd.expires_at:
        print(f"Expired: {datetime.now(timezone.utc) > eurnzd.expires_at}")

# ===== 6. Check what the dedup looks like from engine side =====
print("\n=== Checking engine dedup code ===")
with open(r"C:\prop-frim-bot\backend\apps\trading\management\commands\run_mt5_engine.py", "r") as f:
    engine = f.read()

# Find the dedup logic
for i, line in enumerate(engine.split('\n')):
    if "recent = Signal.objects.filter" in line or "existing_active" in line:
        print(f"  Line {i+1}: {line.strip()[:150]}")
    if "status__in" in line:
        print(f"  Line {i+1}: {line.strip()[:150]}")
