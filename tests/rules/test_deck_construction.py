"""Migration stub for ticket: deck_construction.

Source: sim.py:run_rules_tests() lines 2157-2166
Test count: 3
Headers covered:
- L2157: Audit: BUG deck is exactly 60 cards
- L2164: Audit: All registered decks are exactly 60 cards
- L2166: Audit: All registered decks are exactly 60 cards
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_construction")


@pytest.mark.fast
def test_placeholder_deck_construction():
    """Migration ticket: see docs/proposals/tickets/deck_construction.md."""
    assert False, "stub — migrate from sim.py:2157-2166"
