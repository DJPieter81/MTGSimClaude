"""WST Karakas bounces opponent legendary creatures.

Audit (docs/audits/wan_shi_tong_vs_dnt.md): WST runs 1 Karakas, but
the strategy never activates it — Thalia stays on board taxing every
spell. The engine's existing Karakas helper (`_strategy_dnt` at
engine.py:2890) only targets Murktide via hardcoded tag check.

Refactor: `game.LEGENDARY_CREATURE_TAGS` is the single source of truth
for legendary creature tags (consumed by both the legend rule
enforcement at game.py:534 and the deck-strategy Karakas activations).
Extending the set auto-extends Karakas targeting.

Rule (no card names): a player who controls Karakas may, during their
main phase, return an opponent's legendary creature to its owner's
hand. Targeting is enforced by the legendary supertype (modelled as
membership in `LEGENDARY_CREATURE_TAGS`).
"""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_legendary_tags_includes_thalia():
    """The shared legendary-tag set must include Thalia so the legend
    rule and Karakas both target her."""
    from game import LEGENDARY_CREATURE_TAGS
    assert 'thalia' in LEGENDARY_CREATURE_TAGS


@pytest.mark.fast
def test_wst_karakas_bounces_opponent_thalia():
    """With Karakas untapped on WST's side and Thalia in play for opp,
    the WST strategy must bounce Thalia."""
    from cards import DECKS, basic_land, utility_land, creature
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['wan_shi_tong']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['dnt']())),
        p1_goes_first=True,
    )
    gs.p1_deck = 'wan_shi_tong'
    gs.p2_deck = 'dnt'

    # Put a Karakas in play for WST. play_land requires the card to be in
    # hand first.
    karakas = utility_land('Karakas', ['W'], 'karakas')
    gs.p1.hand.append(karakas)
    gs.p1.play_land(karakas)
    # Ensure it's untapped — play_land may tap it under some rules.
    if gs.p1.lands:
        gs.p1.lands[-1].tapped = False

    # Opp Thalia on the battlefield.
    thalia = creature('Thalia, Guardian of Thraben', 2, {'W': 1, 'generic': 1},  # abstraction-allow: rules-test fixture
                      {'W'}, 2, 1, tag='thalia')
    gs.p2.put_creature_in_play(thalia)

    assert any(p.card.tag == 'thalia' for p in gs.p2.creatures)
    thalia_in_hand_before = any(c.tag == 'thalia' for c in gs.p2.hand)
    assert not thalia_in_hand_before

    from decks.wan_shi_tong import _strategy_wst
    _strategy_wst(gs.p1, gs.p2, gs, total_mana=0,
                  log_fn=lambda *a, **k: None,
                  log_entries=[])

    thalia_in_play_after = any(p.card.tag == 'thalia' for p in gs.p2.creatures)
    thalia_in_hand_after = any(c.tag == 'thalia' for c in gs.p2.hand)
    assert not thalia_in_play_after and thalia_in_hand_after, (
        f'Karakas must bounce Thalia. in_play_after={thalia_in_play_after}, '
        f'in_hand_after={thalia_in_hand_after}')
