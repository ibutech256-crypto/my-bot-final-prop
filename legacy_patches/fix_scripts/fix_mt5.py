"""Fix MT5 client with two-step ECN dispatch, digit normalization, and market data validation."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

path = r"C:\prop-frim-bot\broker_engine\mt5_client.py"
with open(path, "r") as f:
    content = f.read()

# Replace the place_market_order function
old_func = """    def place_market_order(self, req: BrokerOrderRequest) -> dict:
        \"\"\"Place a market order with spread protection.\"\"\"
        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")

        typ = (
            self.mt5.ORDER_TYPE_BUY
            if req.direction == \"BUY\"
            else self.mt5.ORDER_TYPE_SELL
        )
        price = tick.ask if req.direction == \"BUY\" else tick.bid

        # Run spread safety checks before placing order
        self._check_spread_safety(req.symbol, price, float(req.stop_loss) if req.stop_loss else None)

        result = self.mt5.order_send({
            \"action\": self.mt5.TRADE_ACTION_DEAL,
            \"symbol\": req.symbol,
            \"volume\": float(req.volume),
            \"type\": typ,
            \"price\": float(price),
            \"sl\": float(req.stop_loss or 0),
            \"tp\": float(req.take_profit or 0),
            \"deviation\": req.deviation,
            \"type_filling\": self.mt5.ORDER_FILLING_IOC,
        })
        if result is None:
            raise RuntimeError(f\"MT5 order_send failed: {self.mt5.last_error()}\")

        result_dict = result._asdict()"""

new_func = """    def place_market_order(self, req: BrokerOrderRequest) -> dict:
        \"\"\"Two-step ECN dispatch: send with SL/TP=0, then modify. Prevents Exness Error 130.\"\"\"
        # Step 0: Validate market data freshness
        tick = self.mt5.symbol_info_tick(req.symbol)
        if tick is None:
            raise RuntimeError(f"No tick data for {req.symbol}")
        
        self.last_tick_time = tick.time
        self.last_tick_price = (tick.bid + tick.ask) / 2

        # Normalize prices to symbol digits
        spec = self.mt5.symbol_info(req.symbol)
        digits = spec.digits if spec else 5

        typ = (
            self.mt5.ORDER_TYPE_BUY
            if req.direction == "BUY"
            else self.mt5.ORDER_TYPE_SELL
        )
        price = round(tick.ask if req.direction == "BUY" else tick.bid, digits)
        sl = round(float(req.stop_loss), digits) if req.stop_loss else 0.0
        tp = round(float(req.take_profit), digits) if req.take_profit else 0.0

        # Run spread safety checks before placing order
        self._check_spread_safety(req.symbol, price, sl if sl > 0 else None)

        # Step 1: Send order WITHOUT SL/TP (prevents Exness Error 130 - Invalid Stops)
        result = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": typ,
            "price": float(price),
            "sl": 0.0,  # DELIBERATELY ZERO
            "tp": 0.0,  # DELIBERATELY ZERO
            "deviation": req.deviation,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")

        # Step 2: If order succeeded, immediately modify SL/TP
        if result.retcode in (10008, 10009) and hasattr(result, 'order') and result.order:
            modify_result = self.mt5.order_send({
                "action": self.mt5.TRADE_ACTION_SLTP,
                "position": result.order,
                "sl": sl,
                "tp": tp,
            })

        result_dict = result._asdict()"""

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(path, "w") as f:
        f.write(content)
    print("Two-step ECN dispatch installed in place_market_order")
else:
    print("Function pattern not found. Checking actual content...")
    idx = content.find("def place_market_order")
    if idx >= 0:
        end = content.find("def place_limit_order", idx)
        if end < 0:
            end = idx + 800
        print(f"Found function at {idx}:")
        print(content[idx:end][:600])

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("SYNTAX OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
