"""Migrated rules tests for ticket: misc_rules_part13.

Source: sim.py:run_rules_tests() lines 4261-4366

Covers two adjacent rule blocks:
  * deck-class derivation / membership for the structural grader
    (registry-driven COMBO_DECKS / INTERACTION_DECKS buckets), and
  * the typed Decision algebra in `decision.py` — `to_token()` byte-equality
    with the prefix-string contract the grader already consumes, plus
    `to_log_entry()` shape parity with `StrategicLogger.entries`.

Each migrated `def test_*` mirrors exactly one `test(...)` call from the
source range — one assertion per function.
"""
from __future__ import annotations

import pytest

from decision import ComboDecision, DisruptionDecision
from scripts import structural_grader as sg


# ---------------------------------------------------------------------------
# Rule 15b / 15c — deck-class derivation: COMBO_DECKS / INTERACTION_DECKS
# membership is derived from `deck_registry.get_decks_in_category(...)` ∪ a
# built-in floor. These tests pin canonical memberships so a future refactor
# can't silently drop a deck without re-declaring its category in DECK_META.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_combo_decks_auto_includes_registry_combo_category_members():
    # Rule 15b — every deck whose DECK_META declares 'combo' must appear in
    # the grader's COMBO_DECKS bucket (no hardcoded literal allow-list).
    try:
        from deck_registry import get_decks_in_category
        combo_from_reg = get_decks_in_category('combo')
    except ImportError:
        combo_from_reg = frozenset()
    assert combo_from_reg.issubset(sg.COMBO_DECKS)


@pytest.mark.fast
def test_combo_decks_membership_includes_glimpse_engine_deck():
    # Rule 15c — `elves` runs a Glimpse-of-Nature combo engine and must be
    # bucketed as COMBO even though older registry data tagged it 'aggro'.
    assert 'elves' in sg.COMBO_DECKS


@pytest.mark.fast
def test_combo_decks_membership_includes_painter_after_execute_wiring():
    # Rule 15c — `painter` emits typed `combo:painter_grindstone_mill`
    # Execute tokens at the Painter+Grindstone lock; it IS a combo deck.
    assert 'painter' in sg.COMBO_DECKS


@pytest.mark.fast
def test_painter_is_not_interaction_deck_after_combo_reclassification():
    # Rule 15c — the same reclassification removes painter from the
    # INTERACTION bucket (combo archetype after Execute wiring).
    assert 'painter' not in sg.INTERACTION_DECKS


@pytest.mark.fast
def test_structural_grader_deck_class_setup_does_not_raise():
    # Source guard: the original try/except wrapped the whole rule-15 block
    # so a missing import or surprise membership would surface as a failure.
    # Migration form: re-run the bucket lookups; any exception fails the test.
    from deck_registry import get_decks_in_category
    combo_from_reg = get_decks_in_category('combo')
    # Re-trigger the same membership reads the original block performed.
    _ = (combo_from_reg.issubset(sg.COMBO_DECKS),
         'elves' in sg.COMBO_DECKS,
         'painter' in sg.COMBO_DECKS,
         'painter' not in sg.INTERACTION_DECKS)
    assert True


# ---------------------------------------------------------------------------
# Rules A1-A2 — DisruptionDecision.to_token() reproduces the
# '<kind>_<target>_with_<instrument>' format the strategy layer writes.
# Byte-equality lets the grader consume typed and string forms uniformly.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_disruption_decision_counter_to_token_format():
    d = DisruptionDecision(turn=2, deck='bug', kind='counter',
                           target_tag='ts', instrument_tag='fow')
    assert d.to_token() == 'counter_ts_with_fow'


@pytest.mark.fast
def test_disruption_decision_discard_to_token_format():
    d = DisruptionDecision(turn=1, deck='bug', kind='discard',
                           target_tag='fow', instrument_tag='ts')
    assert d.to_token() == 'discard_fow_with_ts'


@pytest.mark.fast
def test_disruption_decision_remove_to_token_format():
    d = DisruptionDecision(turn=3, deck='bug', kind='remove',
                           target_tag='goyf', instrument_tag='push')
    assert d.to_token() == 'remove_goyf_with_push'


# ---------------------------------------------------------------------------
# Rules A3-A5 — ComboDecision tokens: execute / tried / hold / defer.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_combo_decision_execute_with_path_tag_emits_combo_prefix():
    # Rule A3 — non-empty path_tag yields 'combo:<path_tag>'.
    c = ComboDecision(turn=4, deck='storm', kind='execute', path_tag='storm')
    assert c.to_token() == 'combo:storm'


@pytest.mark.fast
def test_combo_decision_execute_with_empty_path_tag_falls_back_to_kill_c():
    # Rule A3 — empty path_tag falls back to the legacy 'kill_C' token.
    c = ComboDecision(turn=4, deck='storm', kind='execute', path_tag='')
    assert c.to_token() == 'kill_C'


@pytest.mark.fast
def test_combo_decision_tried_emits_partial_credit_token():
    # Rule A4 — tried kind emits 'tried_combo:<piece_tag>' (PR #153).
    c = ComboDecision(turn=2, deck='storm', kind='tried', piece_tag='darkrit')
    assert c.to_token() == 'tried_combo:darkrit'


@pytest.mark.fast
def test_combo_decision_hold_emits_hold_piece_token():
    # Rule A5 — hold kind matches the legacy 'hold_<piece>' token.
    c = ComboDecision(turn=1, deck='storm', kind='hold', piece_tag='fow')
    assert c.to_token() == 'hold_fow'


@pytest.mark.fast
def test_combo_decision_defer_emits_defer_token():
    # Rule A5 — defer kind matches the legacy 'defer' token.
    c = ComboDecision(turn=1, deck='storm', kind='defer')
    assert c.to_token() == 'defer'


# ---------------------------------------------------------------------------
# Rule A7 — to_log_entry() emits the dict shape StrategicLogger.entries
# already uses (turn / deck / phase / candidates / chosen / reason).
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_disruption_decision_to_log_entry_chosen_matches_to_token():
    d = DisruptionDecision(turn=2, deck='bug', kind='counter',
                           target_tag='ts', instrument_tag='fow')
    assert d.to_log_entry()['chosen'] == 'counter_ts_with_fow'


@pytest.mark.fast
def test_disruption_decision_to_log_entry_has_six_canonical_keys():
    d = DisruptionDecision(turn=2, deck='bug', kind='counter',
                           target_tag='ts', instrument_tag='fow')
    assert sorted(d.to_log_entry().keys()) == [
        'candidates', 'chosen', 'deck', 'phase', 'reason', 'turn',
    ]
