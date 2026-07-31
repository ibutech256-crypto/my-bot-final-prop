"""Tests for sweep candidate selection.

Background
----------
KOD is a two-candle pattern: sweep candle ``N`` plus displacement candle
``N+1``. ``detect_sweep`` returned only the *newest* sweep, and because the
newest completed candle usually wins the sweep race it frequently had no
``N+1`` yet. Measured live on 2026-07-31 across 366 symbol/timeframe
evaluations, 133 of 205 detected sweeps (64.9%) failed KOD with "awaiting
displacement candle after sweep" — the single largest KOD blocker.

``select_sweep_for_displacement`` prefers a slightly older sweep that already
has its displacement candle. These tests pin the selection rules, and in
particular the fallback that keeps the previous behaviour intact.
"""

from __future__ import annotations

from decimal import Decimal

from trading_engine.liquidity import select_sweep_for_displacement
from trading_engine.types import Direction, LiquidityEvent


def _event(index: int, direction: Direction = Direction.BUY) -> LiquidityEvent:
    return LiquidityEvent(
        direction=direction,
        swept_level=Decimal("1.1000"),
        kind="equal_lows",
        candle_index=index,
        failed=False,
        description=f"sweep at {index}",
    )


def test_no_candidates_returns_none():
    event, note = select_sweep_for_displacement((), completed_count=50)
    assert event is None
    assert "no sweep" in note.lower()


def test_newest_sweep_used_when_it_already_has_displacement():
    """Unchanged behaviour whenever the newest sweep is confirmable."""
    events = (_event(47), _event(40))
    event, note = select_sweep_for_displacement(events, completed_count=50)
    assert event.candle_index == 47
    assert "displacement candle available" in note


def test_older_sweep_preferred_when_newest_lacks_displacement():
    """The regression: a valid older sweep must not be masked by an unconfirmable newer one."""
    newest_index = 49  # last completed candle -> no N+1 exists
    events = (_event(newest_index), _event(44))
    event, note = select_sweep_for_displacement(events, completed_count=50)
    assert event.candle_index == 44
    assert "no displacement candle yet" in note
    assert "44" in note


def test_falls_back_to_newest_when_no_candidate_has_displacement():
    """Never invent a sweep: if none is confirmable, behave exactly as before."""
    events = (_event(49),)
    event, note = select_sweep_for_displacement(events, completed_count=50)
    assert event.candle_index == 49
    assert "has not formed yet" in note


def test_scan_disabled_always_returns_newest():
    """KOD_SCAN_OLDER_SWEEPS=0 restores the exact previous selection."""
    events = (_event(49), _event(44))
    event, note = select_sweep_for_displacement(events, completed_count=50, prefer_displaced=False)
    assert event.candle_index == 49
    assert "disabled" in note


def test_selects_the_newest_displaced_candidate_not_merely_any_older_one():
    """Among several confirmable sweeps the most recent one wins."""
    events = (_event(49), _event(46), _event(30))
    event, _ = select_sweep_for_displacement(events, completed_count=50)
    assert event.candle_index == 46


def test_selection_preserves_event_identity():
    """The returned object must be the candidate itself, not a copy."""
    older = _event(44)
    events = (_event(49), older)
    event, _ = select_sweep_for_displacement(events, completed_count=50)
    assert event is older
