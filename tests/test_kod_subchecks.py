"""Tests for KOD per-sub-check telemetry.

``confirmed_with_reason`` short-circuits on the first failing check, so it can
only ever name the earliest failure. That made it impossible to tell which
threshold was actually starving the funnel. ``subcheck_results`` evaluates all
five independently; running it live produced the pass rates that explained the
zero-KOD problem (volume 4.2%, displacement-ATR 11.3%, compound ~0.4%).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_engine.kod import KOD_SUBCHECKS, KODEngine
from trading_engine.types import Candle, Direction, LiquidityEvent


BASE = datetime(2026, 7, 31, tzinfo=timezone.utc)


def _flat(n: int, price: str = "100", volume: str = "100") -> list[Candle]:
    """Filler history so the 21-candle minimum is satisfied."""
    p = Decimal(price)
    return [
        Candle(
            time=BASE + timedelta(minutes=15 * i),
            open=p, high=p + Decimal("0.5"), low=p - Decimal("0.5"),
            close=p, volume=Decimal(volume), completed=True,
        )
        for i in range(n)
    ]


def _bullish_sweep_setup(
    displacement_body: str = "3.0",
    displacement_volume: str = "500",
    lower_wick: str = "3.0",
    bullish_displacement: bool = True,
):
    """A textbook bullish sweep (long lower wick) plus a displacement candle."""
    candles = _flat(25)
    idx = len(candles)

    # Sweep candle: pierces lows and closes back up -> long lower wick.
    wick = Decimal(lower_wick)
    sweep = Candle(
        time=BASE + timedelta(minutes=15 * idx),
        open=Decimal("100"), high=Decimal("100.5"),
        low=Decimal("100") - wick, close=Decimal("100.2"),
        volume=Decimal("100"), completed=True,
    )
    candles.append(sweep)

    body = Decimal(displacement_body)
    if bullish_displacement:
        d_open, d_close = Decimal("100.2"), Decimal("100.2") + body
    else:
        d_open, d_close = Decimal("100.2"), Decimal("100.2") - body
    disp = Candle(
        time=BASE + timedelta(minutes=15 * (idx + 1)),
        open=d_open,
        high=max(d_open, d_close) + Decimal("0.05"),
        low=min(d_open, d_close) - Decimal("0.05"),
        close=d_close,
        volume=Decimal(displacement_volume),
        completed=True,
    )
    candles.append(disp)

    event = LiquidityEvent(
        direction=Direction.BUY, swept_level=Decimal("100"),
        kind="equal_lows", candle_index=idx, failed=False, description="sweep",
    )
    return candles, event


# --------------------------------------------------------------------------- #
# Unevaluable cases return None (never a dict of Falses)
# --------------------------------------------------------------------------- #

def test_no_sweep_returns_none():
    assert KODEngine().subcheck_results(_flat(30), None) is None


def test_insufficient_history_returns_none():
    candles, event = _bullish_sweep_setup()
    assert KODEngine().subcheck_results(candles[:10], event) is None


def test_missing_displacement_candle_returns_none():
    """The 64.9% case: sweep on the last completed candle has no N+1 yet."""
    candles, event = _bullish_sweep_setup()
    truncated = candles[:-1]  # drop the displacement candle
    assert KODEngine().subcheck_results(truncated, event) is None


# --------------------------------------------------------------------------- #
# All five checks are reported independently
# --------------------------------------------------------------------------- #

def test_returns_all_five_subchecks():
    candles, event = _bullish_sweep_setup()
    results = KODEngine().subcheck_results(candles, event)
    assert results is not None
    assert set(results) == set(KOD_SUBCHECKS)
    assert all(isinstance(v, bool) for v in results.values())


def test_textbook_setup_passes_every_check():
    candles, event = _bullish_sweep_setup()
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("1.0"))
    assert all(results.values()), f"unexpected failures: {results}"


def test_wrong_direction_displacement_fails_only_direction_check():
    """Independence is the point: one bad check must not mask the others."""
    candles, event = _bullish_sweep_setup(bullish_displacement=False)
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("1.0"))
    assert results["displacement_direction"] is False
    # The other checks are still evaluated and still pass.
    assert results["sweep_rejection_wick"] is True
    assert results["displacement_body_ratio"] is True


def test_low_volume_fails_only_volume_check():
    candles, event = _bullish_sweep_setup(displacement_volume="1")
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("1.0"))
    assert results["displacement_volume"] is False
    assert results["displacement_direction"] is True


def test_small_body_fails_atr_check():
    candles, event = _bullish_sweep_setup(displacement_body="0.10")
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("5.0"))
    assert results["displacement_atr"] is False


def test_short_wick_fails_rejection_check():
    candles, event = _bullish_sweep_setup(lower_wick="0.01")
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("1.0"))
    assert results["sweep_rejection_wick"] is False


def test_zero_atr_does_not_fail_the_atr_check():
    """ATR is unavailable on short series; that must not count as a failure."""
    candles, event = _bullish_sweep_setup(displacement_body="0.10")
    results = KODEngine().subcheck_results(candles, event, atr_14=Decimal("0"))
    assert results["displacement_atr"] is True


# --------------------------------------------------------------------------- #
# Configurability
# --------------------------------------------------------------------------- #

def test_thresholds_can_be_overridden_per_instance():
    candles, event = _bullish_sweep_setup(displacement_volume="1")
    strict = KODEngine(volume_multiplier=Decimal("1.5"))
    lenient = KODEngine(volume_multiplier=Decimal("0"))
    assert strict.subcheck_results(candles, event)["displacement_volume"] is False
    assert lenient.subcheck_results(candles, event)["displacement_volume"] is True


def test_subchecks_agree_with_confirmed_on_a_passing_setup():
    """Telemetry must not contradict the execution path."""
    candles, event = _bullish_sweep_setup()
    engine = KODEngine()
    results = engine.subcheck_results(candles, event, atr_14=Decimal("1.0"))
    confirmed = engine.confirmed(candles, event, atr_14=Decimal("1.0"))
    assert all(results.values()) == bool(confirmed)
