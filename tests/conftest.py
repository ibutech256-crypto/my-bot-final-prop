"""Pytest bootstrap for the trading-engine unit tests.

``trading_engine.account_manager`` imports ``backend.apps.trading.models``, so
Django must be configured before any engine module is imported. The production
settings module pulls in daphne, channels, DRF, drf-spectacular and a Redis
channel layer, none of which these tests need; configuring a minimal in-memory
settings object keeps the suite runnable anywhere (including CI and the VPS)
without standing up Redis.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django
from django.conf import settings

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bootstrap_django() -> None:
    if settings.configured:
        return
    settings.configure(
        DEBUG=False,
        USE_TZ=True,
        TIME_ZONE="UTC",
        SECRET_KEY="test-only-not-a-real-secret",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "backend.apps.common",
            "backend.apps.accounts",
            "backend.apps.trading",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        AUTH_USER_MODEL="accounts.User",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()


# Env hygiene: a stray value inherited from the developer's shell (or from the
# VPS .env when the suite is run there) would silently change the defaults the
# configuration tests assert against.
for _key in list(os.environ):
    if _key.startswith((
        "KOD_", "LIQ_", "CRT_", "TIER_", "HTF_", "EXEC_GATE_", "MT5_MAX_SPREAD",
        "STOP_ATR_", "TAKE_PROFIT_", "ATR_PERIOD", "MIN_VOLATILITY_",
        "BREAKEVEN_", "SESSION_", "KILLZONE_", "SHADOW_MODE", "EXEC_COOLDOWN_",
        "SIGNAL_REFRESH_", "PERSIST_NO_SWEEP_", "MIN_PERSIST_SCORE",
        "FUNNEL_", "TRACE_ALL_", "SCAN_TIMEFRAMES", "NON_KOD_SCORE_CAP",
    )):
        del os.environ[_key]

_bootstrap_django()
