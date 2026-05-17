"""Rules tests migrated from sim.py:run_rules_tests() lines 2098-2099.

Audit: Daze tapped-out logic (opp_mana <= spell_cmc).

Daze (CR 118.5 / alternate cost) is "free" only when the controller of the
spell on the stack cannot afford to pay the {1} return-an-Island cost. From
the caster's perspective the heuristic is: the opponent is effectively tapped
out for the CMC of the spell they just cast iff their available untapped mana
count <= that spell's CMC (the cast itself consumed mana down to <= 0 spare).
"""
from __future__ import annotations

import pytest

from game import PlayerState
from rules import Card, CardType, LandPermanent


def _untapped_dual() -> LandPermanent:
    """Build a single untapped Underground Sea-style dual land permanent."""
    c = Card(
        name='Underground Sea',  # abstraction-allow: rules-test fixture
        card_type=CardType.LAND,
        cmc=0,
        mana_cost={},
        colors=set(),
        is_basic=False,
        produces={'U'},
        subtypes=set(),
        tag='dual',
        gy_type='land',
    )
    perm = LandPermanent(card=c, controller='o')
    perm.tapped = False
    return perm


def _opp_with_lands(n: int) -> PlayerState:
    opp = PlayerState(name='o', hand=[], library=[])
    for _ in range(n):
        opp.lands.append(_untapped_dual())
    return opp


# Spell CMC the opponent just cast — Daze targets a CMC-3 spell here.
# Rule: opp is "tapped out" iff available_mana_count() <= spell.cmc.
SPELL_CMC = 3


@pytest.mark.fast
def test_daze_free_when_opp_tapped_out_after_casting_equal_cmc_spell():
    """3 untapped lands casting a CMC-3 spell leaves 0 spare mana → Daze is free."""
    opp = _opp_with_lands(3)
    assert (opp.available_mana_count() <= SPELL_CMC) is True


@pytest.mark.fast
def test_daze_not_free_when_opp_has_spare_mana_after_casting_spell():
    """4 untapped lands casting a CMC-3 spell leaves 1 spare → opp pays Daze cost."""
    opp = _opp_with_lands(4)
    assert (opp.available_mana_count() <= SPELL_CMC) is False
