"""Pytest migration for ticket: burn_triggers.

Source: sim.py:run_rules_tests() line 2357
Section: Eidolon — 2 damage per CMC <= 3 spell
"""
from __future__ import annotations

import pytest

from rules import Card, CardType
from game import GameState, PlayerState
from engine import _eidolon_trigger


@pytest.mark.fast
def test_eidolon_triggers_on_cheap_spell_dealing_two_to_caster():
    """Eidolon of the Great Revel deals 2 damage to the caster of any spell
    with CMC <= 3 (CR 603 triggered ability; oracle text: 'whenever a player
    casts a spell with converted mana cost 3 or less')."""
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[], life=20),
        p2=PlayerState(name='o', hand=[], library=[], life=20),
    )
    gs.eidolon_active = True
    bolt = Card(
        name='Lightning Bolt', card_type=CardType.INSTANT, cmc=1,
        mana_cost={'R': 1}, colors={'R'}, tag='bolt',
    )
    _eidolon_trigger(gs, bolt, lambda *a, **kw: None, caster=gs.p1)
    # Starting life 20 - 2 (Eidolon trigger) = 18
    assert gs.p1.life == 18
