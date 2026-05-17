"""Migration stub for ticket: tax_effects.

Source: sim.py:run_rules_tests() lines 1987-2483
Test count: 19
Headers covered:
- L1987: Chalice CMC check (printed CMC)
- L1988: Chalice CMC check (printed CMC)
- L1989: Chalice CMC check (printed CMC)
- L1990: Chalice CMC check (printed CMC)
- L2317: Trinisphere: all spells cost at least {3}
- L2320: Trinisphere: all spells cost at least {3}
- L2323: Trinisphere: all spells cost at least {3}
- L2336: Must place an actual Thalia creature on board (computed property)
- L2340: Must place an actual Thalia creature on board (computed property)
- L2347: Chalice at X=0: blocks CMC 0 spells
- L2348: Chalice at X=0: blocks CMC 0 spells
- L2464: Chalice@1 blocks a CMC-1 spell
- L2466: Chalice@1 blocks a CMC-1 spell
- L2468: Chalice@1 blocks a CMC-1 spell
- L2472: Trinisphere taxes CMC-1 to cost 3
- L2473: Trinisphere taxes CMC-1 to cost 3
- L2478: Thalia +1 tax on noncreature spells
- L2480: Thalia +1 tax on noncreature spells
- L2483: Thalia +1 tax on noncreature spells
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket tax_effects")


@pytest.mark.fast
def test_placeholder_tax_effects():
    """Migration ticket: see docs/proposals/tickets/tax_effects.md."""
    assert False, "stub — migrate from sim.py:1987-2483"
