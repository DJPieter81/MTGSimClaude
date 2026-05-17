"""Migration stub for ticket: burn_triggers.

Source: sim.py:run_rules_tests() lines 2357-2357
Test count: 1
Headers covered:
- L2357: Eidolon: 2 damage per CMC ≤ 3 spell
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket burn_triggers")


@pytest.mark.fast
def test_placeholder_burn_triggers():
    """Migration ticket: see docs/proposals/tickets/burn_triggers.md."""
    assert False, "stub — migrate from sim.py:2357-2357"
