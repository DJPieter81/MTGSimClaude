"""Migration stub for ticket: bowmasters.

Source: sim.py:run_rules_tests() lines 1976-2278
Test count: 5
Headers covered:
- L1976: Bowmasters draw triggers
- L1977: Bowmasters draw triggers
- L2137: Put Bowmasters in play so the computed property returns True
- L2154: Put Bowmasters in play so the trigger can actually fire
- L2278: Two Bowmasters -> legend rule does NOT fire (not legendary)
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket bowmasters")


@pytest.mark.fast
def test_placeholder_bowmasters():
    """Migration ticket: see docs/proposals/tickets/bowmasters.md."""
    assert False, "stub — migrate from sim.py:1976-2278"
