"""Migration stub for ticket: combat_damage.

Source: sim.py:run_rules_tests() lines 1966-4689
Test count: 20
Headers covered:
- L1966: Summoning sickness + attacker tapping
- L1967: Summoning sickness + attacker tapping
- L1969: Summoning sickness + attacker tapping
- L1972: C2: tap_attacker actually taps
- L1973: C2: tap_attacker actually taps
- L2192: Now mark 3 damage (lethal) - should die
- L4029: reaches A on combat (because removal stood in for the swing).
- L4143: JSON's `values` block carries the four chosen thresholds.
- L4145: JSON's `values` block carries the four chosen thresholds.
- L4147: JSON's `values` block carries the four chosen thresholds.
- L4149: JSON's `values` block carries the four chosen thresholds.
- L4238: / pressure-via-combat), not card names.
- L4242: / pressure-via-combat), not card names.
- L4246: / pressure-via-combat), not card names.
- L4358: _is_combat_decision recognises via the 'attack' prefix.
- L4421: Rule A11 — typed CombatDecision buckets to counts['combat'].
- L4655: Rule CB1 — to_token() byte-equality for block: 'block_<tag>'.
- L4663: different buckets via `phase` (combat-axis hold carries phase='combat').
- L4676: treats block / hold / attack identically (any CombatDecision counts).
- L4689: Rule CB4 — typed mix of block + hold + attack all roll into combat.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket combat_damage")


@pytest.mark.fast
def test_placeholder_combat_damage():
    """Migration ticket: see docs/proposals/tickets/combat_damage.md."""
    assert False, "stub — migrate from sim.py:1966-4689"
