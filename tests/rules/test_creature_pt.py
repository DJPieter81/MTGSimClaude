"""Creature P/T rules tests (migrated from sim.py:1953-1954).

Mechanic under test: Tarmogoyf-style P/T derived from the set of card types
present across both graveyards. Power = number of distinct gy_types across
both yards; toughness = power + 1.
"""
from __future__ import annotations

import pytest

from rules import Card, CardType, MTGRules


def _mkcard(gy_type: str) -> Card:
    """Build a minimal Card whose graveyard type slot is the only thing that matters."""
    return Card(
        name="x",
        card_type=CardType.INSTANT,
        cmc=1,
        mana_cost={},
        colors=set(),
        gy_type=gy_type,
    )


@pytest.mark.fast
def test_pt_counts_distinct_graveyard_types():
    # 4 distinct types across both yards -> 4 / (4+1)
    pw, pt = MTGRules.tarmogoyf_pt(
        [_mkcard("instant"), _mkcard("sorcery")],
        [_mkcard("creature"), _mkcard("land")],
    )
    assert (pw, pt) == (4, 5)


@pytest.mark.fast
def test_pt_with_empty_graveyards_is_zero_one():
    # No types in either yard -> 0 / (0+1)
    assert MTGRules.tarmogoyf_pt([], []) == (0, 1)
