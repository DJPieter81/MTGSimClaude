"""Migrated from sim.py:run_rules_tests() lines 4850-4867.

Covers the MetaDecision / meta-axis structural grader (PR #160):
- Storm-loss grading bucket for the meta axis (strict equality, not rank-or-better).
- Gameability resistance: prose mentioning play-around tokens with chosen='pass'
  MUST NOT increment the meta counter.
- Belt-and-braces predicate `_is_meta` rejects 'pass' and accepts the typed token.
- Import sentinel: the decision algebra + structural-grader symbols import cleanly
  (corresponds to the L4867 except-block sentinel in the legacy harness).
"""
from __future__ import annotations

import pytest

from decision import MetaDecision
from scripts.structural_grader import (
    _count_structural,
    _grade_meta,
    _is_meta,
)


@pytest.mark.fast
def test_meta_axis_loss_with_one_play_around_grades_C_plus():
    # Storm loss + 1 play_around → meta=C+ (strict equality, not rank-or-better).
    md = MetaDecision(turn=2, deck='storm', kind='play_around', threat_tag='fow')
    trace_loss = {'deck1': 'storm', 'deck2': 'dimir', 'winner': 'p2',
                  'game_length': 5}
    counts_loss = _count_structural([md], deck1='storm')
    grade_loss, _ = _grade_meta(trace_loss, counts_loss)
    assert grade_loss == 'C+'


@pytest.mark.fast
def test_meta_axis_gameability_resistance_prose_with_pass_chosen():
    # Prose 'play around fow daze' in `reason` with chosen='pass' MUST NOT
    # increment the meta bucket — the structural grader credits only typed
    # decisions or 'meta_*' chosen tokens, not free-form prose.
    gameable = {'turn': 1, 'deck': 'storm', 'phase': 'meta',
                'chosen': 'pass', 'candidates': ['fire', 'pass'],
                'reason': 'play around fow daze surgical bowmasters'}
    counts_gameable = _count_structural([gameable], deck1='storm')
    assert counts_gameable['meta'] == 0


@pytest.mark.fast
def test_is_meta_predicate_rejects_pass_token():
    # Belt-and-braces: _is_meta predicate rejects bare 'pass'.
    assert _is_meta('pass') is False


@pytest.mark.fast
def test_is_meta_predicate_accepts_meta_play_around_token():
    # Belt-and-braces: _is_meta predicate accepts the typed meta_play_around_* token.
    assert _is_meta('meta_play_around_fow') is True


@pytest.mark.fast
def test_meta_decision_grader_imports_resolve():
    # Corresponds to the L4867 except-block sentinel: the symbols used by this
    # slice must import without raising. Reaching this assertion proves it.
    assert MetaDecision is not None
    assert _count_structural is not None
    assert _grade_meta is not None
    assert _is_meta is not None
