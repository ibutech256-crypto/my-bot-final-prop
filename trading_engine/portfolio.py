from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import AssetClass, Direction, SymbolSpec
@dataclass(frozen=True)
class Exposure:
    symbol: str; asset_class: AssetClass; direction: Direction; risk_pct: Decimal; notional: Decimal
class PortfolioEngine:
    def group_key(self, symbol: str, asset_class: AssetClass) -> str:
        text=symbol.upper()
        if asset_class==AssetClass.FOREX: return text[:3] + "/" + text[3:6] if len(text)>=6 else text
        if asset_class==AssetClass.CRYPTO: return "CRYPTO"
        return asset_class.value
    def permits(self, exposures: list[Exposure], spec: SymbolSpec, new_risk_pct: Decimal, max_group_risk_pct: Decimal = Decimal("5"), max_total_risk_pct: Decimal = Decimal("12")) -> tuple[bool,str]:
        total=sum((e.risk_pct for e in exposures),Decimal("0"))+new_risk_pct
        if total>max_total_risk_pct: return False,"Total portfolio risk limit exceeded"
        key=self.group_key(spec.symbol,spec.asset_class)
        group=sum((e.risk_pct for e in exposures if self.group_key(e.symbol,e.asset_class)==key),Decimal("0"))+new_risk_pct
        if group>max_group_risk_pct: return False,f"Correlated exposure limit exceeded for {key}"
        return True,"Portfolio exposure accepted"
