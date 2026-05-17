"""Wasteland targeting (CR 305.6) — migrated from sim.py:2063-2066.

CR 305.6: a land is "basic" iff it has the supertype "basic". Wasteland's
ability targets nonbasic lands. Fetchlands (e.g. Polluted Delta) are also
nonbasic and therefore legal targets. Wasteland cannot target itself
because it is the source of the ability (and is itself nonbasic, but the
engine flags Wasteland-tagged lands as illegal targets to model the
"another land" semantics used in the simulator).
"""
from __future__ import annotations

import pytest

from rules import Card, CardType, LandPermanent, MTGRules


def _mkland(name: str, tag: str = '', is_basic: bool = False,
            subtypes=None) -> LandPermanent:
    c = Card(name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
             colors=set(), is_basic=is_basic, produces={'U'},
             subtypes=set(subtypes or []), tag=tag, gy_type='land')
    return LandPermanent(card=c, controller='o')


@pytest.mark.fast
def test_wasteland_misses_basic_land():
    # CR 305.6: basic supertype protects basic lands from Wasteland.
    basic_island = _mkland('Island', is_basic=True, subtypes=['Island'])  # abstraction-allow: rules-test
    assert MTGRules.wasteland_can_target(basic_island) is False


@pytest.mark.fast
def test_wasteland_hits_nonbasic_dual_land():
    # Dual lands lack the basic supertype, so they are legal Wasteland targets.
    underground = _mkland('Underground Sea', tag='dual')  # abstraction-allow: rules-test
    assert MTGRules.wasteland_can_target(underground) is True


@pytest.mark.fast
def test_wasteland_hits_nonbasic_fetch_land():
    # Fetchlands are nonbasic and therefore legal Wasteland targets.
    polluted = _mkland('Polluted Delta', tag='fetch')  # abstraction-allow: rules-test
    assert MTGRules.wasteland_can_target(polluted) is True


@pytest.mark.fast
def test_wasteland_cannot_target_itself():
    # The Wasteland ability cannot select the source itself as its target.
    wl_self = _mkland('Wasteland', tag='wl')  # abstraction-allow: rules-test
    assert MTGRules.wasteland_can_target(wl_self) is False
