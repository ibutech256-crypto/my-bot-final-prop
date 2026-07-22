from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("trading")


@dataclass
class EATPhaseStatus:
    phase_name: str
    is_allowed: bool
    reason: str
    sizing_multiplier: Decimal
    is_pit_open: bool
    expiration_clamp_utc: Optional[int]


class EATPhaseEngine:
    """
    East Africa Time (EAT / UTC+3) 24-Hour Market Phase & Multi-Asset Session Engine.
    Enforces Updated Trading Timeline:
    - System Shutdown (Overnight Block): 23:00 - 05:00 EAT (20:00 - 02:00 UTC) -> Hard Block across all assets.
    - Pre-London Morning Window (Gold & FX): 05:00 - 10:00 EAT (02:00 - 07:00 UTC) -> Morning Guard Rules.
    - Major FX Pairs: 10:00 - 20:00 EAT (07:00 - 17:00 UTC).
    - Precious Metals & Crypto: 10:00 - 22:00 EAT (07:00 - 19:00 UTC).
    - US Single Stock CFDs: 16:30 - 23:00 EAT (13:30 - 20:00 UTC).
    """
    @staticmethod
    def is_us_dst(dt_utc: datetime) -> bool:
        year = dt_utc.year
        march_first = datetime(year, 3, 1, tzinfo=timezone.utc)
        dst_start = march_first + timedelta(days=(6 - march_first.weekday()) % 7 + 7, hours=7)
        nov_first = datetime(year, 11, 1, tzinfo=timezone.utc)
        dst_end = nov_first + timedelta(days=(6 - nov_first.weekday()) % 7, hours=6)
        return dst_start <= dt_utc < dst_end

    @staticmethod
    def get_eat_time(dt_utc: Optional[datetime] = None) -> datetime:
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        return dt_utc + timedelta(hours=3)

    @classmethod
    def evaluate_asset_phase(cls, symbol: str, score: Decimal, dt_utc: Optional[datetime] = None) -> EATPhaseStatus:
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        
        eat_dt = cls.get_eat_time(dt_utc)
        eat_hour = eat_dt.hour
        eat_minute = eat_dt.minute
        eat_time_float = eat_hour + eat_minute / 60.0
        weekday = eat_dt.weekday()  # 0=Monday ... 4=Friday, 5=Saturday, 6=Sunday

        clean_sym = symbol.upper().replace("M", "")
        us_dst = cls.is_us_dst(dt_utc)
        us_open_eat = 16.5 if us_dst else 17.5
        us_close_eat = 23.0 if us_dst else 24.0

        # --- RULE 0: System Shutdown (Overnight Block) -> 23:00 - 05:00 EAT ---
        # Hard Rule: Block all new trade executions across all asset classes (23:00 - 05:00 EAT)
        if eat_time_float >= 23.0 or eat_time_float < 5.0:
            return EATPhaseStatus(
                phase_name="System Shutdown (Overnight Block: 23:00 - 05:00 EAT)",
                is_allowed=False,
                reason=f"EAT PHASE GATE: Hard block across all asset classes during overnight shutdown (`{eat_dt.strftime('%H:%M')} EAT`)",
                sizing_multiplier=Decimal("0.0"),
                is_pit_open=False,
                expiration_clamp_utc=None
            )

        # --- RULE 1: Daily Maintenance Halt (00:00 - 01:00 EAT) ---
        if 0.0 <= eat_time_float < 1.0:
            return EATPhaseStatus(
                phase_name="Daily Maintenance Halt (00:00 - 01:00 EAT)",
                is_allowed=False,
                reason="EAT PHASE GATE: Hard block during daily broker maintenance halt",
                sizing_multiplier=Decimal("0.0"),
                is_pit_open=False,
                expiration_clamp_utc=None
            )

        # --- RULE 2: Single Stock CFDs & U.S. Actual Stocks ---
        is_stock = any(s in clean_sym for s in ["TSLA", "VRTX", "NTES", "SBUX", "TMO", "BABA", "META", "AMZN", "AAPL", "MSFT", "GOOG", "NVDA", "NFLX", "CSCO", "ADP", "ADBE", "BIDU", "PDD", "PYPL", "BB"]) or (len(clean_sym) <= 4 and not any(k in clean_sym for k in ["GOLD", "OIL", "US30", "DXY", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "BTC", "ETH"]))
        if is_stock:
            if weekday >= 5:
                return EATPhaseStatus(
                    phase_name="Weekend Stock Halt",
                    is_allowed=False,
                    reason="EAT PHASE GATE: U.S. Stocks closed over the weekend",
                    sizing_multiplier=Decimal("0.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )
            if us_open_eat <= eat_time_float < us_close_eat:
                exp_clamp = int((dt_utc.replace(hour=20, minute=0, second=0, microsecond=0)).timestamp())
                return EATPhaseStatus(
                    phase_name="Active US Stock Cash Session (16:30 - 23:00 EAT)",
                    is_allowed=True,
                    reason="EAT PHASE GATE: Inside active US equity cash market window",
                    sizing_multiplier=Decimal("1.0"),
                    is_pit_open=(us_open_eat <= eat_time_float < us_open_eat + 0.5),
                    expiration_clamp_utc=exp_clamp
                )
            else:
                if score >= Decimal("95.00"):
                    return EATPhaseStatus(
                        phase_name="The 95+ Score Exception (Stock CFD Outside Core Hours)",
                        is_allowed=True,
                        reason=f"EAT PHASE GATE: Elite setup ({score}/100 >= 95) clears out-of-hours Stock CFD exception",
                        sizing_multiplier=Decimal("0.5"),
                        is_pit_open=False,
                        expiration_clamp_utc=int((dt_utc + timedelta(minutes=15)).timestamp())
                    )
                return EATPhaseStatus(
                    phase_name="Stock CFD Hard Shutdown (Outside 16:30 - 23:00 EAT)",
                    is_allowed=False,
                    reason=f"EAT PHASE GATE: Stock CFD outside US cash market window (`{eat_dt.strftime('%H:%M')} EAT`). Requires Score >= 95",
                    sizing_multiplier=Decimal("0.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )

        # --- RULE 3: Pre-London Morning Window (05:00 - 10:00 EAT) ---
        if 5.0 <= eat_time_float < 10.0:
            is_morning_asset = any(a in clean_sym for a in ["XAU", "GOLD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"])
            if is_morning_asset or score >= Decimal("92.00"):
                return EATPhaseStatus(
                    phase_name="Pre-London Morning Window (05:00 - 10:00 EAT)",
                    is_allowed=True,
                    reason="EAT PHASE GATE: Pre-London Morning Window active (subject to Morning Guard Rules)",
                    sizing_multiplier=Decimal("1.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )
            return EATPhaseStatus(
                phase_name="Pre-London Morning Window (05:00 - 10:00 EAT)",
                is_allowed=False,
                reason=f"EAT PHASE GATE: Asset {clean_sym} restricted during Pre-London Morning Window (`05:00-10:00 EAT`)",
                sizing_multiplier=Decimal("0.0"),
                is_pit_open=False,
                expiration_clamp_utc=None
            )

        # --- RULE 4: Major FX Pairs (10:00 - 20:00 EAT) ---
        is_forex = any(f in clean_sym for f in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]) and not any(m in clean_sym for m in ["GOLD", "OIL", "BTC", "ETH", "US30", "XAU"])
        if is_forex:
            if 10.0 <= eat_time_float < 20.0:
                return EATPhaseStatus(
                    phase_name="Major FX Active Window (10:00 - 20:00 EAT)",
                    is_allowed=True,
                    reason="EAT PHASE GATE: Inside active Major FX liquidity window",
                    sizing_multiplier=Decimal("1.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )
            elif 20.0 <= eat_time_float < 23.0:
                if score >= Decimal("88.00") or any(a in clean_sym for a in ["USDJPY", "AUDUSD", "USDCAD"]):
                    return EATPhaseStatus(
                        phase_name="Late FX Evening Window (20:00 - 23:00 EAT)",
                        is_allowed=True,
                        reason="EAT PHASE GATE: Qualified Late FX Evening clearance",
                        sizing_multiplier=Decimal("0.5"),
                        is_pit_open=False,
                        expiration_clamp_utc=None
                    )
                return EATPhaseStatus(
                    phase_name="FX Evening Restriction (20:00 - 23:00 EAT)",
                    is_allowed=False,
                    reason=f"EAT PHASE GATE: FX outside core window (`{eat_dt.strftime('%H:%M')} EAT`). Requires Score >= 88",
                    sizing_multiplier=Decimal("0.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )

        # --- RULE 5: Precious Metals & Crypto (10:00 - 22:00 EAT) ---
        is_metal_or_crypto = any(c in clean_sym for c in ["XAU", "GOLD", "XAG", "SILVER", "XPT", "BTC", "ETH", "SOL", "LTC", "XRP"])
        if is_metal_or_crypto:
            if 10.0 <= eat_time_float < 22.0:
                return EATPhaseStatus(
                    phase_name="Metals & Crypto Active Window (10:00 - 22:00 EAT)",
                    is_allowed=True,
                    reason="EAT PHASE GATE: Inside active Metals & Crypto liquidity window",
                    sizing_multiplier=Decimal("1.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )
            elif 22.0 <= eat_time_float < 23.0:
                if score >= Decimal("90.00"):
                    return EATPhaseStatus(
                        phase_name="Late Metals/Crypto Window (22:00 - 23:00 EAT)",
                        is_allowed=True,
                        reason="EAT PHASE GATE: Elite setup clears late evening window",
                        sizing_multiplier=Decimal("0.5"),
                        is_pit_open=False,
                        expiration_clamp_utc=None
                    )
                return EATPhaseStatus(
                    phase_name="Metals/Crypto Evening Restriction (22:00 - 23:00 EAT)",
                    is_allowed=False,
                    reason=f"EAT PHASE GATE: Metals/Crypto outside core `10:00-22:00 EAT` window (`{eat_dt.strftime('%H:%M')} EAT`)",
                    sizing_multiplier=Decimal("0.0"),
                    is_pit_open=False,
                    expiration_clamp_utc=None
                )

        return EATPhaseStatus(
            phase_name="Standard Liquidity Phase",
            is_allowed=True,
            reason="EAT PHASE GATE: Standard multi-asset liquidity window verified",
            sizing_multiplier=Decimal("1.0"),
            is_pit_open=False,
            expiration_clamp_utc=None
        )
