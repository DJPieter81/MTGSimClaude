"""Migration stub for ticket: free_counters.

Source: sim.py:run_rules_tests() lines 2098-2099
Test count: 2
Headers covered:
- L2098: Audit: Daze tapped-out logic (opp_mana <= spell_cmc)
- L2099: Audit: Daze tapped-out logic (opp_mana <= spell_cmc)
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket free_counters")


@pytest.mark.fast
def test_placeholder_free_counters():
    """Migration ticket: see docs/proposals/tickets/free_counters.md."""
    assert False, "stub — migrate from sim.py:2098-2099"
