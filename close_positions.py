import os, sys
sys.path.insert(0, "C:\\prop-frim-bot")
from broker_engine.mt5_client import MT5Client

client = MT5Client(
    login=int(os.getenv("MT5_LOGIN", "436005794")),
    password=os.getenv("MT5_PASSWORD", "1234#Dt@"),
    server=os.getenv("MT5_SERVER", "Exness-MT5Trial9")
)
client.connect()

# Get all positions
mt5_positions = client.mt5.positions_get() or []
print(f"Open positions: {len(mt5_positions)}")

for pos in mt5_positions:
    print(f"\nClosing #{pos.ticket} {pos.symbol} Vol={pos.volume} Profit={pos.profit:.2f}")
    
    # Get market data
    tick = client.mt5.symbol_info_tick(pos.symbol)
    if not tick or tick.bid == 0 or tick.ask == 0:
        print(f"  SKIP: Market closed for {pos.symbol}")
        continue
    
    # Determine close price and direction
    is_buy = (pos.type == client.mt5.ORDER_TYPE_BUY)
    close_price = tick.bid if is_buy else tick.ask
    
    close_request = {
        "action": client.mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": float(pos.volume),
        "type": client.mt5.ORDER_TYPE_SELL if is_buy else client.mt5.ORDER_TYPE_BUY,
        "position": pos.ticket,
        "price": float(close_price),
        "deviation": 100,
        "type_filling": client.mt5.ORDER_FILLING_IOC,
        "comment": "Auto-close stale"
    }
    
    result = client.mt5.order_send(close_request)
    if result:
        print(f"  Result: retcode={result.retcode}, comment={result.comment}")
        if result.retcode in (10008, 10009):
            print(f"  ✅ SUCCESS: Closed #{pos.ticket}")
        else:
            print(f"  ❌ FAILED: {result.comment}")
    else:
        print(f"  ❌ FAILED: No response from MT5")

print("\nDone closing positions!")
