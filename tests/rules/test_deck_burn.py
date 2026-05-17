"""Migration stub for ticket: deck_burn.

Source: sim.py:run_rules_tests() lines 2647-3956
Test count: 3
Headers covered:
- L2647: Burn-heavy metas.  Trimmed 1 Counterspell to fit the 4th copy.
- L2650: Burn-heavy metas.  Trimmed 1 Counterspell to fit the 4th copy.
- L3956: combat decision was logged, since burn can win pre-combat).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_burn")


@pytest.mark.fast
def test_placeholder_deck_burn():
    """Migration ticket: see docs/proposals/tickets/deck_burn.md."""
    assert False, "stub — migrate from sim.py:2647-3956"
