from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

@dataclass(frozen=True)
class CacheStats:
    entries: int
    bytes_estimate: int
    oldest_entry: datetime | None

class ResamplerCache:
    """Bounded in-process cache for synthetic timeframe bars with deterministic cleanup.

    The engine stores compact Python candle lists instead of pandas dataframes. Even so,
    background workers must purge old references before high-volume sessions to avoid
    VPS memory pressure. Cleanup is safe to run every hour from Celery beat.
    """
    def __init__(self, ttl_minutes: int = 90, max_entries: int = 512):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_entries = max_entries
        self._lock = RLock()
        self._items: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            created_at, value = item
            if datetime.now(timezone.utc) - created_at > self.ttl:
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (datetime.now(timezone.utc), value)
            self._enforce_bounds()

    def cleanup(self, now: datetime | None = None) -> CacheStats:
        checked_at = now or datetime.now(timezone.utc)
        with self._lock:
            expired = [k for k, (created, _) in self._items.items() if checked_at - created > self.ttl]
            for key in expired:
                self._items.pop(key, None)
            self._enforce_bounds()
            oldest = min((created for created, _ in self._items.values()), default=None)
            return CacheStats(len(self._items), self._estimate_bytes(), oldest)

    def clear(self) -> CacheStats:
        with self._lock:
            self._items.clear()
            return CacheStats(0, 0, None)

    def _enforce_bounds(self) -> None:
        if len(self._items) <= self.max_entries:
            return
        ordered = sorted(self._items.items(), key=lambda item: item[1][0])
        for key, _ in ordered[:len(self._items) - self.max_entries]:
            self._items.pop(key, None)

    def _estimate_bytes(self) -> int:
        total = 0
        for key, (_, value) in self._items.items():
            total += len(key.encode()) + len(repr(value).encode())
        return total

GLOBAL_RESAMPLER_CACHE = ResamplerCache()
