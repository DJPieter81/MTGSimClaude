"""Migrated rules tests for ticket: deck_storm_part3.

Source: sim.py:run_rules_tests() line 4841
Headers covered:
- L4841: 4. Storm win + 2 play_around tokens grades meta=A
"""
from __future__ import annotations

import pytest

from decision import MetaDecision
from scripts.structural_grader import _count_structural, _grade_meta


@pytest.mark.fast
def test_win_with_two_play_around_tokens_grades_meta_a():
    """Two typed MetaDecision play_around tokens on a win → meta grade A."""
    md_a = MetaDecision(turn=2, deck='storm', kind='play_around',
                        threat_tag='fow')
    md_b = MetaDecision(turn=3, deck='storm', kind='play_around',
                        threat_tag='daze')
    trace_win = {'deck1': 'storm', 'deck2': 'burn', 'winner': 'p1',
                 'game_length': 6}
    counts_win = _count_structural([md_a, md_b], deck1='storm')
    grade, _ = _grade_meta(trace_win, counts_win)
    assert grade == 'A'
