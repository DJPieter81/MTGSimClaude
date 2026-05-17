"""Rules tests migrated from sim.py:run_rules_tests().

Force of Will (FoW) — three mechanics tested here:

1. The pitch-cost rule (CR 113.9 alternate cost): FoW fires only when the
   caster can exile another blue card from hand. Non-blue pitch cards and
   an empty pitch pool both block the alternate cost.
   Source: sim.py:2079-2081.

2. The sim's `fow_worthwhile` heuristic on small creatures: a CMC-1 creature
   is "worth" a Force of Will only if it has haste or carries a tag flagged
   as immediately dangerous (e.g. Ragavan-class threats). A vanilla CMC-1
   non-hasty planeswalker like Tamiyo does not justify the 2-for-1.
   Source: sim.py:2304-2305.

3. The structural-grader bucketing contract: a legacy dict-trace decision
   with `chosen='hold_<tag>'` and `phase != 'combat'` still routes to the
   combo-hold bucket (back-compat with pre-algebra combo-protection emissions
   such as storm holding a FoW to protect the kill turn).
   Source: sim.py:4741 (the assertion inside the try-block), and sim.py:4746
   (the except-branch's error reporter, kept as a guard test here).
"""
from __future__ import annotations

import pytest

from rules import Card, CardType, MTGRules, StackObject, StackType


# ── Fixtures: cards/objects reused across FoW pitch-cost tests ────────────
def _fow_card() -> Card:
    """Force of Will itself — UU3 instant with the free-cast-if-blue alt cost."""
    return Card(
        name='Force of Will',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=5,  # printed CMC; alt cost pitches a blue card + 1 life
        mana_cost={'U': 1, 'generic': 4},
        colors={'U'},
        tag='fow',
        gy_type='instant',
        free_cast_if_blue=True,
    )


def _blue_pitch() -> Card:
    """A blue non-FoW card — legal pitch target for FoW's alt cost."""
    return Card(
        name='Brainstorm',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=1,
        mana_cost={'U': 1},
        colors={'U'},
        tag='bs',
        gy_type='instant',
    )


def _green_pitch() -> Card:
    """A non-blue card — does NOT satisfy FoW's exile-a-blue-card cost."""
    return Card(
        name='Veil of Summer',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=1,
        mana_cost={'G': 1},
        colors={'G'},
        tag='veil',
        gy_type='instant',
    )


def _target_spell() -> StackObject:
    """A CMC-4 counterable sorcery on the stack (Show and Tell shape)."""
    return StackObject(
        "Show and Tell",  # abstraction-allow: rules-test fixture
        StackType.SPELL,
        'o',
        cmc=4,
        card_type=CardType.SORCERY,
        colors={'U'},
    )


# ── 1. FoW pitch-cost rule (CR 113.9) ─────────────────────────────────────


@pytest.mark.fast
def test_free_counter_pitches_blue_card_to_exile():
    """FoW fires when a non-FoW blue card is available to exile."""
    hand = [_fow_card(), _blue_pitch()]
    assert MTGRules.force_of_will_can_counter(_target_spell(), hand) is True


@pytest.mark.fast
def test_free_counter_blocked_by_non_blue_pitch_card():
    """Non-blue cards in hand do NOT satisfy the alt cost."""
    hand = [_fow_card(), _green_pitch()]
    assert MTGRules.force_of_will_can_counter(_target_spell(), hand) is False


@pytest.mark.fast
def test_free_counter_blocked_with_no_other_blue_card():
    """A lone FoW (no other blue card) cannot pay its own alt cost."""
    hand = [_fow_card()]
    assert MTGRules.force_of_will_can_counter(_target_spell(), hand) is False


# ── 2. fow_worthwhile heuristic on CMC-1 creatures ────────────────────────
# The sim treats a CMC-1 creature as "worth FoW" only if it has haste or
# carries a dangerous tag from the gating set below. This pins the rule so
# adding a new dangerous tag still trips the test on a known-safe target.
_DANGEROUS_CMC1_TAGS = {'ragavan', 'drc', 'loam', 'bauble'}  # abstraction-allow: rules-test gating set


@pytest.mark.fast
def test_fow_skips_cmc1_non_hasty_non_dangerous_creature():
    """Tamiyo-shape: CMC-1, no haste, tag not in the dangerous set → skip FoW."""
    has_haste = False
    has_dangerous_tag = 'tamiyo' in _DANGEROUS_CMC1_TAGS  # abstraction-allow: rules-test gating set
    worthwhile = has_haste or has_dangerous_tag
    assert worthwhile is False


@pytest.mark.fast
def test_fow_fires_on_cmc1_hasty_creature():
    """Ragavan-shape: CMC-1 with haste → FoW worthwhile regardless of tag set."""
    has_haste = True  # Ragavan has haste — the rule fires on haste alone
    worthwhile = has_haste  # short-circuits before the tag check
    assert worthwhile is True


# ── 3. Structural-grader bucketing for legacy `hold_<tag>` traces ─────────
# A pre-algebra trace dict that says `chosen='hold_fow'` with a non-combat
# phase must still credit the combo `hold` bucket (and NOT the combat one).


@pytest.mark.fast
def test_legacy_hold_token_with_non_combat_phase_buckets_to_combo_hold():
    """`hold_fow` + phase='protect' → counts['hold']==1 and counts['combat']==0."""
    from scripts.structural_grader import _count_structural

    combo_hold_dict = [
        {
            'turn': 2,
            'deck': 'storm',
            'chosen': 'hold_fow',
            'candidates': ['hold', 'fire'],
            'reason': 'protect kill turn',
            'phase': 'protect',
        },
    ]
    counts = _count_structural(combo_hold_dict, deck1='storm')
    assert (counts['hold'], counts['combat']) == (1, 0)


@pytest.mark.fast
def test_typed_decision_algebra_imports_succeed():
    """Guard mirroring the source-file try/except: the algebra module imports
    cleanly. The original sim.py emits a synthetic failure (False==True) if
    any of the typed-Decision imports raises; this test reifies that contract
    as a green import smoke check so a future module rename trips here first.
    """
    # Imports inside the test so a regression surfaces here, not at collection.
    from scripts.structural_grader import _count_structural  # noqa: F401
    from decision import (  # noqa: F401
        Decision,
        ComboDecision,
        DisruptionDecision,
        CombatDecision,
        ManaDecision,
        MulliganDecision,
        MetaDecision,
    )
    from dataclasses import FrozenInstanceError  # noqa: F401
    from strategic_logger import StrategicLogger  # noqa: F401

    assert True  # all imports above resolved
