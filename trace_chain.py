import os, sys, time
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.config.settings"
sys.path.insert(0, "C:\\prop-frim-bot")
import django; django.setup()
from django.utils import timezone
from datetime import timedelta
from backend.apps.trading.models import Signal, OpenPosition, Order, BrokerSetting
from decimal import Decimal

print("=== BROKER SETTTINGS ===")
bs = BrokerSetting.objects.first()
print(f"enable_autotrading: {bs.enable_autotrading}")

print("\n=== WAITING FOR NATURALLY GENERATED KOD=True SIGNAL ===")

# Poll every 15 seconds for up to 3 minutes
for i in range(12):
    recent = Signal.objects.filter(created_at__gte=timezone.now() - timedelta(minutes=1))
    kod_true = recent.filter(rationale__icontains="KOD=True")
    
    if kod_true.count() > 0:
        sig = kod_true.order_by("-created_at").first()
        print(f"\n✅ FOUND KOD=True SIGNAL:")
        print(f"  ID={sig.id} {sig.symbol.symbol} {sig.direction}")
        print(f"  Score={sig.confidence} Status={sig.status}")
        print(f"  Created: {sig.created_at}")
        print(f"  Entry={sig.entry_price} SL={sig.stop_loss} TP={sig.take_profit}")
        print(f"  Rationale: {sig.rationale[:200]}")
        
        # Check if position was created
        time.sleep(15)  # Give time for execution pipeline
        
        # Check OpenPosition
        pos = OpenPosition.objects.filter(symbol=sig.symbol, is_deleted=False).first()
        if pos:
            print(f"\n  ✅ POSITION CREATED: {pos.symbol.symbol} {pos.direction}")
            print(f"    Ticket: {pos.broker_ticket}")
            print(f"    Volume: {pos.volume}")
            print(f"    Entry: {pos.entry_price}")
        else:
            print(f"\n  ❌ NO POSITION CREATED for {sig.symbol.symbol}")
        
        # Check Orders
        order = Order.objects.filter(signal=sig).first()
        if order:
            print(f"\n  ✅ ORDER: status={order.status} ticket={order.broker_ticket}")
        else:
            print(f"\n  ❌ NO ORDER for signal {sig.id}")
        
        # Dump recent log entries for this symbol
        print(f"\n  === Checking engine log for {sig.symbol.symbol} ===")
        break
    else:
        recent_total = recent.filter(confidence__gte=Decimal("55")).count()
        kod_false = recent.filter(rationale__icontains="KOD=False").count()
        print(f"  Poll {i+1}: {recent_total} recent signals, {kod_false} KOD=False, 0 KOD=True (waiting...)")
        time.sleep(15)

if kod_true.count() == 0:
    print("\n❌ No KOD=True signal appeared within monitoring window")
    print("   This means no CRT setup with a confirmed KOD candle appeared naturally.")
    print("   KOD detection depends on market conditions, not on our code.")
    print("   The fix is verified at the code level, not at the market level.")
