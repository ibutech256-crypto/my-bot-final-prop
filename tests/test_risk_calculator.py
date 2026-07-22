from decimal import Decimal
from risk_engine.calculator import PositionSizeRequest,RiskCalculator
def test_position_size():
    r=RiskCalculator().calculate_position_size(PositionSizeRequest(Decimal("10000"),Decimal("1"),Decimal("1.1000"),Decimal("1.0950"),Decimal("100000"),Decimal("0.01"),Decimal("0.01"),Decimal("100")))
    assert r.lots >= Decimal("0.01")
