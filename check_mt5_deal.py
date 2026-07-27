import MetaTrader5 as mt5
import os
from datetime import datetime

login=int(os.getenv("MT5_LOGIN","436005794"))
pw=os.getenv("MT5_PASSWORD","1234#Dt@")
sv=os.getenv("MT5_SERVER","Exness-MT5Trial9")
mt5.initialize()
mt5.login(login,pw,sv)

# Get order history for ticket 3007182573
now = datetime.now()
history = mt5.history_deals_get(now.timestamp()-86400, now.timestamp()+1) or []
print(f"Total deals in last 24h: {len(history)}")
for d in history:
    if str(d.ticket) == "3007182573" or "CADCHF" in d.symbol.upper():
        typ = "BUY" if d.type == 0 else "SELL" if d.type == 1 else f"OTHER({d.type})"
        entry = "IN" if d.entry == 0 else "OUT" if d.entry == 1 else f"OTHER({d.entry})"
        print(f"DEAL: ticket={d.ticket} symbol={d.symbol} {typ} {entry} vol={d.volume} price={d.price} profit={d.profit:.2f} comm={d.commission:.2f} swap={d.swap:.2f} time={datetime.fromtimestamp(d.time)}")

# Current position
positions = mt5.positions_get(symbol="CADCHFm") or []
for p in positions:
    print(f"\nPOSITION: ticket={p.ticket} vol={p.volume} entry={p.price_open} current={p.price_current} sl={p.sl} tp={p.tp} profit={p.profit:.2f}")

# Current tick
tick = mt5.symbol_info_tick("CADCHFm")
if tick:
    print(f"\nCURRENT: bid={tick.bid} ask={tick.ask}")

mt5.shutdown()
