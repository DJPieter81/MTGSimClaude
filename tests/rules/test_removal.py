"""Migrated from sim.py:run_rules_tests() lines 1937-3990 (21 asserts).

Covers spot-removal rules (Fatal Push CMC + revolt, Abrupt Decay CMC<=3,
Dismember -5/-5 lethality, Swords to Plowshares life-gain = power) plus
the structural-grader removal-token vocabulary (`remove_<target>_with_<spell>`
mirrors the counter_/discard_ pattern and feeds counts['removal']).
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

from rules import Card, CardType, Permanent, MTGRules  # noqa: E402
import structural_grader as _sg  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers (shared setup)
# ---------------------------------------------------------------------------

def _mkc(name: str, cmc: int, power: int, toughness: int) -> Permanent:
    """Make a creature Permanent with the given stats."""
    c = Card(name=name, card_type=CardType.CREATURE, cmc=cmc, mana_cost={},
             colors=set(), base_power=power, base_toughness=toughness,
             gy_type='creature')
    return Permanent(card=c, controller='o', summoning_sick=False)


def _mkperm(name: str, cmc: int) -> Permanent:
    """Make a noncreature artifact Permanent (target for Abrupt Decay)."""
    c = Card(name=name, card_type=CardType.ARTIFACT, cmc=cmc, mana_cost={},
             colors=set(), gy_type='artifact')
    return Permanent(card=c, controller='o')


# ---------------------------------------------------------------------------
# Fatal Push CMC + revolt (CMC<=2 default, CMC<=4 with revolt)
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_fatal_push_hits_cmc1_creature_without_revolt():
    rag = _mkc("Ragavan", 1, 2, 1)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(rag, False) is True


@pytest.mark.fast
def test_fatal_push_hits_cmc2_creature_without_revolt():
    goyf = _mkc("Tarmogoyf", 2, 4, 5)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(goyf, False) is True


@pytest.mark.fast
def test_fatal_push_misses_cmc4_creature_without_revolt():
    tks = _mkc("TKS", 4, 4, 4)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(tks, False) is False


@pytest.mark.fast
def test_fatal_push_hits_cmc4_creature_with_revolt():
    tks = _mkc("TKS", 4, 4, 4)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(tks, True) is True


@pytest.mark.fast
def test_fatal_push_misses_cmc5_creature_even_with_revolt():
    smasher = _mkc("Smasher", 5, 5, 5)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(smasher, True) is False


@pytest.mark.fast
def test_fatal_push_misses_cmc7_creature_even_with_revolt():
    murk = _mkc("Murktide", 7, 8, 8)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(murk, True) is False


@pytest.mark.fast
def test_fatal_push_misses_cmc3_creature_without_revolt():
    borrow = _mkc("Borrower", 3, 3, 1)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(borrow, False) is False


@pytest.mark.fast
def test_fatal_push_hits_cmc3_creature_with_revolt():
    borrow = _mkc("Borrower", 3, 3, 1)  # abstraction-allow: rules-test
    assert MTGRules.fatal_push_valid_target(borrow, True) is True


# ---------------------------------------------------------------------------
# Abrupt Decay — CMC<=3 only, ignores creature-vs-noncreature
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_abrupt_decay_hits_cmc3_permanent():
    assert MTGRules.abrupt_decay_valid_target(_mkperm("Bridge", 3)) is True  # abstraction-allow: rules-test


@pytest.mark.fast
def test_abrupt_decay_misses_cmc4_permanent():
    assert MTGRules.abrupt_decay_valid_target(_mkperm("Karn", 4)) is False  # abstraction-allow: rules-test


@pytest.mark.fast
def test_abrupt_decay_hits_cmc0_permanent():
    assert MTGRules.abrupt_decay_valid_target(_mkperm("Chalice", 0)) is True  # abstraction-allow: rules-test


# ---------------------------------------------------------------------------
# Dismember -5/-5 (kills toughness<=5 creatures)
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_dismember_kills_toughness_4_creature():
    low_t = _mkc("Low", 1, 2, 4)  # abstraction-allow: rules-test
    assert MTGRules.dismember_kills(low_t) is True


@pytest.mark.fast
def test_dismember_does_not_kill_toughness_10_creature():
    high_t = _mkc("High", 1, 2, 10)  # abstraction-allow: rules-test
    assert MTGRules.dismember_kills(high_t) is False


# ---------------------------------------------------------------------------
# Swords to Plowshares — life gain equals creature power
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_stp_life_gain_equals_target_power():
    a_4_4 = _mkc("Goyf", 2, 4, 5)  # abstraction-allow: rules-test
    assert MTGRules.stp_life_gain(a_4_4) == 4


# ---------------------------------------------------------------------------
# Structural-grader removal-token vocabulary
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_remove_prefix_with_push_spell_classified_as_removal():
    assert _sg._is_removal('remove_bowm_with_push') is True


@pytest.mark.fast
def test_remove_prefix_with_stp_spell_classified_as_removal():
    assert _sg._is_removal('remove_creature_with_stp') is True


@pytest.mark.fast
def test_remove_prefix_is_not_a_counter_token():
    assert _sg._is_counter('remove_bowm_with_push') is False


@pytest.mark.fast
def test_remove_prefix_is_not_a_discard_token():
    assert _sg._is_discard('remove_bowm_with_push') is False


@pytest.mark.fast
def test_remove_prefix_is_not_an_execute_token():
    assert _sg._is_execute('remove_bowm_with_push') is False


@pytest.mark.fast
def test_pass_is_not_a_removal_token():
    assert _sg._is_removal('pass') is False


# ---------------------------------------------------------------------------
# count_structural sums remove_ tokens into counts['removal']
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_count_structural_sums_three_remove_tokens_into_removal_axis():
    trace = [
        {'turn': 2, 'deck': 'bug', 'chosen': 'remove_ragavan_with_push',  # abstraction-allow: rules-test
         'candidates': [], 'reason': ''},
        {'turn': 3, 'deck': 'bug', 'chosen': 'remove_goyf_with_snuff',  # abstraction-allow: rules-test
         'candidates': [], 'reason': ''},
        {'turn': 4, 'deck': 'bug', 'chosen': 'remove_murk_with_push',  # abstraction-allow: rules-test
         'candidates': [], 'reason': ''},
    ]
    counts = _sg._count_structural(trace, deck1='bug')
    assert counts['removal'] == 3
