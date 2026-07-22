from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import AssetClass, Direction
@dataclass(frozen=True)
class PortfolioPosition:
    symbol:str; asset_class:AssetClass; direction:Direction; risk_pct:Decimal; base_currency:str; quote_currency:str
class PortfolioIntelligenceEngine:
    def exposure(self, positions:list[PortfolioPosition])->dict:
        data={"total_risk":sum((p.risk_pct for p in positions),Decimal("0")),"by_asset":{},"by_currency":{},"correlated_positions":0}
        for p in positions:
            data["by_asset"][p.asset_class.value]=data["by_asset"].get(p.asset_class.value,Decimal("0"))+p.risk_pct
            for c in [p.base_currency,p.quote_currency]: data["by_currency"][c]=data["by_currency"].get(c,Decimal("0"))+p.risk_pct
        data["correlated_positions"]=sum(1 for v in data["by_currency"].values() if v>Decimal("3"))
        return data
    def dynamic_limit(self, regime:str, base_limit:Decimal=Decimal("12"))->Decimal:
        return base_limit*Decimal("0.6") if "HIGH_VOLATILITY" in regime or "RISK_OFF" in regime else base_limit*Decimal("1.2") if "RISK_ON" in regime else base_limit
