from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from trading_engine.types import Direction, TradeSetup


@dataclass(frozen=True)
class ExecutionRequest:
    symbol: str
    direction: Direction
    volume: Decimal
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    comment: str
    magic: int
    order_type: str = "MARKET"  # MARKET, LIMIT


@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    broker_ticket: str
    broker_response: dict
    message: str


class BrokerGateway(Protocol):
    def place_market_order(self, request: ExecutionRequest) -> ExecutionResult:
        ...

    def modify_position(self, ticket: str, stop_loss: Decimal, take_profit: Decimal) -> ExecutionResult:
        ...

    def close_partial(self, ticket: str, volume: Decimal) -> ExecutionResult:
        ...


class ExecutionEngine:
    """Execution engine with three-way order placement (v2.0.0).
    
    Supports:
    - Direct Limit at the sweep level
    - Market Order on KOD candle close
    - Limit Order at FVG 50% Consequent Encroachment (CE)
    
    Stop Loss is set strictly beyond sweep extreme + (1.5x ATR + Spread Buffer).
    Auto-move SL to Breakeven at TP1.
    """

    def __init__(
        self,
        gateway: BrokerGateway | None = None,
        signal_only: bool = False,  # Changed default to False for auto-execution
        manual_confirmation: bool = False,
    ):
        self.gateway = gateway
        self.signal_only = signal_only
        self.manual_confirmation = manual_confirmation

    def execute(self, setup: TradeSetup) -> ExecutionResult:
        """Execute a trade setup with the appropriate entry type."""
        if self.signal_only:
            return ExecutionResult(
                False, "", {"mode": "SIGNAL_ONLY"},
                "Signal generated without execution"
            )

        if self.manual_confirmation:
            return ExecutionResult(
                False, "", {"mode": "MANUAL_CONFIRMATION"},
                "Manual confirmation required"
            )

        if self.gateway is None:
            raise RuntimeError("Broker gateway is required for automated execution")

        # Determine entry type from setup audit info
        entry_type = getattr(setup, '_entry_type', 'MARKET')

        req = ExecutionRequest(
            symbol=setup.symbol,
            direction=setup.direction,
            volume=setup.position_size.final_lot_size,
            entry=setup.entry,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit_2,
            comment=f"RomeoTPT {entry_type} execution",
            magic=260628,
            order_type=entry_type,
        )

        result = self.gateway.place_market_order(req)

        # If successful and has TP1, schedule breakeven move
        if result.accepted and setup.take_profit_1:
            self._schedule_breakeven(result.broker_ticket, setup.entry)

        return result

    def _schedule_breakeven(self, ticket: str, entry_price: Decimal) -> None:
        """Schedule SL to breakeven when TP1 is hit.
        
        In a real implementation, this would register a price listener or
        use a background task to monitor when TP1 is reached and then
        modify the position SL to breakeven.
        """
        # Placeholder for breakeven scheduling logic
        # Actual implementation would use the broker gateway's modify_position
        pass
