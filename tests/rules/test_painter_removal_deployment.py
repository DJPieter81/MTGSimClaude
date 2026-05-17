"""Painter strategy must deploy its removal cards.

Audit (docs/audits/painter_vs_burn.md): Painter's `_strategy_painter` at
engine.py:5817 never casts Kozilek's Command or Portable Hole — they sit
in hand while a 3-turn aggro clock kills the protagonist. Per CLAUDE.md
'Strategy Must Model Win Conditions' lesson: every nonland card in the
decklist must be deployable by the strategy.

Rule (no card names): A control deck's strategy must cast its removal
spells when an opponent threat is on the battlefield and mana is
available — otherwise removal in hand is dead cardboard.
"""
from __future__ import annotations

import pytest


def _build_painter_vs_burn():
    from cards import DECKS
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['painter']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['burn']())),
        p1_goes_first=True,
    )
    gs.p1_deck = 'painter'
    gs.p2_deck = 'burn'
    return gs


@pytest.mark.fast
def test_painter_casts_kozileks_command_on_opponent_creature():
    """With Kozilek's Command in hand, ≥4 mana, and an opp creature, the
    strategy must cast Command to remove the threat."""
    from cards import basic_land
    from rules import Card, CardType, Permanent

    gs = _build_painter_vs_burn()

    kcmd = next(c for c in gs.p1.library if c.tag == 'kozcommand')
    gs.p1.library.remove(kcmd)
    gs.p1.hand = [kcmd]

    # Give the strategy 4 mana via 4 basic lands.
    for _ in range(4):
        gs.p1.play_land(basic_land('Wastes', 'C', 'Wastes'))

    # Put an opp creature (Goblin Guide-shape: 2/2 hasty) on the battlefield.
    from cards import creature
    guide = creature('Goblin Guide', 1, {'R': 1}, {'R'}, 2, 2,  # abstraction-allow: rules-test fixture
                     tag='guide')
    gs.p2.put_creature_in_play(guide)
    opp_creatures_before = len(gs.p2.creatures)

    from engine import _strategy_painter
    _strategy_painter(gs.p1, gs.p2, gs, total_mana=4,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    # Either the command is in graveyard (resolved) and opp creature gone,
    # or both are still on the table (didn't fire — bug).
    kcmd_in_grave = any(c.tag == 'kozcommand' for c in gs.p1.graveyard)
    opp_creatures_after = len(gs.p2.creatures)
    assert kcmd_in_grave, (
        f'Kozilek\'s Command must be cast vs opp creature with 4 mana available. '
        f'Still in hand: {any(c.tag == "kozcommand" for c in gs.p1.hand)}; '
        f'opp creatures before/after: {opp_creatures_before}/{opp_creatures_after}')


@pytest.mark.fast
def test_painter_casts_portable_hole_on_opponent_one_drop():
    """With Portable Hole in hand, ≥1 mana, and an opp 1-drop creature,
    the strategy must cast it to exile the threat."""
    from cards import basic_land
    from rules import Card, CardType

    gs = _build_painter_vs_burn()

    hole = next(c for c in gs.p1.library if c.tag == 'hole')
    gs.p1.library.remove(hole)
    gs.p1.hand = [hole]

    # 1 Plains for {W}.
    gs.p1.play_land(basic_land('Plains', 'W', 'Plains'))

    from cards import creature
    guide = creature('Goblin Guide', 1, {'R': 1}, {'R'}, 2, 2,  # abstraction-allow: rules-test fixture
                     tag='guide')
    gs.p2.put_creature_in_play(guide)

    from engine import _strategy_painter
    _strategy_painter(gs.p1, gs.p2, gs, total_mana=1,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    hole_in_play = any(p.card.tag == 'hole' for p in gs.p1.artifacts)
    hole_in_hand = any(c.tag == 'hole' for c in gs.p1.hand)
    assert hole_in_play or not hole_in_hand, (
        'Portable Hole must be cast vs opp 1-drop with 1 mana available')
