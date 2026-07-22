from dataclasses import dataclass
from decimal import Decimal
import importlib
@dataclass(frozen=True)
class BrokerOrderRequest: symbol:str; direction:str; volume:Decimal; price:Decimal|None; stop_loss:Decimal|None; take_profit:Decimal|None; deviation:int=20
class MT5Client:
    def __init__(self,login:int,password:str,server:str,path:str|None=None): self.login=login; self.password=password; self.server=server; self.path=path; self.mt5=importlib.import_module("MetaTrader5")
    def connect(self)->None:
        if not self.mt5.initialize(path=self.path,login=self.login,password=self.password,server=self.server): raise ConnectionError(f"MT5 initialization failed: {self.mt5.last_error()}")
    def shutdown(self)->None: self.mt5.shutdown()
    def account_info(self)->dict:
        info=self.mt5.account_info()
        if info is None: raise RuntimeError(f"Cannot read MT5 account info: {self.mt5.last_error()}")
        return info._asdict()
    def place_market_order(self,req:BrokerOrderRequest)->dict:
        tick=self.mt5.symbol_info_tick(req.symbol)
        if tick is None: raise RuntimeError(f"No tick data for {req.symbol}")
        typ=self.mt5.ORDER_TYPE_BUY if req.direction=="BUY" else self.mt5.ORDER_TYPE_SELL; price=tick.ask if req.direction=="BUY" else tick.bid
        
        # Raw Spread protection check inside broker client (v1.9.2)
        spec = self.mt5.symbol_info(req.symbol)
        if spec:
            point = Decimal(str(spec.point if spec.point else "0.00001"))
            spread_points = Decimal(str(spec.spread if spec.spread else "5"))
            raw_spread = spread_points * point
            pip_size = point * Decimal("10") if spec.digits in [3, 5] else point
            
            # 1. Reject if raw spread > 2.5 pips
            if raw_spread > Decimal("2.5") * pip_size:
                raise RuntimeError(f"SPREAD REJECTED: Raw spread {float(raw_spread)} exceeds 2.5 pips limit.")
                
            # 2. Reject if spread > 15% of Entry-to-SL distance
            if req.stop_loss:
                risk_dist = abs(Decimal(str(price)) - Decimal(str(req.stop_loss)))
                if risk_dist > 0 and raw_spread / risk_dist > Decimal("0.15"):
                    raise RuntimeError(f"SPREAD REJECTED: Raw spread {float(raw_spread)} exceeds 15% of risk buffer ({float(risk_dist)}).")

        result=self.mt5.order_send({"action":self.mt5.TRADE_ACTION_DEAL,"symbol":req.symbol,"volume":float(req.volume),"type":typ,"price":float(price),"sl":float(req.stop_loss or 0),"tp":float(req.take_profit or 0),"deviation":req.deviation,"type_filling":self.mt5.ORDER_FILLING_IOC})
        if result is None: raise RuntimeError(f"MT5 order_send failed: {self.mt5.last_error()}")
        return result._asdict()
