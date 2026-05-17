"""Migration stub for ticket: deck_depths.

Source: sim.py:run_rules_tests() lines 3700-3704
Test count: 2
Headers covered:
- L3700: Phase 5: depths deck declares combo metadata + path coverage
- L3704: Phase 5: depths deck declares combo metadata + path coverage
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_depths")


@pytest.mark.fast
def test_placeholder_deck_depths():
    """Migration ticket: see docs/proposals/tickets/deck_depths.md."""
    assert False, "stub — migrate from sim.py:3700-3704"
