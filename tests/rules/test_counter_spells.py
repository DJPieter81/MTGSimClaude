"""Migrated from sim.py:run_rules_tests() lines 4555-4699.

These two tests are gameability-resistance / interaction-axis checks on the
structural grader. The slice is misnamed "counter_spells" by historical
accident; what is actually asserted is:

- The structural grader buckets ONLY by typed `kind` (and the `chosen` prefix
  on the legacy path), so prose keywords in `reason` cannot inflate axis
  counters when `chosen='pass'`.
- An interaction-deck win with 3 combat tokens (block + hold + attack mix)
  grades 'A' on the combat axis (K_INTER_COMBAT_A floor).
"""
from __future__ import annotations

import os
import sys

import pytest

# scripts/ is on sys.path lazily inside run_rules_tests(); replicate that here.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import structural_grader as _sg2  # type: ignore  # noqa: E402
from decision import CombatDecision as _CbD  # noqa: E402


@pytest.mark.fast
def test_prose_keywords_in_reason_do_not_inflate_disruption_axes():
    """Rule A20: with chosen='pass' (no recognized prefix), English prose in
    `reason` must NOT raise the removal or discard counters. The bucket is
    the sole source of truth — keyword-stuffing has no effect."""
    prose_gaming = [
        {'turn': 2, 'deck': 'bug', 'chosen': 'pass',
         'reason': 'considered wasteland surgical extract but held back'},
        {'turn': 3, 'deck': 'bug', 'chosen': 'pass',
         'reason': 'wasteland and surgical extraction in hand'},
    ]
    counts = _sg2._count_structural(prose_gaming, deck1='bug')
    assert (counts['removal'], counts['discard']) == (0, 0)


@pytest.mark.fast
def test_interaction_deck_win_with_three_combat_tokens_grades_combat_axis_a():
    """Rule CB5: an interaction-deck win whose strategic-decision trace carries
    3 CombatDecision tokens (block + hold + attack mix) clears the
    K_INTER_COMBAT_A floor and grades 'A' on the combat axis."""
    typed_mix = [
        _CbD(turn=2, deck='bug', phase='combat', kind='hold',
             attacker_count=1, attacker_tag='murktide'),
        _CbD(turn=3, deck='bug', phase='combat', kind='block',
             attacker_count=1, attacker_tag='goyf'),
        _CbD(turn=4, deck='bug', phase='combat', kind='attack',
             attacker_count=2, attacker_tag='creatures'),
    ]
    counts = _sg2._count_structural(typed_mix, deck1='bug')
    trace_int_win = {
        'deck1': 'bug', 'deck2': 'storm', 'winner': 'p1', 'game_length': 8,
    }
    grade, _justification = _sg2._grade_combat(trace_int_win, counts)
    assert grade == 'A'
