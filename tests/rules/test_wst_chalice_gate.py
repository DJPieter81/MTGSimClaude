"""Wan Shi Tong Chalice-on-1 deployment gate.

Audits flag a class-wide bug where Chalice@1 fires while the protagonist's
own CMC-1 removal pool (Swords to Plowshares, March of Otherworldly Light)
is still deep in the library:
- docs/audits/wan_shi_tong_vs_mono_black.md (own CMC-1 lockout T10)
- docs/audits/wan_shi_tong_vs_dnt.md (4× March + 4× STP bricked)
- docs/audits/wan_shi_tong_vs_cloudpost.md

Rule (no card names): Chalice of the Void at X=1 must not be deployed
while the controller's own CMC-1 spell density (hand + library) exceeds
a low remaining-count threshold. CR 113.6 — once Chalice resolves with
X=1, every CMC-1 spell the controller draws will be countered on cast.
"""
from __future__ import annotations

import pytest


def _build_gs():
    from cards import DECKS
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['wan_shi_tong']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['dnt']())),
        p1_goes_first=True,
    )
    gs.p1_deck = 'wan_shi_tong'
    gs.p2_deck = 'dnt'
    return gs


@pytest.mark.fast
def test_wst_does_not_chalice_when_library_has_own_cmc1_spells():
    """With Chalice in hand and the full WST library (8 CMC-1 spells:
    4 STP + 4 March), deploying Chalice@1 is negative-EV. Strategy must
    skip Chalice deployment this turn."""
    from rules import Card, CardType
    from cards import basic_land

    gs = _build_gs()

    # Pull Chalice out of library, into hand.
    chalice = next(c for c in gs.p1.library if c.tag == 'chalice')
    gs.p1.library.remove(chalice)
    gs.p1.hand = [chalice]

    # Confirm fixture: ≥4 CMC-1 nonland in library (March + STP).
    own_cmc1_lib = sum(1 for c in gs.p1.library if c.cmc == 1 and not c.is_land())
    assert own_cmc1_lib >= 6, (
        f'fixture: WST library must have ≥6 own CMC-1 nonlands, got {own_cmc1_lib}')

    # Give the strategy 2 mana (Chalice X=1 costs 2 to cast for X=1).
    # Use Ancient Tomb (taps for 2) — already in library; need 2 land drops.
    # Easier: directly tap untapped lands. Mock by placing 2 basics in play.
    plains_card = basic_land('Plains', 'W', 'Plains')
    gs.p1.play_land(plains_card)
    plains_card2 = basic_land('Plains', 'W', 'Plains')
    gs.p1.play_land(plains_card2)

    artifacts_before = len(gs.p1.artifacts)

    from decks.wan_shi_tong import _strategy_wst
    _strategy_wst(gs.p1, gs.p2, gs, total_mana=2,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    chalice_in_play = any(p.card.tag == 'chalice' for p in gs.p1.artifacts)
    assert chalice_in_play is False, (
        f'WST must not deploy Chalice@1 with {own_cmc1_lib} own CMC-1 spells '
        f'still in library — locks out own removal plan.')


@pytest.mark.fast
def test_wst_does_deploy_chalice_when_library_drained_of_cmc1():
    """Late-game with the CMC-1 pool already drawn / spent (≤2 left in
    library), Chalice@1 becomes net positive — strategy must still fire."""
    from rules import Card, CardType
    from cards import basic_land

    gs = _build_gs()

    chalice = next(c for c in gs.p1.library if c.tag == 'chalice')
    gs.p1.library.remove(chalice)
    gs.p1.hand = [chalice]

    # Strip all but 1 own-CMC-1 from library (simulate late-game drainage).
    to_remove = [c for c in gs.p1.library if c.cmc == 1 and not c.is_land()]
    for c in to_remove[:-1]:    # keep 1
        gs.p1.library.remove(c)
        gs.p1.graveyard.append(c)

    own_cmc1_lib = sum(1 for c in gs.p1.library if c.cmc == 1 and not c.is_land())
    assert own_cmc1_lib <= 1, f'fixture: should be ≤1 CMC-1 in library, got {own_cmc1_lib}'

    plains_card = basic_land('Plains', 'W', 'Plains')
    gs.p1.play_land(plains_card)
    plains_card2 = basic_land('Plains', 'W', 'Plains')
    gs.p1.play_land(plains_card2)

    from decks.wan_shi_tong import _strategy_wst
    _strategy_wst(gs.p1, gs.p2, gs, total_mana=2,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    chalice_in_play = any(p.card.tag == 'chalice' for p in gs.p1.artifacts)
    assert chalice_in_play is True, (
        f'WST should deploy Chalice@1 once own CMC-1 pool is depleted '
        f'(only {own_cmc1_lib} in library).')
