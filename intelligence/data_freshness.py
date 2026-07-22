from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

@dataclass(frozen=True)
class FreshnessResult:
    fresh: bool
    latency_ms: Decimal
    source_timestamp: datetime
    checked_at: datetime
    reason: str

class TimestampValidationEngine:
    """Hard gate for market data freshness before any trade calculation or execution.

    Institutional execution must never calculate from stale price data. The default
    500 ms threshold is intentionally strict for fast index and crypto sweeps.
    """
    def __init__(self, max_latency_ms: Decimal = Decimal("500")):
        if max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")
        self.max_latency_ms = max_latency_ms

    def validate(self, source_timestamp: datetime, now: datetime | None = None) -> FreshnessResult:
        checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        ts = source_timestamp.astimezone(timezone.utc)
        latency = Decimal(str((checked_at - ts).total_seconds() * 1000))
        if latency < 0:
            return FreshnessResult(False, latency, ts, checked_at, "Source timestamp is in the future; clock synchronisation failure")
        if latency > self.max_latency_ms:
            return FreshnessResult(False, latency, ts, checked_at, f"Market data latency {latency} ms exceeds {self.max_latency_ms} ms threshold")
        return FreshnessResult(True, latency, ts, checked_at, "Market data timestamp is fresh")

    def assert_fresh(self, source_timestamp: datetime, now: datetime | None = None) -> FreshnessResult:
        result = self.validate(source_timestamp, now)
        if not result.fresh:
            raise TimeoutError(result.reason)
        return result
