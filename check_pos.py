
import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")
from broker_engine.mt5_client import MT5Client

client = MT5Client(
    login=int(os.getenv("MT5_LOGIN", "436005794")),
    password=os.getenv("MT5_PASSWORD", "1234#Dt@"),
    server=os.getenv("MT5_SERVER", "Exness-MT5Trial9")
)
client.connect()

info = client.account_info()
if info:
    print(f"Balance: ${info['balance']:.2f}")
    print(f"Equity: ${info['equity']:.2f}")
    print(f"Free Margin: ${info['margin_free']:.2f}")
    print(f"Margin Level: {info['margin_level']:.2f}%" if info.get('margin_level') else "")

positions = client.mt5.positions_get() or []
print(f"\nOpen positions: {len(positions)}")
total_pnl = 0
for p in sorted(positions, key=lambda x: x.ticket):
    total_pnl += p.profit
    direction = "BUY" if p.type == 0 else "SELL"
    print(f"  #{p.ticket} {p.symbol} {direction} Vol={p.volume} Entry={p.price_open:.5f} Current={p.price_current:.5f} SL={p.sl} TP={p.tp} PnL=${p.profit:.2f}")

print(f"\nTotal P&L: ${total_pnl:.2f}")
