from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from trading_engine.types import Direction, TradeSetup
@dataclass(frozen=True)
class ExecutionRequest:
    symbol: str; direction: Direction; volume: Decimal; entry: Decimal; stop_loss: Decimal; take_profit: Decimal; comment: str; magic: int
@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool; broker_ticket: str; broker_response: dict; message: str
class BrokerGateway(Protocol):
    def place_market_order(self, request: ExecutionRequest) -> ExecutionResult: ...
    def modify_position(self, ticket: str, stop_loss: Decimal, take_profit: Decimal) -> ExecutionResult: ...
    def close_partial(self, ticket: str, volume: Decimal) -> ExecutionResult: ...
class ExecutionEngine:
    def __init__(self, gateway: BrokerGateway | None = None, signal_only: bool = True, manual_confirmation: bool = False):
        self.gateway=gateway; self.signal_only=signal_only; self.manual_confirmation=manual_confirmation
    def execute(self, setup: TradeSetup) -> ExecutionResult:
        if self.signal_only: return ExecutionResult(False,"",{"mode":"SIGNAL_ONLY"},"Signal generated without execution")
        if self.manual_confirmation: return ExecutionResult(False,"",{"mode":"MANUAL_CONFIRMATION"},"Manual confirmation required")
        if self.gateway is None: raise RuntimeError("Broker gateway is required for automated execution")
        req=ExecutionRequest(setup.symbol,setup.direction,setup.position_size.final_lot_size,setup.entry,setup.stop_loss,setup.take_profit_2,"RomeoTPT institutional execution",260628)
        return self.gateway.place_market_order(req)
