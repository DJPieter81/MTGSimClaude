"""Migration stub for ticket: misc_rules_part1.

Source: sim.py:run_rules_tests() lines 1957-2390
Test count: 15
Headers covered:
- L1957: Ensnaring Bridge
- L1958: Ensnaring Bridge
- L1959: Ensnaring Bridge
- L2048: S5: FoN free only on opponent's turn
- L2049: S5: FoN free only on opponent's turn
- L2110: Audit: Card attributes (Oracle text correctness)
- L2111: Audit: Card attributes (Oracle text correctness)
- L2113: Audit: Card attributes (Oracle text correctness)
- L2114: Audit: Card attributes (Oracle text correctness)
- L2115: Audit: Card attributes (Oracle text correctness)
- L2116: Audit: Card attributes (Oracle text correctness)
- L2120: Prior test asserted CMC=2, baking in a misread of the rule.
- L2188: Simulate turn boundary cleanup
- L2361: CMC 5 should NOT trigger
- L2390: Add some creatures to p1
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part1")


@pytest.mark.fast
def test_placeholder_misc_rules_part1():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part1.md."""
    assert False, "stub — migrate from sim.py:1957-2390"
