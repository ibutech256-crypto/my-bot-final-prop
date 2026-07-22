from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from trading_engine.types import NewsState
@dataclass(frozen=True)
class EconomicEvent:
    title: str; impact: str; currency: str; starts_at: datetime
class NewsFilterEngine:
    def __init__(self, before_minutes:int=15, after_minutes:int=15): self.before=timedelta(minutes=before_minutes); self.after=timedelta(minutes=after_minutes)
    def evaluate(self, now: datetime, symbol: str, events: list[EconomicEvent]) -> NewsState:
        now=now.astimezone(timezone.utc); blockers=[]; text=symbol.upper()
        for e in events:
            if e.impact.upper() != "HIGH": continue
            if e.currency.upper() not in text and e.currency.upper() not in {"USD","ALL"}: continue
            start=e.starts_at.astimezone(timezone.utc)
            if start-self.before <= now <= start+self.after: blockers.append(f"{e.currency} {e.title} at {start.isoformat()}")
        return NewsState(not blockers, tuple(blockers))
