import MetaTrader5 as mt5
import os
from datetime import datetime

login = int(os.getenv("MT5_LOGIN", "436005794"))
pw = os.getenv("MT5_PASSWORD", "1234#Dt@")
sv = os.getenv("MT5_SERVER", "Exness-MT5Trial9")

mt5.initialize()
mt5.login(login, pw, sv)

# Check for ticket 3007182573
now = datetime.now()
deals = mt5.history_deals_get(now.timestamp() - 86400 * 3, now.timestamp() + 1) or []
print(f"Total deals in last 3 days: {len(deals)}")

for d in deals:
    if str(d.ticket) == "3007182573" or "CADCHF" in d.symbol.upper():
        typ = "BUY" if d.type == 0 else "SELL" if d.type == 1 else f"OTHER({d.type})"
        entry = "IN" if d.entry == 0 else "OUT" if d.entry == 1 else "INOUT" if d.entry == 2 else f"OTHER({d.entry})"
        print(f"DEAL: ticket={d.ticket} symbol={d.symbol} {typ} {entry}")
        print(f"  volume={d.volume} price={d.price} profit={d.profit:.2f}")
        print(f"  commission={d.commission:.2f} swap={d.swap:.2f}")
        print(f"  position_id={d.position_id} time={datetime.fromtimestamp(d.time)}")
        print(f"  comment={d.comment}")

# Check if position is still open
pos = mt5.positions_get(symbol="CADCHFm")
if pos:
    for p in pos:
        print(f"\nACTIVE POSITION: ticket={p.ticket} entry={p.price_open} current={p.price_current}")
        print(f"  sl={p.sl} tp={p.tp} profit={p.profit:.2f}")
else:
    print("\nNo active CADCHFm position")

mt5.shutdown()
