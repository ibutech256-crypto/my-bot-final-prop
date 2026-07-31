import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")
from broker_engine.mt5_client import MT5Client

client = MT5Client(
    login=int(os.getenv("MT5_LOGIN", "436005794")),
    password=os.getenv("MT5_PASSWORD", "1234#Dt@"),
    server=os.getenv("MT5_SERVER", "Exness-MT5Trial9")
)
client.connect()

mt5_positions = client.mt5.positions_get() or []
print(f"Open MT5 positions: {len(mt5_positions)}")
for p in mt5_positions:
    print(f"  #{p.ticket} {p.symbol} {p.type} Vol={p.volume} SL={p.sl} TP={p.tp} Profit={p.profit:.2f}")

info = client.account_info()
if info:
    print(f"\nBalance: ${info['balance']:.2f}")
    print(f"Equity: ${info['equity']:.2f}")
    print(f"Free margin: ${info['margin_free']:.2f}")
