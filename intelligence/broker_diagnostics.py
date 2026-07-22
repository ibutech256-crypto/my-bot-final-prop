from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.types import SymbolSpec
@dataclass(frozen=True)
class BrokerDiagnosticEvent:
    severity:str; code:str; message:str; metadata:dict
class BrokerDiagnosticsEngine:
    def compare_specs(self, previous:SymbolSpec, current:SymbolSpec)->tuple[BrokerDiagnosticEvent,...]:
        events=[]
        if previous.leverage != current.leverage: events.append(BrokerDiagnosticEvent("WARNING","LEVERAGE_CHANGED",f"{current.symbol} leverage changed {previous.leverage} -> {current.leverage}",{}))
        if previous.contract_size != current.contract_size: events.append(BrokerDiagnosticEvent("CRITICAL","CONTRACT_CHANGED",f"{current.symbol} contract changed",{}))
        if current.spread_points > previous.spread_points * Decimal("3") and previous.spread_points>0: events.append(BrokerDiagnosticEvent("WARNING","SPREAD_EXPANSION",f"{current.symbol} spread expanded",{"previous":str(previous.spread_points),"current":str(current.spread_points)}))
        if not current.visible: events.append(BrokerDiagnosticEvent("CRITICAL","SYMBOL_NOT_VISIBLE",f"{current.symbol} is not visible/tradeable",{}))
        return tuple(events)
