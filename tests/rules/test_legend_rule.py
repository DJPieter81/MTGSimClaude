"""Legend rule (CR 704.5j) — migrated from sim.py:2267-2268.

Two legendary permanents with the same name controlled by the same player
cause that player to choose one to keep; the rest go to their owner's
graveyard as a state-based action.
"""
from __future__ import annotations

import pytest

from cards import make_bug_deck, make_dimir_deck
from game import GameState, PlayerState
from rules import Card, CardType, Permanent


def _make_tagged_creature(name: str, tag: str, cmc: int = 1) -> Permanent:
    c = Card(
        name=name,
        card_type=CardType.CREATURE,
        cmc=cmc,
        mana_cost={},
        colors={'U'},
        base_power=0,
        base_toughness=3,
        tag=tag,
        gy_type='creature',
    )
    p = Permanent(card=c, controller='o')
    p.power_mod = 0
    p.toughness_mod = 0
    return p


def _fresh_legend_gs() -> GameState:
    """Two legendary copies of Tamiyo controlled by p2."""
    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )
    # 'Tamiyo, Inquisitive Student' is legendary; engine reads the flag from
    # the card registry / name lookup, so naming it here is mechanic-bound.
    gs.p2.creatures = [
        _make_tagged_creature('Tamiyo, Inquisitive Student', 'tamiyo'),  # abstraction-allow: rules-test
        _make_tagged_creature('Tamiyo, Inquisitive Student', 'tamiyo'),  # abstraction-allow: rules-test
    ]
    gs.state_based_actions()
    return gs


@pytest.mark.fast
def test_legend_rule_collapses_duplicate_legendaries_to_one():
    gs = _fresh_legend_gs()
    # CR 704.5j: only one legendary copy with a given name may remain.
    assert len(gs.p2.creatures) == 1


@pytest.mark.fast
def test_legend_rule_sends_extra_legendary_to_graveyard():
    gs = _fresh_legend_gs()
    # CR 704.5j: the extras are put into their owner's graveyard.
    assert len(gs.p2.graveyard) == 1
