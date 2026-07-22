from dataclasses import dataclass
from decimal import Decimal,ROUND_DOWN
@dataclass(frozen=True)
class PositionSizeRequest: equity:Decimal; risk_pct:Decimal; entry_price:Decimal; stop_loss:Decimal; pip_value_per_lot:Decimal; lot_step:Decimal; min_lot:Decimal; max_lot:Decimal
@dataclass(frozen=True)
class PositionSizeResult: lots:Decimal; cash_risk:Decimal; price_risk:Decimal
class RiskCalculator:
    def calculate_position_size(self,req:PositionSizeRequest)->PositionSizeResult:
        price_risk=abs(req.entry_price-req.stop_loss)
        if price_risk<=0: raise ValueError("stop_loss must differ from entry_price")
        cash_risk=req.equity*(req.risk_pct/Decimal("100")); raw=cash_risk/(price_risk*req.pip_value_per_lot)
        lots=(raw/req.lot_step).to_integral_value(rounding=ROUND_DOWN)*req.lot_step
        return PositionSizeResult(max(req.min_lot,min(req.max_lot,lots)),cash_risk,price_risk)
