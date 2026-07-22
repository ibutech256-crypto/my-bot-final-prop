from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import Direction
@dataclass(frozen=True)
class ManagementPlan:
    stop_loss: Decimal; tp1: Decimal; tp2: Decimal; tp3: Decimal; break_even_trigger: Decimal; trailing_distance: Decimal; partials: tuple[Decimal, Decimal, Decimal]
class TradeManagementEngine:
    def build_plan(self, direction: Direction, entry: Decimal, stop_loss: Decimal, rr1: Decimal=Decimal("1"), rr2: Decimal=Decimal("2"), rr3: Decimal=Decimal("3")) -> ManagementPlan:
        risk=abs(entry-stop_loss)
        if risk<=0: raise ValueError("Entry and stop loss must differ")
        if direction==Direction.BUY:
            return ManagementPlan(stop_loss, entry+risk*rr1, entry+risk*rr2, entry+risk*rr3, entry+risk, risk, (Decimal("0.33"),Decimal("0.33"),Decimal("0.34")))
        return ManagementPlan(stop_loss, entry-risk*rr1, entry-risk*rr2, entry-risk*rr3, entry-risk, risk, (Decimal("0.33"),Decimal("0.33"),Decimal("0.34")))
    def trailing_stop(self, direction: Direction, current_price: Decimal, current_sl: Decimal, trailing_distance: Decimal) -> Decimal:
        proposed=current_price-trailing_distance if direction==Direction.BUY else current_price+trailing_distance
        return max(current_sl, proposed) if direction==Direction.BUY else min(current_sl, proposed)
