"""Migration stub for ticket: force_of_will.

Source: sim.py:run_rules_tests() lines 2079-4746
Test count: 7
Headers covered:
- L2079: Audit: Force of Will pitch cost (must exile blue card)
- L2080: Audit: Force of Will pitch cost (must exile blue card)
- L2081: Audit: Force of Will pitch cost (must exile blue card)
- L2304: The sim's fow_worthwhile logic: CMC1 creature only if haste or dangerous tag
- L2305: The sim's fow_worthwhile logic: CMC1 creature only if haste or dangerous tag
- L4741: combo-protection emissions (storm holding FoW).
- L4746: combo-protection emissions (storm holding FoW).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket force_of_will")


@pytest.mark.fast
def test_placeholder_force_of_will():
    """Migration ticket: see docs/proposals/tickets/force_of_will.md."""
    assert False, "stub — migrate from sim.py:2079-4746"
