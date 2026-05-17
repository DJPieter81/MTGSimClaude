"""Burn-adjacent rules migrated from `sim.run_rules_tests()` lines 2647-3956.

Slice covers two unrelated mechanics that the original monolith colocated:

1.  Sideboard-hate density for Burn-heavy metas:  the Wan Shi Tong list must
    carry the canonical 4 copies of its anti-Burn sanctifier.
2.  Structural grader's combat-grade lift for an aggro-deck win that logged a
    combat decision — burn can win pre-combat, so the *combat-decision-present*
    branch is the one this slice pins.

The third assertion mirrors the original `try/except` harness in `sim.py`:
the bare wrapper itself must import without error so the rule above can run.
"""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_anti_burn_sanctifier_count_in_control_sideboard():
    """Canonical anti-Burn hate density: 4 copies of the sanctifier tag.

    2 copies → ~22% chance to have one in opener vs Burn, 3 → ~32%, 4 → ~40%.
    Real Bo1 lists run 3-4 main; 4 is the canonical density.
    """
    from cards import DECKS
    sanct_count = sum(
        1 for c in DECKS['wan_shi_tong']() if c.tag == 'sanctifier'
    )
    assert sanct_count == 4


@pytest.mark.fast
def test_anti_burn_sanctifier_harness_imports_without_error():
    """Mirrors the source `except Exception` fallback: the deck-data import
    and tag-count plumbing must not raise — that's the precondition the
    original harness wrapped in try/except."""
    from cards import DECKS
    assert 'wan_shi_tong' in DECKS
    # Building the deck and reading `.tag` on each card must not raise.
    deck = DECKS['wan_shi_tong']()
    assert all(hasattr(c, 'tag') for c in deck)


@pytest.mark.fast
def test_structural_grader_aggro_win_with_combat_decision_grades_a():
    """Aggro deck + combat decision logged + win → combat grade 'A'.

    The 'B+ if no combat decision was logged' branch exists because burn can
    win pre-combat; this test pins the *combat-decision-present* branch.
    """
    from scripts import structural_grader as sg
    trace = {
        'deck1': 'goblins', 'deck2': 'uwx', 'winner': 'p1',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 3, 'phase': 'combat', 'chosen': 'attack with 2 goblins',
             'candidates': [], 'reason': ''},
        ],
    }
    counts = sg._count_structural(trace['strategic_decisions'])
    grade, _just = sg._grade_combat(trace, counts)
    assert grade == 'A'
