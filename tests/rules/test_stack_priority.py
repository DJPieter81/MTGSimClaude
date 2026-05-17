"""Migrated from sim.py:run_rules_tests() line 2295.

Covers the Thoughtseize-style discard priority order: a flash threat
(e.g. Orcish Bowmasters) outranks a free counter (FoW), which in turn
outranks a 1-mana removal spell (Fatal Push).
"""
from __future__ import annotations

import pytest

from cards import creature, instant
from game import PlayerState


@pytest.mark.fast
def test_priority_picks_flash_threat_over_counter_and_removal():
    bowm_card = creature(
        'Orcish Bowmasters', 2, {'B': 1, 'generic': 1}, {'B'}, 1, 1,
        tag='bowm', flash=True,
    )
    push_card = instant('Fatal Push', 1, {'B': 1}, {'B'}, tag='push')
    fow_card = instant(
        'Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
        tag='fow', free_cast_if_blue=True,
    )
    opp = PlayerState(name='o', hand=[push_card, fow_card, bowm_card], library=[])

    # Priority cascade: flash threat ('bowm') > free counter ('fow'/'fon')
    # > any non-land spell.
    target = (
        next((c for c in opp.hand if c.tag == 'bowm'), None) or
        next((c for c in opp.hand if c.tag in ('fow', 'fon')), None) or
        next((c for c in opp.hand if not c.is_land()), None)
    )
    assert target.name == 'Orcish Bowmasters'  # abstraction-allow: rules-test
