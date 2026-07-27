import os
import sys
sys.path.append('C:/prop-frim-bot')
from dotenv import load_dotenv
load_dotenv('C:/prop-frim-bot/.env')
from broker_engine.mt5_client import MT5Client

client = MT5Client(
    login=int(os.getenv('MT5_LOGIN')),
    password=os.getenv('MT5_PASSWORD'),
    server=os.getenv('MT5_SERVER'),
    path=os.getenv('MT5_PATH')
)
client.connect()

symbol = "EURUSDm"
tick = client.mt5.symbol_info_tick(symbol)
if not tick:
    print(f"Failed to get tick for {symbol}")
    client.shutdown()
    sys.exit(1)

print(f"Placing test market BUY order on {symbol}...")
request = {
    "action": client.mt5.TRADE_ACTION_DEAL,
    "symbol": symbol,
    "volume": 0.01,
    "type": client.mt5.ORDER_TYPE_BUY,
    "price": tick.ask,
    "deviation": 20,
    "sl": tick.ask - 0.0020,  # Safe Stop Loss (20 pips away)
    "tp": tick.ask + 0.0040,  # Safe Take Profit (40 pips away)
    "type_filling": client.mt5.ORDER_FILLING_IOC
}

res = client.mt5.order_send(request)
if res:
    print("Execution retcode:", res.retcode)
    print("Execution comment:", res.comment)
    print("Order ticket:", res.order)
    print("Deal ticket:", res.deal)
else:
    print("Failed to send order, no response.")

client.shutdown()
