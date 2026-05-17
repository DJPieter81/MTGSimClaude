"""Migration stub for ticket: misc_rules_part4.

Source: sim.py:run_rules_tests() lines 2938-3140
Test count: 15
Headers covered:
- L2938: Each subclass must inherit from Pile.
- L3001: Branch 1: AGGRO opp at low life, Lurrus available → LurrusPile.
- L3010: Branch 2: COMBO opp → TendrilsPile.
- L3028: Branch 4: INTERACTION opp without LED → OraclePile default.
- L3035: inputs (no mutation between calls).
- L3038: inputs (no mutation between calls).
- L3063: TendrilsPile selected).
- L3067: TendrilsPile selected).
- L3119: cast if the payment would reduce life ≤ 0.
- L3123: cast if the payment would reduce life ≤ 0.
- L3129: tweak to the literals can't silently invert the strategic intent.
- L3131: tweak to the literals can't silently invert the strategic intent.
- L3134: tweak to the literals can't silently invert the strategic intent.
- L3137: tweak to the literals can't silently invert the strategic intent.
- L3140: tweak to the literals can't silently invert the strategic intent.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part4")


@pytest.mark.fast
def test_placeholder_misc_rules_part4():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part4.md."""
    assert False, "stub — migrate from sim.py:2938-3140"
