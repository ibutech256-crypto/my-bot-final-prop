"""Tests for the higher-timeframe bias engine.

The defect this module replaced was ``htf_ok = True`` as a default in
``orchestrator.evaluate_signal``: because ``run_mt5_engine`` never passed HTF
candles, the override never ran and *every* signal collected the 15-point HTF
component for free. Live evidence: 460 of 460 stored signals carried the
'HTF Alignment' confluence. The single most important property below is
therefore that missing or partial data can never yield ``aligned=True``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trading_engine.htf_bias import HTFBiasEngine, HTFStatus
from trading_engine.types import Candle, Direction


def _series(start: float, step: float, count: int = 60) -> list[Candle]:
    """A clean monotonic ramp: ``step`` > 0 trends up, < 0 trends down."""
    base = datetime(2026, 7, 31, tzinfo=timezone.utc)
    candles = []
    for i in range(count):
        price = Decimal(str(start + step * i))
        candles.append(Candle(
            time=base + timedelta(hours=i),
            open=price,
            high=price + Decimal("0.5"),
            low=price - Decimal("0.5"),
            close=price,
            volume=Decimal("100"),
            completed=True,
        ))
    return candles


def _loader(mapping):
    """Build a rate loader from ``{timeframe: candles}``; missing -> empty."""
    def load(symbol, timeframe, bars):
        return mapping.get(timeframe, [])
    return load


def _all_timeframes(candles):
    from trading_engine.strategy_config import CONFIG
    return {tf: candles for tf in CONFIG.htf.timeframes}


# --------------------------------------------------------------------------- #
# The regression: data problems must never read as agreement
# --------------------------------------------------------------------------- #

def test_missing_data_is_not_aligned():
    engine = HTFBiasEngine(_loader({}))
    result = engine.evaluate("EURUSDm", Direction.BUY)
    assert result.aligned is False
    assert result.status is HTFStatus.DATA_UNAVAILABLE


def test_loader_exception_is_not_aligned():
    def exploding(symbol, timeframe, bars):
        raise ConnectionError("MT5 pipe closed")

    engine = HTFBiasEngine(exploding)
    result = engine.evaluate("EURUSDm", Direction.BUY)
    assert result.aligned is False
    assert result.status is HTFStatus.DATA_UNAVAILABLE


def test_short_history_is_not_aligned():
    """Fewer bars than the slow MA cannot produce a bias."""
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(1.0, 0.01, count=5))))
    result = engine.evaluate("EURUSDm", Direction.BUY)
    assert result.aligned is False
    assert result.status is HTFStatus.DATA_UNAVAILABLE


def test_no_direction_is_not_evaluated():
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(1.0, 0.01))))
    assert engine.evaluate("EURUSDm", None).status is HTFStatus.NOT_EVALUATED
    assert engine.evaluate("EURUSDm", Direction.NEUTRAL).aligned is False


# --------------------------------------------------------------------------- #
# Genuine agreement / disagreement
# --------------------------------------------------------------------------- #

def test_uptrend_aligns_with_buy():
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(1.0, 0.01))))
    result = engine.evaluate("EURUSDm", Direction.BUY)
    assert result.aligned is True
    assert result.status is HTFStatus.ALIGNED


def test_uptrend_conflicts_with_sell():
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(1.0, 0.01))))
    result = engine.evaluate("EURUSDm", Direction.SELL)
    assert result.aligned is False
    assert result.status is HTFStatus.CONFLICT


def test_downtrend_aligns_with_sell():
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(2.0, -0.01))))
    result = engine.evaluate("EURUSDm", Direction.SELL)
    assert result.aligned is True


def test_partial_timeframe_availability_is_not_aligned_when_confirmation_required():
    """One good timeframe plus one missing must not pass while HTF_REQUIRE_CONFIRMATION is on."""
    from trading_engine.strategy_config import CONFIG
    timeframes = list(CONFIG.htf.timeframes)
    if len(timeframes) < 2 or not CONFIG.htf.require_confirmation:
        pytest.skip("requires >=2 configured HTF timeframes with confirmation on")
    mapping = {timeframes[0]: _series(1.0, 0.01)}
    engine = HTFBiasEngine(_loader(mapping))
    result = engine.evaluate("EURUSDm", Direction.BUY)
    assert result.aligned is False
    assert result.status is HTFStatus.DATA_UNAVAILABLE


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #

def test_results_are_cached_per_symbol():
    calls = []

    def counting(symbol, timeframe, bars):
        calls.append((symbol, timeframe))
        return _series(1.0, 0.01)

    engine = HTFBiasEngine(counting)
    engine.evaluate("EURUSDm", Direction.BUY)
    first = len(calls)
    engine.evaluate("EURUSDm", Direction.BUY)
    assert len(calls) == first, "second evaluation should be served from cache"
    assert engine.cache_hits >= 1


def test_invalidate_forces_refetch():
    calls = []

    def counting(symbol, timeframe, bars):
        calls.append(timeframe)
        return _series(1.0, 0.01)

    engine = HTFBiasEngine(counting)
    engine.evaluate("EURUSDm", Direction.BUY)
    first = len(calls)
    engine.invalidate("EURUSDm")
    engine.evaluate("EURUSDm", Direction.BUY)
    assert len(calls) > first


def test_result_is_json_safe():
    import json
    engine = HTFBiasEngine(_loader(_all_timeframes(_series(1.0, 0.01))))
    json.dumps(engine.evaluate("EURUSDm", Direction.BUY).as_dict())
