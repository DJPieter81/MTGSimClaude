"""Migration stub for ticket: misc_rules_part2.

Source: sim.py:run_rules_tests() lines 2391-2682
Test count: 15
Headers covered:
- L2391: Add some creatures to p1
- L2433: difference reflects strategy, not RNG noise.
- L2443: 100%/0% cases; natural variance no longer trips the test.
- L2504: remove tags not present in the maindeck or the SB pool runs short.
- L2508: remove tags not present in the maindeck or the SB pool runs short.
- L2514: sample doesn't crash and returns both match_wr and game_wr.
- L2515: sample doesn't crash and returns both match_wr and game_wr.
- L2517: sample doesn't crash and returns both match_wr and game_wr.
- L2543: Every tier-1 list runs 4 LED — anything less is not a real DD list.
- L2546: Every tier-1 list runs 4 LED — anything less is not a real DD list.
- L2632: T1 free (pitching Island).  Lock the printed cost in via spot tests.
- L2635: T1 free (pitching Island).  Lock the printed cost in via spot tests.
- L2636: T1 free (pitching Island).  Lock the printed cost in via spot tests.
- L2638: T1 free (pitching Island).  Lock the printed cost in via spot tests.
- L2682: (≥3) to make a hand-presence on the kill turn likely.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part2")


@pytest.mark.fast
def test_placeholder_misc_rules_part2():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part2.md."""
    assert False, "stub — migrate from sim.py:2391-2682"
