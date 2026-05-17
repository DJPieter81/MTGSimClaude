"""Goblins decklist runs Wasteland for land disruption.

Audit (docs/audits/goblins_vs_depths.md): real Legacy Goblins lists
include 2–4 Wasteland to disrupt land-combo (Depths, Cloudpost, Lands)
and tax nonbasic-heavy manabases. The simulator's goblins build at
decks/goblins.py:make_goblins_deck shipped with zero Wastelands,
making the `interaction.soft_to_wasteland: False` signal misleading.

Rule (no card names): Tribal aggro shells operating in a Legacy meta
must include some land-disruption when the deck plugin's interaction
profile claims `soft_to_wasteland: False`.
"""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_goblins_deck_contains_wastelands():
    """The deck list must include at least 2 Wastelands (tag `wl`) so
    engine helpers at engine.py:1272 / 2337 / 2868 / 3081 (Wasteland
    selectors keyed on tag == 'wl') can activate them."""
    from cards import DECKS

    deck = DECKS['goblins']()
    wastelands = [c for c in deck if c.tag == 'wl']
    assert len(wastelands) >= 2, (
        f'goblins decklist must include ≥2 Wastelands; found {len(wastelands)}')


@pytest.mark.fast
def test_goblins_deck_still_60_cards():
    """Land-rebalance must keep the 60-card constraint."""
    from cards import DECKS
    assert len(DECKS['goblins']()) == 60
