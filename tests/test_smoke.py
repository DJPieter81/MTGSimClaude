"""Smoke test — proves the pytest loop runs in <2s under xdist."""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_imports_root_module():
    import sim  # noqa: F401


@pytest.mark.fast
def test_imports_rules():
    from rules import Card, MTGRules, Permanent  # noqa: F401


@pytest.mark.fast
def test_fixture_makes_gamestate(fresh_gs):
    assert fresh_gs.p1 is not None
    assert fresh_gs.p2 is not None
    assert len(fresh_gs.p1.library) == 60
    assert len(fresh_gs.p2.library) == 60


@pytest.mark.fast
def test_factory_picks_deck(make_gs):
    gs = make_gs("storm", "burn")
    assert len(gs.p1.library) == 60
    assert len(gs.p2.library) == 60
