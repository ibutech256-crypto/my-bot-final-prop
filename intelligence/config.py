from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import time

@dataclass(frozen=True)
class ValidationPolicy:
    conflict_mode: str = "PENALTY"  # PENALTY or HARD_BLOCK
    daily_order_block_penalty: Decimal = Decimal("25")
    htf_bias_penalty: Decimal = Decimal("20")
    minimum_post_penalty_score: Decimal = Decimal("70")

@dataclass(frozen=True)
class KillZoneDefinition:
    name: str
    start_utc: time
    end_utc: time
    enabled: bool = True

@dataclass(frozen=True)
class CorrelationRule:
    reference_symbol: str
    affected_assets: tuple[str, ...]
    bullish_blocks: tuple[str, ...] = ()
    bearish_blocks: tuple[str, ...] = ()
    mode: str = "PENALTY"  # DISABLED, PENALTY, HARD_BLOCK, WEIGHT_ADJUSTMENT
    penalty: Decimal = Decimal("15")
    enabled: bool = True

@dataclass(frozen=True)
class IntelligenceConfig:
    validation_policy: ValidationPolicy = ValidationPolicy()
    kill_zones: tuple[KillZoneDefinition, ...] = field(default_factory=lambda: (
        KillZoneDefinition("London Kill Zone", time(7,0), time(10,0)),
        KillZoneDefinition("New York Kill Zone", time(12,0), time(15,0)),
        KillZoneDefinition("London Close", time(15,0), time(16,30)),
        KillZoneDefinition("Power Hour", time(19,0), time(20,0)),
        KillZoneDefinition("Asian Expansion", time(0,0), time(3,0), enabled=False),
    ))
    backup_retention_days: int = 30
    administrator_auto_approval: bool = False
