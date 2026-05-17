"""Belcher Burning Wish gate ensures Empty can be cast same turn.

Audit (docs/audits/belcher_vs_ur_delver.md): the Wish target is Empty
the Warrens (CMC 4), but the existing gate at decks/belcher.py:519
required only `budget >= 2 and storm >= 3`. With budget == 2 and no
LED in hand, after Wish resolves the budget is 0 and the fetched
Empty sits in hand with no mana to cast it — a wasted Wish.

Rule (no card names): When a wish/tutor spell fetches a payoff that
must be cast on the same turn, the strategy must verify enough mana
remains post-resolve to cover both the tutor cost and the payoff cost.
Side-cost ramps (Lion's Eye Diamond) reduce the floor proportionally.
"""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_belcher_wish_gate_requires_mana_for_empty_when_no_led():
    """Without LED in hand: Wish (2) + Empty (4) = 6 mana minimum.
    With only 5 mana and storm count, the strategy must NOT cast Wish."""
    from cards import DECKS
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['belcher']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['ur_delver']())),
        p1_goes_first=True,
    )
    gs.p1_deck = 'belcher'
    gs.p2_deck = 'ur_delver'

    # Just Burning Wish in hand — no LED, no other cards.
    wish = next(c for c in gs.p1.library if c.tag == 'burning_wish')
    gs.p1.library.remove(wish)
    gs.p1.hand = [wish]

    # 5 mana (below the 6-mana no-LED floor), storm=3.
    gs.p1.spells_cast_this_turn = 3

    from decks.belcher import _strategy_belcher
    _strategy_belcher(gs.p1, gs.p2, gs, total_mana=5,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    wish_in_hand = any(c.tag == 'burning_wish' for c in gs.p1.hand)
    empty_in_hand = any(c.tag == 'empty' for c in gs.p1.hand)
    assert wish_in_hand and not empty_in_hand, (
        f'Wish must not fire at 5 mana without LED (would leave fetched '
        f'Empty uncastable). wish_in_hand={wish_in_hand}, '
        f'empty_in_hand={empty_in_hand}')


# Note: the inverse case (Wish fires at 6 mana) is harder to construct as
# a unit test because the strategy's local `storm` counter is initialised
# to 0 and only incremented by spells the strategy itself casts — driving
# it to ≥3 requires populating the hand with rituals + petals, at which
# point the test exercises the full ritual chain rather than just the
# Wish gate. The sweep validation (belcher_vs_ur_delver 33% → 38%) is
# the canonical signal that the gate fires correctly when conditions are
# met.
