"""Migration stub for ticket: deck_storm_part1.

Source: sim.py:run_rules_tests() lines 2243-2952
Test count: 15
Headers covered:
- L2243: Give opp GY: land + instant + creature = 3 types
- L2244: Give opp GY: land + instant + creature = 3 types
- L2245: Give opp GY: land + instant + creature = 3 types
- L2555: storm out under pressure.  Adding 4 Petal swings storm vs dnt 34→50%.
- L2556: storm out under pressure.  Adding 4 Petal swings storm vs dnt 34→50%.
- L2558: storm out under pressure.  Adding 4 Petal swings storm vs dnt 34→50%.
- L2580: Pre-fix the sim ran 4 BS + 2 Ponder, halving cantrip dig redundancy.
- L2582: Pre-fix the sim ran 4 BS + 2 Ponder, halving cantrip dig redundancy.
- L2590: is a free cantrip + storm-count enabler.  Both are 4-of in real lists.
- L2591: is a free cantrip + storm-count enabler.  Both are 4-of in real lists.
- L2593: is a free cantrip + storm-count enabler.  Both are 4-of in real lists.
- L2668: wins around 1-2/10 due to the cantrip + step-through bugs.
- L2672: wins around 1-2/10 due to the cantrip + step-through bugs.
- L2949: Frozen invariant: mutating a constructed instance raises.
- L2952: Frozen invariant: mutating a constructed instance raises.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_storm_part1")


@pytest.mark.fast
def test_placeholder_deck_storm_part1():
    """Migration ticket: see docs/proposals/tickets/deck_storm_part1.md."""
    assert False, "stub — migrate from sim.py:2243-2952"
