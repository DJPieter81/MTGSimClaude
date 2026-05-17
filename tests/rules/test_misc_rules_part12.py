"""Migrated rules tests for ticket: misc_rules_part12.

Source: sim.py:run_rules_tests() lines 4047-4226

Covers the structural_grader's `tried_combo:<tag>` token contract, the
`_count_structural` bucketing of those tokens, the combo-deck grade
promotions / wins they trigger, the calibration-tool wiring for the four
STRUCT_K_* literals, and two anti-gameability invariants on the
interaction / combo grading paths.

Each migrated ``def test_*`` mirrors exactly one ``test(...)`` call from the
source range — one assertion per function.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ is a package via scripts/__init__.py; importing through it is
# the same pattern used in tests/rules/test_misc_rules_part13.py.
from scripts import structural_grader as sg


# ───────────────────────── shared fixtures ─────────────────────────


@pytest.fixture(scope='module')
def grade_to_index():
    """Inverse map of `llm_judge.GRADE_SCALE` — index lookup for ≥-comparisons."""
    from llm_judge import GRADE_SCALE
    return {g: i for i, g in enumerate(GRADE_SCALE)}


@pytest.fixture(scope='module')
def tried_combo_counts():
    """Bucket counts derived from two `tried_combo:<tag>` decisions."""
    decisions = [
        {'turn': 1, 'phase': 'combo', 'chosen': 'tried_combo:storm',
         'candidates': [], 'reason': ''},
        {'turn': 2, 'phase': 'combo', 'chosen': 'tried_combo:darkrit',
         'candidates': [], 'reason': ''},
    ]
    return sg._count_structural(decisions)


@pytest.fixture(scope='module')
def combo_loss_short_grade():
    """`_grade_combo` on a length-5 combo-deck loss with one tried_combo token."""
    trace = {
        'deck1': 'storm', 'deck2': 'dimir', 'winner': 'p2',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': 'combo', 'chosen': 'kill_C',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'tried_combo:darkrit',
             'candidates': [], 'reason': ''},
        ],
    }
    return sg._grade_combo(trace, sg._count_structural(trace['strategic_decisions']))


@pytest.fixture(scope='module')
def combo_loss_long_grade():
    """`_grade_combo` on a length-8 combo-deck loss with two tried_combo tokens."""
    trace = {
        'deck1': 'storm', 'deck2': 'dimir', 'winner': 'p2',
        'game_length': 8, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': 'combo', 'chosen': 'kill_C',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'tried_combo:darkrit',
             'candidates': [], 'reason': ''},
            {'turn': 3, 'phase': 'combo', 'chosen': 'tried_combo:tendrils',
             'candidates': [], 'reason': ''},
        ],
    }
    return sg._grade_combo(trace, sg._count_structural(trace['strategic_decisions']))


@pytest.fixture(scope='module')
def combo_win_with_tried_grade():
    """`_grade_combo` on a combo-deck WIN that also contains a tried_combo token."""
    trace = {
        'deck1': 'storm', 'deck2': 'dnt', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'phase': 'combo', 'chosen': 'tried_combo:darkrit',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'combo:tendrils',
             'candidates': [], 'reason': ''},
            {'turn': 2, 'phase': 'combo', 'chosen': 'kill_C',
             'candidates': [], 'reason': ''},
        ],
    }
    return sg._grade_combo(trace, sg._count_structural(trace['strategic_decisions']))


@pytest.fixture(scope='module')
def calibration_values():
    """Parsed `values` block of `config/calibration.json` (or {} if absent)."""
    repo_root = Path(__file__).resolve().parents[2]
    cal_path = repo_root / 'config' / 'calibration.json'
    if not cal_path.exists():
        return {}
    try:
        with cal_path.open() as f:
            return json.load(f).get('values', {})
    except (OSError, json.JSONDecodeError):
        return {}


@pytest.fixture(scope='module')
def adversarial_interaction_grade(grade_to_index):
    """Interaction grade for a zero-token trace whose `reason` fields are
    saturated with grader keywords — gameability invariant 1."""
    decisions = [
        {'turn': t, 'deck': 'bug', 'phase': None, 'chosen': 'pass',
         'candidates': ['pass'],
         'reason': 'protect combo counter attack force tendrils storm kill'}
        for t in range(1, 6)
    ]
    trace = {
        'deck1': 'bug', 'deck2': 'storm', 'winner': 'p2',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': decisions,
    }
    counts = sg._count_structural(decisions, deck1='bug')
    grade, justification = sg._grade_interaction(trace, counts)
    return {
        'grade': grade,
        'index': grade_to_index.get(grade, 99),
        'justification': justification,
    }


@pytest.fixture(scope='module')
def faked_token_combo_grade(grade_to_index):
    """Combo grade for a non-COMBO deck that emits a fake `kill_C` token —
    gameability invariant 2."""
    trace = {
        'deck1': 'goblins', 'deck2': 'uwx', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'deck': 'goblins', 'phase': 'setup',
             'chosen': 'kill_C', 'candidates': [], 'reason': ''},
        ],
    }
    counts = sg._count_structural(trace['strategic_decisions'], deck1='goblins')
    grade, justification = sg._grade_combo(trace, counts)
    return {
        'grade': grade,
        'index': grade_to_index.get(grade, 99),
        'justification': justification,
    }


# ────── Rule 10: `tried_combo:<tag>` token classifier contract ──────


@pytest.mark.fast
def test_tried_combo_storm_tag_classifies_as_tried_combo_token():
    """`tried_combo:<tag>` is the structured emission for a combo piece
    that left hand without an Execute firing this turn."""
    assert sg._is_tried_combo('tried_combo:storm') is True


@pytest.mark.fast
def test_tried_combo_reanimate_tag_classifies_as_tried_combo_token():
    """The classifier is tag-agnostic — any tag after the prefix qualifies."""
    assert sg._is_tried_combo('tried_combo:reanimate') is True


@pytest.mark.fast
def test_tried_combo_token_is_not_an_execute_token():
    """tried_combo is a partial-credit signal, not a kill-firing Execute."""
    assert sg._is_execute('tried_combo:storm') is False


@pytest.mark.fast
def test_tried_combo_token_is_not_a_hold_token():
    """tried_combo is orthogonal to the Hold axis."""
    assert sg._is_hold('tried_combo:storm') is False


@pytest.mark.fast
def test_tried_combo_token_is_not_a_defer_token():
    """tried_combo is orthogonal to the Defer axis."""
    assert sg._is_defer('tried_combo:storm') is False


@pytest.mark.fast
def test_pass_token_is_not_a_tried_combo_emission():
    """The bare prefix without a tag is not a tried_combo emission — the
    engine's emit site always appends a tag, so `pass` (and friends) fail."""
    assert sg._is_tried_combo('pass') is False


# ─────── Rule 11: `_count_structural` bucketing of tried_combo ──────


@pytest.mark.fast
def test_two_tried_combo_tokens_raise_tried_combo_count_to_two(tried_combo_counts):
    """Two distinct tried_combo emissions surface in counts['tried_combo']."""
    assert tried_combo_counts['tried_combo'] == 2


@pytest.mark.fast
def test_tried_combo_tokens_do_not_raise_execute_count(tried_combo_counts):
    """tried_combo bucketing must not bleed into the execute axis."""
    assert tried_combo_counts['execute'] == 0


@pytest.mark.fast
def test_tried_combo_tokens_do_not_raise_hold_count(tried_combo_counts):
    """tried_combo bucketing must not bleed into the hold axis."""
    assert tried_combo_counts['hold'] == 0


# ───────── Rule 12: combo-loss promotions on the tried_combo axis ─────


@pytest.mark.fast
def test_combo_loss_short_with_tried_combo_promotes_d_to_c_plus(combo_loss_short_grade):
    """A combo-deck loss at length ≤ 5 with n_tried ≥ 1 lifts D to C+
    ("played pieces but disrupted")."""
    grade, _justification = combo_loss_short_grade
    assert grade == 'C+'


# ───────── Rule 13: long-loss tried_combo still off the D floor ───────


@pytest.mark.fast
def test_combo_loss_long_with_tried_combo_lifts_grade_to_c(combo_loss_long_grade):
    """A combo-deck loss at length > 5 with n_tried ≥ 1 still earns C
    instead of dropping to D — the partial-credit signal holds."""
    grade, _justification = combo_loss_long_grade
    assert grade == 'C'


# ───────── Rule 14: combo-deck win unaffected by tried_combo ───────


@pytest.mark.fast
def test_combo_win_with_tried_combo_keeps_top_grade(combo_win_with_tried_grade):
    """Wins continue to grade at A/A+; tried_combo only matters on losses."""
    grade, _justification = combo_win_with_tried_grade
    assert grade in ('A', 'A+')


# ────── Calibration-tool wiring: STRUCT_K_* keys live in JSON ──────


@pytest.mark.fast
@pytest.mark.parametrize('key_name', [
    'STRUCT_K_INTER_A',
    'STRUCT_K_INTER_C_PLUS',
    'STRUCT_K_COMBO_GAME_LEN_A',
    'STRUCT_K_MANA_GAME_LEN_B',
])
def test_calibration_struct_k_key_present_in_calibration_json(
        calibration_values, key_name):
    """If `config/calibration.json` exists, its `values` block must carry
    each STRUCT_K_* key the `--write` tool target writes. Missing file =
    vacuous pass (matches the source's literal-defaults fallback branch).
    Mirrors the for-loop at sim.py:4164-4168 as a single parametrized test
    so the test-function count stays at 15 per ticket contract."""
    if not calibration_values:
        pytest.skip("config/calibration.json absent — vacuous pass per source contract")
    assert key_name in calibration_values


# ─────── Anti-gameability invariant 1: keyword-stuffed reasons ───────


@pytest.mark.fast
def test_adversarial_keyword_reason_does_not_promote_interaction_loss_above_c(
        adversarial_interaction_grade):
    """A zero-token loss whose `reason` fields are saturated with grader
    keywords must still grade ≥ C (idx 5) — i.e. cannot climb above C just
    because English prose contains 'protect', 'counter', etc."""
    grade_c_idx = 5
    assert adversarial_interaction_grade['index'] >= grade_c_idx


# ───────── Anti-gameability invariant 2: faked Execute token ─────────


@pytest.mark.fast
def test_non_combo_deck_with_faked_execute_token_keeps_combo_grade_at_b_floor(
        faked_token_combo_grade):
    """A non-COMBO deck (goblins) that emits a fake `kill_C` token still
    grades at the non-combo branch's B floor — the faked Execute cannot lift
    the grade past it."""
    grade_b_idx = 3
    assert faked_token_combo_grade['index'] >= grade_b_idx
