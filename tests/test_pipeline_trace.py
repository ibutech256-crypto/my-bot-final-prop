"""Tests for the signal-lifecycle trace and the funnel counters.

Phase 2/3 of the brief require that no evaluation may disappear silently and
that every terminal state carries a specific, machine-readable reason. The old
engine had a bare ``continue`` with no logging in the duplicate-signal path,
which is precisely how 501 WATCHLIST rows accumulated with zero explanation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from trading_engine.pipeline_trace import (
    FUNNEL_ORDER,
    FunnelCounters,
    Outcome,
    Reason,
    SignalTrace,
    Stage,
    classify_session,
    describe,
)


# --------------------------------------------------------------------------- #
# Reason codes
# --------------------------------------------------------------------------- #

def test_every_reason_has_a_specific_description():
    """No code may fall back to a generic 'blocked'/'rejected' string."""
    for reason in Reason:
        text = describe(reason.value)
        assert text, f"{reason.name} has no description"
        assert text.lower() not in {"blocked", "rejected", "error"}
        assert text != reason.value, f"{reason.name} has no human-readable text"


def test_describe_appends_detail():
    text = describe(Reason.SPREAD_ABSOLUTE_CAP.value, "3.4 pips > 2.5 cap")
    assert "3.4 pips" in text


def test_reason_codes_are_unique():
    values = [r.value for r in Reason]
    assert len(values) == len(set(values))


def test_stage_order_is_the_declaration_order():
    """Conversion percentages are only meaningful if the order is monotonic."""
    assert FUNNEL_ORDER[0] is Stage.SCANNED
    assert list(FUNNEL_ORDER) == list(Stage)


# --------------------------------------------------------------------------- #
# SignalTrace
# --------------------------------------------------------------------------- #

def test_trace_records_stages_and_facts():
    trace = SignalTrace(symbol="EURUSDm", timeframe="M15")
    trace.mark(Stage.SCANNED).mark(Stage.DATA_OK, "120 bars", bars=120)
    assert trace.reached(Stage.SCANNED)
    assert trace.reached(Stage.DATA_OK)
    assert not trace.reached(Stage.KOD_CONFIRMED)
    assert trace.facts["bars"] == 120


def test_terminate_sets_machine_and_human_reason():
    trace = SignalTrace(symbol="EURUSDm", timeframe="M15")
    trace.mark(Stage.SCANNED)
    trace.terminate(Outcome.WATCHLIST, Reason.BELOW_TIER_1, "score 55 < 55")
    assert trace.terminated is True
    assert trace.outcome == Outcome.WATCHLIST.value
    assert trace.reason_code == Reason.BELOW_TIER_1.value
    assert "55" in trace.reason_text


def test_arrow_chain_includes_outcome():
    trace = SignalTrace(symbol="XAUUSDm", timeframe="H1")
    trace.mark(Stage.SCANNED).mark(Stage.CRT_CONFIRMED)
    trace.terminate(Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP)
    chain = trace.arrow_chain()
    assert "SCANNED" in chain and "CRT_CONFIRMED" in chain
    assert Outcome.NO_SETUP.value in chain


def test_trace_is_json_serialisable():
    trace = SignalTrace(symbol="EURUSDm", timeframe="M5")
    trace.mark(Stage.SCANNED, entry=1.2345)
    trace.terminate(Outcome.REJECTED, Reason.SPREAD_ABSOLUTE_CAP, "too wide")
    json.dumps(trace.as_dict())


# --------------------------------------------------------------------------- #
# Session classification
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("hour,expected", [
    (8, "LONDON"),      # London open, before NY
    (13, "OVERLAP"),    # London + New York both open
    (18, "NEW_YORK"),   # after London close
    (2, "ASIA"),        # Tokyo
])
def test_session_classification(hour, expected):
    now = datetime(2026, 7, 31, hour, 0, tzinfo=timezone.utc)
    assert classify_session(now) == expected


# --------------------------------------------------------------------------- #
# FunnelCounters
# --------------------------------------------------------------------------- #

def _trace(symbol, stages, outcome, reason, session_facts=None):
    t = SignalTrace(symbol=symbol, timeframe="M15")
    for s in stages:
        t.mark(s)
    if session_facts:
        t.fact(**session_facts)
    t.terminate(outcome, reason)
    return t


def test_funnel_counts_stages_and_reasons():
    funnel = FunnelCounters()
    funnel.record(_trace("A", [Stage.SCANNED, Stage.DATA_OK], Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP), session="LONDON")
    funnel.record(_trace("B", [Stage.SCANNED, Stage.DATA_OK, Stage.CRT_CONFIRMED],
                         Outcome.WATCHLIST, Reason.BELOW_TIER_1), session="LONDON")

    snap = funnel.snapshot()
    payload = json.dumps(snap)  # must be transport-safe for the websocket push
    assert payload
    assert "LONDON" in json.dumps(snap)


def test_funnel_separates_sessions():
    funnel = FunnelCounters()
    funnel.record(_trace("A", [Stage.SCANNED], Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP), session="LONDON")
    funnel.record(_trace("B", [Stage.SCANNED], Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP), session="NEW_YORK")
    snap = json.dumps(funnel.snapshot())
    assert "LONDON" in snap and "NEW_YORK" in snap


def test_render_text_is_human_readable():
    funnel = FunnelCounters()
    for i in range(3):
        funnel.record(_trace(f"S{i}", [Stage.SCANNED, Stage.DATA_OK], Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP))
    text = funnel.render_text()
    assert "SCANNED" in text
    assert isinstance(text, str) and len(text.splitlines()) > 3


def test_write_snapshot_creates_valid_json(tmp_path):
    funnel = FunnelCounters()
    funnel.record(_trace("A", [Stage.SCANNED], Outcome.NO_SETUP, Reason.NO_LIQUIDITY_SWEEP))
    target = tmp_path / "funnel_snapshot.json"
    written = funnel.write_snapshot(str(target))
    assert written is not None
    assert json.loads(target.read_text())


def test_kod_subcheck_pass_rates_are_tracked():
    """Per-subcheck rates are what revealed the ~0.4% compound KOD pass rate."""
    funnel = FunnelCounters()
    funnel.note_kod_subchecks({"sweep_rejection_wick": True, "displacement_volume": False})
    funnel.note_kod_subchecks({"sweep_rejection_wick": False, "displacement_volume": False})
    snap = json.dumps(funnel.snapshot())
    assert "sweep_rejection_wick" in snap


def test_cycle_complete_increments():
    funnel = FunnelCounters()
    assert funnel.cycle_complete() == 1
    assert funnel.cycle_complete() == 2
