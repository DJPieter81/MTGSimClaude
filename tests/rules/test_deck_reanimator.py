"""Migration stub for ticket: deck_reanimator.

Source: sim.py:run_rules_tests() lines 3492-3495
Test count: 2
Headers covered:
- L3492: Branch 5: reanimator + all pieces present → Execute.
- L3495: Branch 5: reanimator + all pieces present → Execute.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_reanimator")


@pytest.mark.fast
def test_placeholder_deck_reanimator():
    """Migration ticket: see docs/proposals/tickets/deck_reanimator.md."""
    assert False, "stub — migrate from sim.py:3492-3495"
