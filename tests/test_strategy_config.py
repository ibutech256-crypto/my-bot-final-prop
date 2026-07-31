"""Tests for the central strategy configuration and its reload semantics.

The reload path is the one that matters operationally: an operator changing a
threshold in ``.env`` and restarting (or hitting the config endpoint) must see
that threshold actually applied by the scoring engine and the execution gate.
Before the fix these tests cover, ``reload()`` rebound only the name inside
``strategy_config``, so ``scoring.TIER_2_THRESHOLD`` and
``account_manager.ADX_MAX`` silently kept their import-time values.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from trading_engine import account_manager, scoring, strategy_config


@pytest.fixture(autouse=True)
def restore_environment():
    """Snapshot/restore os.environ and reload config around every test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    strategy_config.reload()


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #

def test_defaults_match_previously_hardcoded_values():
    """Importing the module must not change behaviour on a bare environment."""
    cfg = strategy_config.reload()
    assert cfg.tiers.tier_1 == Decimal("55")
    assert cfg.tiers.tier_2 == Decimal("70")
    assert cfg.tiers.tier_3 == Decimal("85")
    # Tier 3 structurally requires KOD: the non-KOD ceiling sits below it.
    assert cfg.tiers.non_kod_cap < cfg.tiers.tier_3


def test_invalid_value_falls_back_to_default_instead_of_crashing():
    """A typo in .env must not take the engine down at startup."""
    os.environ["TIER_2_THRESHOLD"] = "not-a-number"
    cfg = strategy_config.reload()
    assert cfg.tiers.tier_2 == Decimal("70")


# --------------------------------------------------------------------------- #
# Reload propagation -- the regression this suite exists for
# --------------------------------------------------------------------------- #

def test_reload_preserves_object_identity():
    """Consumers bind the object via ``from ... import CONFIG``.

    Rebinding the module global would strand every one of them on the old
    instance, so reload must mutate in place.
    """
    before = strategy_config.CONFIG
    returned = strategy_config.reload()
    assert returned is before
    assert strategy_config.CONFIG is before


def test_reload_propagates_to_nested_group_held_by_reference():
    """Engines capture nested groups (``cfg = CONFIG.kod``); those must update."""
    group = strategy_config.CONFIG.kod
    os.environ["KOD_ATR_MULTIPLIER"] = "0.77"
    strategy_config.reload()
    assert group.atr_multiplier == Decimal("0.77")


def test_reload_propagates_to_scoring_module_constants():
    """`TIER_2_THRESHOLD` is a module-level scalar; the hook must re-derive it."""
    os.environ["TIER_2_THRESHOLD"] = "66"
    strategy_config.reload()
    assert scoring.TIER_2_THRESHOLD == Decimal("66")


def test_reload_propagates_to_execution_gate_constants():
    """The gate reads ADX_MAX at evaluation time from module scope."""
    os.environ["EXEC_GATE_ADX_MAX"] = "41"
    strategy_config.reload()
    assert account_manager.ADX_MAX == Decimal("41")


def test_reload_updates_risk_multiplier_dict_in_place():
    """Callers may hold the dict itself, so it is updated rather than replaced."""
    held = scoring.TIER_RISK_MULTIPLIERS
    os.environ["TIER_1_RISK_MULTIPLIER"] = "1.75"
    strategy_config.reload()
    assert held["TIER_1"] == Decimal("1.75")
    assert scoring.tier_risk_multiplier("TIER_1") == Decimal("1.75")


def test_tier_change_actually_changes_scoring_decision():
    """End-to-end proof: the retuned threshold reaches the tier decision.

    A score of 66 is below the default Tier 2 threshold of 70 and at or above a
    retuned threshold of 66, so the same score must classify differently after
    the reload. This is what "env-configurable" has to mean.
    """
    strategy_config.reload()
    assert Decimal("66") < scoring.TIER_2_THRESHOLD

    os.environ["TIER_2_THRESHOLD"] = "66"
    strategy_config.reload()
    assert Decimal("66") >= scoring.TIER_2_THRESHOLD


# --------------------------------------------------------------------------- #
# Hook registry
# --------------------------------------------------------------------------- #

def test_hook_registration_is_idempotent():
    calls = []

    def hook(cfg):
        calls.append(cfg)

    strategy_config.register_reload_hook(hook)
    strategy_config.register_reload_hook(hook)
    try:
        strategy_config.reload()
    finally:
        strategy_config._RELOAD_HOOKS.remove(hook)
    assert len(calls) == 1


def test_failing_hook_does_not_abort_reload():
    """One broken consumer must not stop the rest of the system reconfiguring."""
    def boom(cfg):
        raise RuntimeError("simulated consumer failure")

    strategy_config.register_reload_hook(boom)
    try:
        os.environ["TIER_2_THRESHOLD"] = "64"
        strategy_config.reload()
        assert strategy_config.CONFIG.tiers.tier_2 == Decimal("64")
        assert scoring.TIER_2_THRESHOLD == Decimal("64")
    finally:
        strategy_config._RELOAD_HOOKS.remove(boom)


def test_as_dict_is_json_safe():
    import json
    payload = strategy_config.CONFIG.as_dict()
    json.dumps(payload)  # must not raise
    assert "tiers.tier_2" in payload
    assert isinstance(payload["tiers.tier_2"], str)  # Decimal serialised
