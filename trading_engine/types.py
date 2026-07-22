from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Any

class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

class Timeframe(str, Enum):
    M1="M1"; M5="M5"; M15="M15"; H1="H1"; H4="H4"; D1="D1"; W1="W1"; MN1="MN1"

class AssetClass(str, Enum):
    FOREX="FOREX"; METAL="METAL"; INDEX="INDEX"; COMMODITY="COMMODITY"; CRYPTO="CRYPTO"; OTHER="OTHER"

@dataclass(frozen=True)
class Candle:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    completed: bool = True
    def body(self) -> Decimal: return abs(self.close - self.open)
    def range(self) -> Decimal: return self.high - self.low
    def upper_wick(self) -> Decimal: return self.high - max(self.open, self.close)
    def lower_wick(self) -> Decimal: return min(self.open, self.close) - self.low
    def direction(self) -> Direction:
        if self.close > self.open: return Direction.BUY
        if self.close < self.open: return Direction.SELL
        return Direction.NEUTRAL

@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    asset_class: AssetClass
    broker_name: str
    server: str
    account_currency: str
    leverage: Decimal
    contract_size: Decimal
    digits: int
    tick_size: Decimal
    tick_value: Decimal
    volume_step: Decimal
    min_volume: Decimal
    max_volume: Decimal
    spread_points: Decimal
    commission_per_lot: Decimal
    swap_long: Decimal
    swap_short: Decimal
    execution_mode: str
    filling_modes: tuple[str, ...]
    order_types: tuple[str, ...]
    trade_hours: tuple[tuple[time, time], ...]
    visible: bool
    margin_initial: Decimal = Decimal("0")
    def normalize_volume(self, raw_volume: Decimal) -> Decimal:
        if raw_volume <= 0: return Decimal("0")
        stepped = (raw_volume / self.volume_step).to_integral_value(rounding=ROUND_DOWN) * self.volume_step
        return max(self.min_volume, min(self.max_volume, stepped))

@dataclass(frozen=True)
class AccountSnapshot:
    broker_name: str
    server: str
    currency: str
    balance: Decimal
    equity: Decimal
    free_margin: Decimal
    margin_level: Decimal
    leverage: Decimal

@dataclass(frozen=True)
class SwingPoint:
    index: int
    time: datetime
    price: Decimal
    kind: str

@dataclass(frozen=True)
class CRTRange:
    high: Decimal
    low: Decimal
    start_index: int
    end_index: int
    internal_high: Decimal
    internal_low: Decimal
    external_high: Decimal
    external_low: Decimal
    state: str
    target_high: Decimal
    target_low: Decimal

@dataclass(frozen=True)
class LiquidityEvent:
    direction: Direction
    swept_level: Decimal
    kind: str
    candle_index: int
    failed: bool
    description: str

@dataclass(frozen=True)
class StructureState:
    bias: Direction
    last_event: str
    swings: tuple[SwingPoint, ...]
    expansion: bool
    compression: bool
    accumulation: bool
    distribution: bool

@dataclass(frozen=True)
class Zone:
    direction: Direction
    low: Decimal
    high: Decimal
    start_index: int
    end_index: int
    state: str
    strength: Decimal
    kind: str

@dataclass(frozen=True)
class SessionState:
    name: str
    kill_zone: bool
    liquid: bool
    reason: str

@dataclass(frozen=True)
class NewsState:
    trading_allowed: bool
    blocking_events: tuple[str, ...] = ()

@dataclass(frozen=True)
class ScoreBreakdown:
    total: Decimal
    components: dict[str, Decimal]
    passed: bool

@dataclass(frozen=True)
class PositionSize:
    risk_amount: Decimal
    raw_position_size: Decimal
    margin_required: Decimal
    maximum_allowed_position: Decimal
    rounded_broker_position: Decimal
    final_lot_size: Decimal

@dataclass(frozen=True)
class TradeSetup:
    symbol: str
    timeframe: Timeframe
    direction: Direction
    entry: Decimal
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal
    take_profit_3: Decimal
    expected_rr: Decimal
    score: ScoreBreakdown
    crt_range: CRTRange
    liquidity_event: LiquidityEvent
    structure: StructureState
    order_blocks: tuple[Zone, ...]
    fair_value_gaps: tuple[Zone, ...]
    session: SessionState
    position_size: PositionSize
    explanation: str
    audit: dict[str, Any] = field(default_factory=dict)
