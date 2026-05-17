"""Painter prefers Karn over Ring when Chalice@1 blocks Grindstone.

Audit (docs/audits/painter_vs_eldrazi.md): seed 42 T8 had Grim Monolith
cracked for 5 mana, but the strategy cast The One Ring ({4}) ahead of
Karn ({4}), draining the budget. Karn would have wished Grindstone
into play, bypassing Eldrazi's Chalice@1 which was blocking the 4
Grindstones in hand for 4 turns. With Ring instead of Karn, combo was
delayed ≥1 turn against a 4-power clock that killed next turn.

Rule (no card names, generalises beyond Painter): When a continuous
effect (Chalice with X = the combo piece's CMC) blocks an in-hand
combo piece, the tutor / wish that bypasses the continuous effect
outranks card-draw engines in budget priority. The wish puts the
piece directly into play; the draw engine does nothing while the lock
holds.
"""
from __future__ import annotations

import pytest


def _build_painter_vs_eldrazi():
    from cards import DECKS
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=list(DECKS['painter']())),
        p2=PlayerState(name='o', hand=[], library=list(DECKS['dimir']())),  # surrogate opp
        p1_goes_first=True,
    )
    gs.p1_deck = 'painter'
    gs.p2_deck = 'dimir'
    return gs


@pytest.mark.fast
def test_painter_prioritises_karn_over_ring_under_chalice_one():
    """With Chalice@1 in play, Grindstone in hand, and exactly 4 mana
    available, Painter must cast Karn (not Ring). Ring drains the
    budget; Karn wishes Grindstone and bypasses the Chalice lock."""
    from cards import basic_land

    gs = _build_painter_vs_eldrazi()

    # Put Karn + Ring + Grindstone in hand, rest stays in library.
    karn = next(c for c in gs.p1.library if c.tag == 'karn')
    ring = next(c for c in gs.p1.library if c.tag == 'ring')
    grind = next(c for c in gs.p1.library if c.tag == 'grind')
    for c in (karn, ring, grind):
        gs.p1.library.remove(c)
    gs.p1.hand = [karn, ring, grind]

    # 4 untapped lands for mana.
    for _ in range(4):
        gs.p1.play_land(basic_land('Wastes', 'C', 'Wastes'))

    # Chalice@1 in play — blocks Grindstone (CMC 1).
    gs.chalice_x = 1

    from engine import _strategy_painter
    _strategy_painter(gs.p1, gs.p2, gs, total_mana=4,
                      log_fn=lambda *a, **k: None,
                      log_entries=[])

    # Karn must be deployed; Ring must NOT have consumed the 4-mana budget.
    karn_deployed = any(p.card.tag == 'karn' for p in gs.p1.artifacts)
    ring_deployed = any(p.card.tag == 'ring' for p in gs.p1.artifacts)
    karn_in_hand = any(c.tag == 'karn' for c in gs.p1.hand)
    ring_in_hand = any(c.tag == 'ring' for c in gs.p1.hand)

    assert karn_deployed, (
        f'Painter must cast Karn at 4 mana when Chalice@1 blocks Grindstone. '
        f'karn_in_hand={karn_in_hand}, ring_deployed={ring_deployed}, '
        f'ring_in_hand={ring_in_hand}')
    assert not ring_deployed, (
        'Ring must NOT consume the budget — it drains mana that Karn needs '
        'to wish-bypass the Chalice lock.')
