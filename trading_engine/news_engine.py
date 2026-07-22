from __future__ import annotations
import logging
import requests
import pytz
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger("trading")


class NewsBlackoutEngine:
    """
    High-Impact Economic News Blackout Engine.
    Dynamically fetches Red Folder events from Forex Factory weekly JSON calendar feed.
    Enforces a strict ±15 minute blackout window on related currency pairs.
    """
    def __init__(self, cache_ttl_hours: int = 6):
        self.eat_tz = pytz.timezone("Africa/Nairobi")
        self.utc_tz = pytz.utc
        self.blackout_pre_mins = 15
        self.blackout_post_mins = 15
        self.cache_ttl = cache_ttl_hours * 3600
        self.last_fetch: float = 0.0
        self.cached_events: List[Dict[str, Any]] = []

    def fetch_calendar_events(self) -> List[Dict[str, Any]]:
        """
        Fetches the Forex Factory weekly JSON economic calendar.
        """
        now = time.time()
        if now - self.last_fetch < self.cache_ttl and self.cached_events:
            return self.cached_events

        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            logger.info("NewsBlackoutEngine: Fetching live economic calendar from Forex Factory JSON feed...")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                events = []
                for item in data:
                    # Parse Forex Factory date, e.g. "2026-07-21T10:00:00-04:00"
                    date_str = item.get("date")
                    if not date_str:
                        continue
                    
                    try:
                        # Extract timezone offset or parse with standard datetime ISO parser
                        evt_dt = datetime.fromisoformat(date_str)
                        # Convert to UTC and EAT
                        evt_dt_utc = evt_dt.astimezone(self.utc_tz)
                        evt_dt_eat = evt_dt.astimezone(self.eat_tz)
                    except Exception as parse_err:
                        logger.warning(f"NewsBlackoutEngine: Failed to parse date string {date_str}: {parse_err}")
                        continue

                    events.append({
                        "title": item.get("title", "Economic Event"),
                        "currency": item.get("country", "").upper(),
                        "impact": item.get("impact", "").upper(),
                        "datetime_utc": evt_dt_utc,
                        "datetime_eat": evt_dt_eat
                    })
                
                self.cached_events = events
                self.last_fetch = now
                logger.info(f"NewsBlackoutEngine: Successfully fetched & cached {len(events)} economic events.")
                return self.cached_events
        except Exception as e:
            logger.error(f"NewsBlackoutEngine: Failed to fetch calendar events: {e}")
        
        # Fallback to empty if initial fetch failed
        return self.cached_events

    def is_news_blackout_active(self, symbol: str, current_time_utc: datetime) -> Tuple[bool, str]:
        """
        Checks if symbol is currently inside a high-impact economic news blackout window.
        Returns: (is_blocked, reason)
        """
        self.fetch_calendar_events()

        currencies = self._get_symbol_currencies(symbol)
        utc_now = current_time_utc.astimezone(self.utc_tz)

        for event in self.cached_events:
            # Enforce RED folder (HIGH impact) only
            if event["impact"] != "HIGH":
                continue

            if event["currency"] in currencies:
                event_time = event["datetime_utc"]
                window_start = event_time - timedelta(minutes=self.blackout_pre_mins)
                window_end = event_time + timedelta(minutes=self.blackout_post_mins)

                if window_start <= utc_now <= window_end:
                    event_time_eat = event["datetime_eat"]
                    reason = (
                        f"NEWS BLACKOUT [{symbol}]: High-Impact event '{event['title']}' ({event['currency']}) "
                        f"at {event_time_eat.strftime('%H:%M EAT')} (Blackout window: "
                        f"{window_start.astimezone(self.eat_tz).strftime('%H:%M')} - "
                        f"{window_end.astimezone(self.eat_tz).strftime('%H:%M EAT')})."
                    )
                    return True, reason

        return False, "OK"

    def _get_symbol_currencies(self, symbol: str) -> List[str]:
        """
        Helper to extract currency components from symbol name.
        """
        clean = symbol.upper().replace("M", "")
        # Precious metals or Crypto paired with USD
        if any(m in clean for m in ["XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER", "BTC", "ETH", "SOL", "LTC", "XRP"]):
            return ["USD"]
        # Standard FX majors/minors
        if len(clean) == 6:
            return [clean[:3], clean[3:6]]
        return [clean]
