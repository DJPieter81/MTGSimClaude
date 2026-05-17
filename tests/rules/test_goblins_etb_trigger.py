"""Goblin ETB triggers fire on every entry path (cast, Vial flash, cheat).

Audit (docs/audits/goblins_vs_dimir_d.md) flagged that Aether Vial-flashed
creatures skip their ETB triggers — Muxus Vialed in at vial_counters=6
"silently" enters without revealing the top 6. The fix is a single
`_fire_goblin_etb(card, ...)` helper invoked from every entry path so
Vial / Lackey / hard-cast all share ETB resolution.

Rule (no card names): A creature's ETB-triggered ability resolves on
*every* zone change into play (CR 603.6a) — the cast/cheat/flash
distinction does not gate the trigger.
"""
from __future__ import annotations

import pytest


def _build_gs():
    """Construct a GameState with goblins/dimir libraries and empty hands."""
    from cards import DECKS
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['goblins']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['dimir']())),
        p1_goes_first=True,
    )
    gs.p1_deck = 'goblins'
    gs.p2_deck = 'dimir'
    return gs


@pytest.mark.fast
def test_vial_flashed_muxus_fires_reveal_etb():
    """Muxus entering via Aether Vial must reveal top 6 and put Goblins
    into play — same as a hard-cast or Lackey-cheat entry."""
    from rules import Card, CardType

    gs = _build_gs()

    # Take Muxus out of library, put in hand.
    muxus = next(c for c in gs.p1.library if c.tag == 'muxus')
    gs.p1.library.remove(muxus)
    gs.p1.hand = [muxus]

    # Force top-6 to be all goblins.
    goblin_cards = [c for c in gs.p1.library
                    if c.is_creature() and c.tag in (
                        'lackey', 'matron', 'ringleader', 'warchief',
                        'expert', 'sling', 'cratermaker', 'pashalik')]
    assert len(goblin_cards) >= 6, 'fixture: deck must have ≥6 non-muxus goblins'
    top_six = goblin_cards[:6]
    for c in top_six:
        gs.p1.library.remove(c)
    gs.p1.library = top_six + gs.p1.library

    # Vial in play with 6 counters — use PlayerState helper (sets controller).
    vial_card = Card(name='Aether Vial',  # abstraction-allow: rules-test fixture
                     card_type=CardType.ARTIFACT, cmc=1,
                     mana_cost={'generic': 1}, colors=set(),
                     tag='vial', gy_type='artifact')
    gs.p1.put_artifact_in_play(vial_card)
    gs.vial_counters = 6
    gs._vial_entered_last_turn = True  # block the upkeep-tick on this turn

    creatures_before = len(gs.p1.creatures)

    from decks.goblins import _strategy_goblins
    _strategy_goblins(gs.p1, gs.p2, gs, total_mana=0,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    creatures_added = len(gs.p1.creatures) - creatures_before
    assert creatures_added >= 2, (
        f'Muxus Vial-flash should fire reveal-6 ETB. '
        f'creatures +{creatures_added}. '
        f'Expected creatures +2 or more (Muxus + ≥1 revealed goblin).')


@pytest.mark.fast
def test_vial_flashed_matron_tutors_muxus():
    """Matron entering via Vial must fire the tutor-Muxus ETB —
    same as a hard-cast entry."""
    from rules import Card, CardType

    gs = _build_gs()

    matron = next(c for c in gs.p1.library if c.tag == 'matron')
    gs.p1.library.remove(matron)
    gs.p1.hand = [matron]

    muxus_in_lib_before = sum(1 for c in gs.p1.library if c.tag == 'muxus')
    assert muxus_in_lib_before >= 1, 'fixture: muxus must be in library'

    vial_card = Card(name='Aether Vial',  # abstraction-allow: rules-test fixture
                     card_type=CardType.ARTIFACT, cmc=1,
                     mana_cost={'generic': 1}, colors=set(),
                     tag='vial', gy_type='artifact')
    gs.p1.put_artifact_in_play(vial_card)
    gs.vial_counters = 3  # Matron CMC is 3
    gs._vial_entered_last_turn = True  # block the upkeep-tick on this turn

    from decks.goblins import _strategy_goblins
    _strategy_goblins(gs.p1, gs.p2, gs, total_mana=0,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    muxus_in_lib_after = sum(1 for c in gs.p1.library if c.tag == 'muxus')
    muxus_in_hand_after = sum(1 for c in gs.p1.hand if c.tag == 'muxus')

    assert muxus_in_hand_after >= 1 or muxus_in_lib_after < muxus_in_lib_before, (
        f'Matron Vial-flash should tutor Muxus from library to hand. '
        f'muxus in library {muxus_in_lib_before} → {muxus_in_lib_after}, '
        f'muxus in hand → {muxus_in_hand_after}')
