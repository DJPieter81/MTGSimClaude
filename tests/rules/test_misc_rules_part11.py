"""Migrated rules tests for ticket misc_rules_part11.

Source: sim.py:run_rules_tests() lines 3842-4039.
Covers the structural grader's typed-token discrimination, deck1 filtering,
gameability-resistance and grade-rollup contracts.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the scripts/ dir importable so we can hit structural_grader directly.
_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import structural_grader as _sg  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures (module scope — these are read-only synthetic decision lists)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adversarial_counts():
    """English-prose `reason` containing structural-grader keywords must NOT
    raise structural counts. The grader keys on chosen tokens, not prose."""
    decisions = [
        {'turn': 1, 'phase': None, 'chosen': 'pass',
         'reason': 'protect combo counter attack force tendrils'},
        {'turn': 2, 'phase': None, 'chosen': 'pass',
         'reason': 'storm kill combo win damage'},
    ]
    return _sg._count_structural(decisions)


@pytest.fixture(scope="module")
def cross_deck_counts():
    """deck1 filter must scope counts to that deck's own decisions."""
    decisions = [
        {'turn': 1, 'deck': 'storm', 'chosen': 'discard_fow_with_ts'},
        {'turn': 2, 'deck': 'bug', 'chosen': 'counter_lightning_bolt_with_fow'},
    ]
    return {
        'bug': _sg._count_structural(decisions, deck1='bug'),
        'storm': _sg._count_structural(decisions, deck1='storm'),
        'all': _sg._count_structural(decisions),
    }


# ---------------------------------------------------------------------------
# Tests — one assertion per function, named by mechanic, not by card.
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_combat_decision_recognized_by_attack_chosen_prefix():
    # L3842
    assert _sg._is_combat_decision(
        {'phase': None, 'chosen': 'attack with 2 goblins'}  # abstraction-allow: rules-test
    ) is True


@pytest.mark.fast
def test_combat_decision_requires_phase_or_attack_prefix():
    # L3845
    assert _sg._is_combat_decision({'phase': None, 'chosen': 'pass'}) is False


@pytest.mark.fast
def test_adversarial_reason_does_not_raise_execute_count(adversarial_counts):
    # L3860
    assert adversarial_counts['execute'] == 0


@pytest.mark.fast
def test_adversarial_reason_does_not_raise_hold_count(adversarial_counts):
    # L3862
    assert adversarial_counts['hold'] == 0


@pytest.mark.fast
def test_adversarial_reason_does_not_raise_combat_count(adversarial_counts):
    # L3864
    assert adversarial_counts['combat'] == 0


@pytest.mark.fast
def test_deck1_filter_includes_own_counter_token(cross_deck_counts):
    # L3876
    assert cross_deck_counts['bug']['counter'] == 1


@pytest.mark.fast
def test_deck1_filter_excludes_opponent_discard_token(cross_deck_counts):
    # L3878
    assert cross_deck_counts['bug']['discard'] == 0


@pytest.mark.fast
def test_deck1_filter_includes_own_discard_token(cross_deck_counts):
    # L3880
    assert cross_deck_counts['storm']['discard'] == 1


@pytest.mark.fast
def test_deck1_filter_excludes_opponent_counter_token(cross_deck_counts):
    # L3882
    assert cross_deck_counts['storm']['counter'] == 0


@pytest.mark.fast
def test_no_deck1_filter_counts_every_token(cross_deck_counts):
    # L3886
    all_counts = cross_deck_counts['all']
    assert all_counts['counter'] + all_counts['discard'] == 2


@pytest.mark.fast
def test_execute_token_plus_fast_combo_win_lifts_combo_grade_to_a():
    # L3905
    trace = {
        'deck1': 'storm', 'deck2': 'dnt', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': 'setup', 'chosen': 'kill_C',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'combo:tendrils',
             'candidates': [], 'reason': ''},
        ],
    }
    grade, _ = _sg._grade_combo(
        trace, _sg._count_structural(trace['strategic_decisions'])
    )
    assert grade in ('A', 'A+')


@pytest.mark.fast
def test_combo_deck_with_no_execute_token_caps_combo_grade_at_c():
    # L3922
    trace = {
        'deck1': 'storm', 'deck2': 'burn', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': None, 'chosen': 'pass',
             'candidates': [], 'reason': 'storm kill combo'},
        ],
    }
    grade, _ = _sg._grade_combo(
        trace, _sg._count_structural(trace['strategic_decisions'])
    )
    assert grade == 'C'


@pytest.mark.fast
def test_hold_token_plus_combo_win_lifts_interaction_grade_to_b_plus():
    # L3941
    trace = {
        'deck1': 'storm', 'deck2': 'bug', 'winner': 'p1',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': 'setup', 'chosen': 'hold_fow',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'combo:tendrils',
             'candidates': [], 'reason': ''},
        ],
    }
    counts = _sg._count_structural(trace['strategic_decisions'])
    grade, _ = _sg._grade_interaction(trace, counts)
    assert grade == 'B+'


@pytest.mark.fast
def test_three_removal_tokens_for_interaction_deck_lifts_grade_to_a():
    # L4011
    trace = {
        'deck1': 'bug', 'deck2': 'goblins', 'winner': 'p1',
        'game_length': 8, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 2, 'deck': 'bug', 'chosen': 'remove_lackey_with_push',
             'candidates': [], 'reason': ''},
            {'turn': 3, 'deck': 'bug', 'chosen': 'remove_warchief_with_snuff',
             'candidates': [], 'reason': ''},
            {'turn': 4, 'deck': 'bug', 'chosen': 'remove_matron_with_push',
             'candidates': [], 'reason': ''},
        ],
    }
    counts = _sg._count_structural(trace['strategic_decisions'], deck1='bug')
    grade, _ = _sg._grade_interaction(trace, counts)
    assert grade == 'A'


@pytest.mark.fast
def test_adversarial_remove_in_reason_does_not_raise_removal_count():
    # L4039
    decisions = [
        {'turn': 1, 'deck': 'bug', 'chosen': 'pass',
         'candidates': [], 'reason': 'remove kill destroy push snuff'},
    ]
    counts = _sg._count_structural(decisions, deck1='bug')
    assert counts['removal'] == 0
