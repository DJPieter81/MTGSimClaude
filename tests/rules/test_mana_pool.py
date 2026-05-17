"""Migration stub for ticket: mana_pool.

Source: sim.py:run_rules_tests() lines 2017-3501
Test count: 16
Headers covered:
- L2017: C1: mana enforcement
- L2018: C1: mana enforcement
- L2371: ManaManager: spend deducts and tracks
- L2373: ManaManager: spend deducts and tracks
- L2375: ManaManager: spend deducts and tracks
- L2528: actual card or the strategy's mana gates lie.
- L2529: actual card or the strategy's mana gates lie.
- L2532: actual card or the strategy's mana gates lie.
- L3090: when DD has 5+ mana.
- L3094: when DD has 5+ mana.
- L3345: ReanimatePath: reanimate_tag + enabler_tag + target + mana.
- L3347: ReanimatePath: reanimate_tag + enabler_tag + target + mana.
- L3349: ReanimatePath: reanimate_tag + enabler_tag + target + mana.
- L3351: ReanimatePath: reanimate_tag + enabler_tag + target + mana.
- L3353: ReanimatePath: reanimate_tag + enabler_tag + target + mana.
- L3501: Branch 6: same scenario, mana=0 → no path satisfiable → NoPlan.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket mana_pool")


@pytest.mark.fast
def test_placeholder_mana_pool():
    """Migration ticket: see docs/proposals/tickets/mana_pool.md."""
    assert False, "stub — migrate from sim.py:2017-3501"
