import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
django.setup()
from backend.apps.trading.models import OpenPosition, Signal
from broker_engine.mt5_client import MT5Client
import os as _os

# Check how many positions are actually open in MT5
login = int(_os.getenv("MT5_LOGIN", "436005794"))
password = _os.getenv("MT5_PASSWORD", "1234#Dt@")
server = _os.getenv("MT5_SERVER", "Exness-MT5Trial9")

client = MT5Client(login=login, password=password, server=server)
try:
    client.connect()
    # Get actual open positions from MT5
    mt5_positions = client.mt5.positions_get()
    if mt5_positions:
        mt5_tickets = set(str(p.ticket) for p in mt5_positions)
        print(f"MT5 live positions: {len(mt5_tickets)}")
    else:
        mt5_tickets = set()
        print("MT5 live positions: 0")
    
    # Get DB positions
    db_positions = OpenPosition.objects.filter(is_deleted=False)
    print(f"DB positions: {db_positions.count()}")
    
    # Find DB positions not in MT5
    stale = 0
    for pos in db_positions:
        if str(pos.broker_ticket) not in mt5_tickets:
            # Position is stale, mark it closed
            stale += 1
            pos.is_deleted = True
            pos.save()
    
    print(f"Stale positions cleaned: {stale}")
    print(f"Remaining DB positions: {OpenPosition.objects.filter(is_deleted=False).count()}")
    
    client.shutdown()
except Exception as e:
    print(f"Error: {e}")
    # Even without MT5 access, expire old positions
    from django.utils import timezone
    from datetime import timedelta
    old = timezone.now() - timedelta(hours=48)
    expired = OpenPosition.objects.filter(is_deleted=False, opened_at__lt=old)
    cnt = expired.count()
    expired.update(is_deleted=True)
    print(f"Expired old positions (48h): {cnt}")
    print(f"Remaining: {OpenPosition.objects.filter(is_deleted=False).count()}")

