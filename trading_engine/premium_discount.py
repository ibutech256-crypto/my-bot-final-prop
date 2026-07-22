from __future__ import annotations
from decimal import Decimal
from trading_engine.types import CRTRange, Direction
class PremiumDiscountEngine:
    def zone(self, price: Decimal, crt: CRTRange) -> str:
        mid=(crt.high+crt.low)/Decimal("2")
        return "PREMIUM" if price>mid else "DISCOUNT" if price<mid else "EQUILIBRIUM"
    def permits(self, direction: Direction, price: Decimal, crt: CRTRange) -> bool:
        z=self.zone(price,crt)
        return (direction==Direction.BUY and z in {"DISCOUNT","EQUILIBRIUM"}) or (direction==Direction.SELL and z in {"PREMIUM","EQUILIBRIUM"})
