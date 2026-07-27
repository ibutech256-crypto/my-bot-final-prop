"""Check current MT5 positions and account status."""
import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")
from broker_engine.mt5_client import MT5Client

client = MT5Client(
    login=int(os.getenv("MT5_LOGIN", "436005794")),
    password=os.getenv("MT5_PASSWORD", "1234#Dt@"),
    server=os.getenv("MT5_SERVER", "Exness-MT5Trial9")
)
client.connect()

# Account info
info = client.account_info()
if info:
    print(f"Balance: ${info['balance']:.2f}")
    print(f"Equity: ${info['equity']:.2f}")

# Current positions
positions = client.mt5.positions_get() or []
print(f"\nOpen positions on MT5: {len(positions)}")
total_pnl = 0
for p in positions:
    total_pnl += p.profit
    direction = "BUY" if p.type == 0 else "SELL"
    print(f"  #{p.ticket} {p.symbol} {direction} Vol={p.volume} PnL=${p.profit:.2f}")
print(f"Total P&L: ${total_pnl:.2f}")

if len(positions) > 0:
    print("\nPositions are still open. Need to wait for them to close naturally or close manually.")
else:
    print("\n✅ No open positions! New trades can enter.")
