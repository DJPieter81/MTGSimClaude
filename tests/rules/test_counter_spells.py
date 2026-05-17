"""Migration stub for ticket: counter_spells.

Source: sim.py:run_rules_tests() lines 4555-4699
Test count: 2
Headers covered:
- L4555: prefix, so all axis counters stay at 0.
- L4699: (block + hold + counter-swing) get the top combat grade.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket counter_spells")


@pytest.mark.fast
def test_placeholder_counter_spells():
    """Migration ticket: see docs/proposals/tickets/counter_spells.md."""
    assert False, "stub — migrate from sim.py:4555-4699"
