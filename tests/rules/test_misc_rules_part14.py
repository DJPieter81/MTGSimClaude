"""Rules tests migrated from sim.py:run_rules_tests() lines 4397-4566.

Decision algebra (typed Decision dataclass) + structural-grader bucketing
invariants. Each test pins one assertion on the typed/dict bucketing path
in `structural_grader._count_structural` or on the `to_token()` byte-string
contract for `DisruptionDecision`/`ManaDecision`.

Headers covered (mechanic-named):
- Rule A9 fast-path: typed `remove`/`counter` bucket into removal/counter.
- Rule A10:           typed combo bucket to execute/hold/defer/tried_combo.
- Rule A12:           frozen Decision rejects attribute assignment.
- Rule A13:           mixed typed+dict list yields identical bucketing.
- Rule A14:           deck1 filter on typed path mirrors dict path.
- Rule A15:           extract → discard, land_destroy → removal kind map.
- Rule A16:           legacy trace-JSON dict path buckets identically.
- Rule A17:           land_destroy / extract to_token() byte-equality.
- Rule A18:           legacy dict-token (land_destroy_*, extract_*) prefix.
- Rule M1:            ManaDecision(ramp).to_token() == 'mana_ramp_<N>'.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make repo-root and scripts/ importable (mirrors sim.run_rules_tests setup).
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SCRIPTS = _ROOT / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import structural_grader as _sg  # noqa: E402
from dataclasses import FrozenInstanceError  # noqa: E402
from decision import (  # noqa: E402
    ComboDecision,
    CombatDecision,
    DisruptionDecision,
    ManaDecision,
)


# ── Module-level fixtures: typed Decision lists used by multiple tests. ──

@pytest.fixture(scope='module')
def typed_remove_counter_counts():
    """Rule A9: typed remove+counter list bucketed by deck1='bug'."""
    typed = [
        DisruptionDecision(turn=2, deck='bug', kind='remove',
                           target_tag='goyf', instrument_tag='push'),
        DisruptionDecision(turn=3, deck='bug', kind='counter',
                           target_tag='ts', instrument_tag='fow'),
    ]
    return _sg._count_structural(typed, deck1='bug')


@pytest.fixture(scope='module')
def typed_combo_counts():
    """Rule A10: typed combo execute/hold/defer/tried bucketed."""
    typed = [
        ComboDecision(turn=1, deck='storm', kind='execute', path_tag='storm'),
        ComboDecision(turn=2, deck='storm', kind='hold', piece_tag='fow'),
        ComboDecision(turn=3, deck='storm', kind='defer'),
        ComboDecision(turn=4, deck='storm', kind='tried', piece_tag='darkrit'),
    ]
    return _sg._count_structural(typed, deck1='storm')


@pytest.fixture(scope='module')
def mixed_typed_dict_counts():
    """Rule A13: one typed Decision + one dict; deck1='bug'."""
    mixed = [
        DisruptionDecision(turn=2, deck='bug', kind='remove',
                           target_tag='goyf', instrument_tag='push'),
        {'turn': 3, 'deck': 'bug', 'chosen': 'counter_ts_with_fow',
         'candidates': [], 'reason': '', 'phase': None},
    ]
    return _sg._count_structural(mixed, deck1='bug')


@pytest.fixture(scope='module')
def typed_xdeck_bug_counts():
    """Rule A14: typed list with both decks, filtered to deck1='bug'."""
    typed = [
        DisruptionDecision(turn=1, deck='storm', kind='discard',
                           target_tag='fow', instrument_tag='ts'),
        DisruptionDecision(turn=2, deck='bug', kind='counter',
                           target_tag='lightning_bolt',  # abstraction-allow: rules-test
                           instrument_tag='fow'),
    ]
    return _sg._count_structural(typed, deck1='bug')


@pytest.fixture(scope='module')
def typed_new_kinds_counts():
    """Rule A15: typed extract + land_destroy kinds, deck1='bug'."""
    typed = [
        DisruptionDecision(turn=1, deck='bug', kind='extract',
                           target_tag='fow', instrument_tag='surgical'),
        DisruptionDecision(turn=2, deck='bug', kind='land_destroy',
                           target_tag='depths', instrument_tag='wasteland'),
    ]
    return _sg._count_structural(typed, deck1='bug')


@pytest.fixture(scope='module')
def legacy_xdeck_counts():
    """Rule A16: pre-algebra dict-shaped decisions, both deck1 filters."""
    legacy = [
        {'turn': 1, 'deck': 'storm', 'chosen': 'discard_fow_with_ts'},
        {'turn': 2, 'deck': 'bug',
         'chosen': 'counter_lightning_bolt_with_fow'},  # abstraction-allow: rules-test
    ]
    return {
        'bug': _sg._count_structural(legacy, deck1='bug'),
        'storm': _sg._count_structural(legacy, deck1='storm'),
    }


@pytest.fixture(scope='module')
def legacy_new_kinds_counts():
    """Rule A18: legacy dict tokens for land_destroy / extract."""
    legacy = [
        {'turn': 2, 'deck': 'bug',
         'chosen': 'land_destroy_dual_with_wasteland'},
        {'turn': 3, 'deck': 'bug',
         'chosen': 'extract_reanimate_with_surgical'},
    ]
    return _sg._count_structural(legacy, deck1='bug')


# ── Rule A9 (slice tails — Rule A9 head was migrated upstream) ───────────

@pytest.mark.fast
def test_typed_remove_decision_buckets_into_removal(typed_remove_counter_counts):
    """L4397: typed DisruptionDecision(remove) → counts['removal']=1."""
    assert typed_remove_counter_counts['removal'] == 1


@pytest.mark.fast
def test_typed_counter_decision_buckets_into_counter(typed_remove_counter_counts):
    """L4399: typed DisruptionDecision(counter) → counts['counter']=1."""
    assert typed_remove_counter_counts['counter'] == 1


# ── Rule A10 — typed ComboDecision buckets ────────────────────────────────

@pytest.mark.fast
def test_typed_combo_decisions_bucket_execute_hold_defer_tried(typed_combo_counts):
    """L4410: typed combo execute/hold/defer/tried each bump their bucket."""
    assert (
        typed_combo_counts['execute'],
        typed_combo_counts['hold'],
        typed_combo_counts['defer'],
        typed_combo_counts['tried_combo'],
    ) == (1, 1, 1, 1)


# ── Rule A12 — frozen-dataclass immutability ──────────────────────────────

@pytest.mark.fast
def test_decision_dataclass_is_frozen_against_field_mutation():
    """L4433: assigning to a Decision field raises FrozenInstanceError."""
    froz = DisruptionDecision(turn=2, deck='bug', kind='counter',
                              target_tag='ts', instrument_tag='fow')
    with pytest.raises(FrozenInstanceError):
        froz.turn = 99  # type: ignore[misc]


# ── Rule A13 — mixed typed + dict list back-compat ────────────────────────

@pytest.mark.fast
def test_mixed_typed_and_dict_list_buckets_identically(mixed_typed_dict_counts):
    """L4446: mixed list yields (removal=1, counter=1)."""
    assert (
        mixed_typed_dict_counts['removal'],
        mixed_typed_dict_counts['counter'],
    ) == (1, 1)


# ── Rule A14 — typed deck1 filter mirrors dict-path filter ────────────────

@pytest.mark.fast
def test_typed_deck1_filter_excludes_opponent_decisions(typed_xdeck_bug_counts):
    """L4459: deck1='bug' sees own counter but not storm's discard."""
    assert (
        typed_xdeck_bug_counts['counter'],
        typed_xdeck_bug_counts['discard'],
    ) == (1, 0)


# ── Rule A15 — _DISRUPTION_KIND_TO_BUCKET wiring ──────────────────────────

@pytest.mark.fast
def test_extract_kind_buckets_into_discard(typed_new_kinds_counts):
    """L4473: typed kind='extract' increments counts['discard']."""
    assert typed_new_kinds_counts['discard'] == 1


@pytest.mark.fast
def test_land_destroy_kind_buckets_into_removal(typed_new_kinds_counts):
    """L4475: typed kind='land_destroy' increments counts['removal']."""
    assert typed_new_kinds_counts['removal'] == 1


# ── Rule A16 — legacy trace-JSON dict back-compat ─────────────────────────

@pytest.mark.fast
def test_legacy_dict_counter_token_buckets_for_deck1_bug(legacy_xdeck_counts):
    """L4489: legacy dict 'counter_*' for bug → counter=1, discard=0."""
    bug = legacy_xdeck_counts['bug']
    assert (bug['counter'], bug['discard']) == (1, 0)


@pytest.mark.fast
def test_legacy_dict_discard_token_buckets_for_deck1_storm(legacy_xdeck_counts):
    """L4491: legacy dict 'discard_*' for storm → discard=1, counter=0."""
    storm = legacy_xdeck_counts['storm']
    assert (storm['discard'], storm['counter']) == (1, 0)


# ── Rule A17 — to_token() byte-equality for new kinds ─────────────────────

@pytest.mark.fast
def test_disruption_decision_land_destroy_to_token_format():
    """L4501: land_destroy_<target>_with_<instrument> byte-equality."""
    d = DisruptionDecision(turn=2, deck='lands', kind='land_destroy',
                           target_tag='ws', instrument_tag='wasteland')
    assert d.to_token() == 'land_destroy_ws_with_wasteland'


@pytest.mark.fast
def test_disruption_decision_extract_to_token_format():
    """L4505: extract_<target>_with_<instrument> byte-equality."""
    d = DisruptionDecision(turn=3, deck='bug', kind='extract',
                           target_tag='reanimate', instrument_tag='surgical')
    assert d.to_token() == 'extract_reanimate_with_surgical'


# ── Rule A18 — legacy dict-token prefix bucketing ────────────────────────

@pytest.mark.fast
def test_legacy_land_destroy_dict_token_buckets_into_removal(legacy_new_kinds_counts):
    """L4518: legacy 'land_destroy_*' chosen string → counts['removal']."""
    assert legacy_new_kinds_counts['removal'] == 1


@pytest.mark.fast
def test_legacy_extract_dict_token_buckets_into_discard(legacy_new_kinds_counts):
    """L4520: legacy 'extract_*' chosen string → counts['discard']."""
    assert legacy_new_kinds_counts['discard'] == 1


# ── Rule M1 — ManaDecision.to_token() prefix-string contract ──────────────

@pytest.mark.fast
def test_mana_decision_ramp_to_token_format_value_2():
    """L4566: ManaDecision(ramp, mana_value=2).to_token() == 'mana_ramp_2'."""
    md = ManaDecision(turn=1, deck='storm', kind='ramp', mana_value=2)
    assert md.to_token() == 'mana_ramp_2'
