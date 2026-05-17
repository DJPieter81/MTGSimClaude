"""Combat damage / summoning sickness / typed CombatDecision tests.

Migrated from sim.py:run_rules_tests() lines 1966-4689.

Mechanic coverage:
- CR 302.1 — summoning sickness blocks a creature from attacking until it has
  been controlled continuously since the start of its controller's most recent
  turn (haste short-circuits this rule).
- Tap-attacker: an attacker, once declared, is tapped (CR 508.1f) and cannot be
  re-declared this combat (CR 508.1a "untapped creatures").
- CR 510.2 — damage marked on a permanent persists until the end of the turn
  cleanup step. Lethal damage (>= toughness) destroys a creature via SBAs.
- structural_grader / typed Decision algebra: CombatDecision.to_token()
  byte-equality and bucketing of attack/block/hold into counts['combat'].
- Deck-class derivation: COMBO / INTERACTION / AGGRO frozensets surface their
  canonical members from deck_registry + built-in floor.
- Calibration wiring: K_* constants on structural_grader match
  _load_calibrated() defaults for the four STRUCT_K_* keys.
"""
from __future__ import annotations

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

from rules import (  # noqa: E402
    Card,
    CardType,
    MTGRules,
    Permanent,
)


# ── Module-level fixtures: shared creature permanents ────────────────────


def _mk_creature(name: str, cmc: int, power: int, toughness: int) -> Permanent:
    """Build a minimal creature Permanent with the given P/T."""
    c = Card(
        name=name,
        card_type=CardType.CREATURE,
        cmc=cmc,
        mana_cost={},
        colors=set(),
        base_power=power,
        base_toughness=toughness,
        gy_type='creature',
    )
    return Permanent(card=c, controller='o', summoning_sick=False)


@pytest.fixture
def sick_creature() -> Permanent:
    """A vanilla 2/2 with summoning sickness still set."""
    p = _mk_creature("Sick", 2, 2, 2)  # abstraction-allow: rules-test
    p.summoning_sick = True
    return p


@pytest.fixture
def haste_creature() -> Permanent:
    """A 2/2 with haste — should bypass summoning sickness."""
    haste_card = Card(
        name="Haste",  # abstraction-allow: rules-test
        card_type=CardType.CREATURE,
        cmc=2,
        mana_cost={},
        colors=set(),
        base_power=2,
        base_toughness=2,
        haste=True,
        gy_type='creature',
    )
    return Permanent(card=haste_card, controller='b', summoning_sick=True)


# ── CR 302.1: summoning sickness ──────────────────────────────────────────


@pytest.mark.fast
def test_cr_302_1_summoning_sick_creature_cannot_attack(sick_creature):
    """L1966: a creature that has summoning sickness cannot be declared as an attacker."""
    assert MTGRules.can_attack(sick_creature) is False


@pytest.mark.fast
def test_cr_302_1_haste_ignores_summoning_sickness(haste_creature):
    """L1967: haste lets a creature attack even on the turn it enters the battlefield."""
    assert MTGRules.can_attack(haste_creature) is True


@pytest.mark.fast
def test_cr_302_1_cleared_sickness_allows_attack(sick_creature):
    """L1969: once summoning sickness clears (start of controller's untap), the creature can attack."""
    sick_creature.summoning_sick = False
    assert MTGRules.can_attack(sick_creature) is True


# ── CR 508.1f: declared attacker is tapped ────────────────────────────────


@pytest.mark.fast
def test_cr_508_1f_tap_attacker_taps_the_creature(sick_creature):
    """L1972: tap_attacker() actually flips Permanent.tapped to True."""
    sick_creature.summoning_sick = False
    MTGRules.tap_attacker(sick_creature)
    assert sick_creature.tapped is True


@pytest.mark.fast
def test_cr_508_1a_tapped_creature_cannot_be_declared_attacker(sick_creature):
    """L1973: an already-tapped creature is an illegal attacker on a fresh declaration."""
    sick_creature.summoning_sick = False
    MTGRules.tap_attacker(sick_creature)
    assert MTGRules.can_attack(sick_creature) is False


# ── CR 510.2: marked damage persists until cleanup; lethal kills via SBA ──


@pytest.mark.fast
def test_cr_510_2_lethal_marked_damage_destroys_creature():
    """L2192: a 0/3 with 3 marked damage is destroyed by state-based actions (CR 704.5g)."""
    from cards import make_bug_deck, make_dimir_deck
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )
    tamiyo_c = Card(
        name='Tamiyo, Inquisitive Student',  # abstraction-allow: rules-test
        card_type=CardType.CREATURE,
        cmc=1,
        mana_cost={},
        colors={'U'},
        base_power=0,
        base_toughness=3,
        tag='tamiyo',
        gy_type='creature',
    )
    tam_perm = Permanent(card=tamiyo_c, controller='o')
    tam_perm.power_mod = 0
    tam_perm.toughness_mod = 0
    gs.p2.creatures = [tam_perm]
    tam_perm.damage_marked = 3  # lethal: damage >= toughness
    gs.state_based_actions()
    assert len(gs.p2.creatures) == 0


# ── structural_grader: aggro-win + remove token lifts combat axis ────────


@pytest.mark.fast
def test_aggro_win_with_remove_token_grades_combat_a():
    """L4029: aggro deck win + 1 remove_ token (no attack token) still reaches A on combat axis.

    Mechanic: a removal spell that clears a blocker IS a combat-enabling decision, so
    `_grade_combat` credits it on the combat tally.
    """
    import structural_grader as sg
    trace = {
        'deck1': 'burn', 'deck2': 'bug', 'winner': 'p1',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 2, 'deck': 'burn', 'chosen': 'remove_bowm_with_bolt',
             'candidates': [], 'reason': ''},
        ],
    }
    counts = sg._count_structural(trace['strategic_decisions'], deck1='burn')
    grade, _ = sg._grade_combat(trace, counts)
    assert grade == 'A'


# ── structural_grader: K_* constants sourced from calibration JSON ───────


@pytest.mark.fast
def test_calibration_struct_k_inter_a_matches_module_constant():
    """L4143: K_INTER_A is sourced from _load_calibrated('STRUCT_K_INTER_A', 3)."""
    import structural_grader as sg
    from config import _load_calibrated
    assert sg.K_INTER_A == _load_calibrated('STRUCT_K_INTER_A', 3)


@pytest.mark.fast
def test_calibration_struct_k_inter_c_plus_matches_module_constant():
    """L4145: K_INTER_C_PLUS is sourced from _load_calibrated('STRUCT_K_INTER_C_PLUS', 2)."""
    import structural_grader as sg
    from config import _load_calibrated
    assert sg.K_INTER_C_PLUS == _load_calibrated('STRUCT_K_INTER_C_PLUS', 2)


@pytest.mark.fast
def test_calibration_struct_k_combo_game_len_a_matches_module_constant():
    """L4147: K_COMBO_GAME_LEN_A is sourced from _load_calibrated('STRUCT_K_COMBO_GAME_LEN_A', 4)."""
    import structural_grader as sg
    from config import _load_calibrated
    assert sg.K_COMBO_GAME_LEN_A == _load_calibrated('STRUCT_K_COMBO_GAME_LEN_A', 4)


@pytest.mark.fast
def test_calibration_struct_k_mana_game_len_b_matches_module_constant():
    """L4149: K_MANA_GAME_LEN_B is sourced from _load_calibrated('STRUCT_K_MANA_GAME_LEN_B', 8)."""
    import structural_grader as sg
    from config import _load_calibrated
    assert sg.K_MANA_GAME_LEN_B == _load_calibrated('STRUCT_K_MANA_GAME_LEN_B', 8)


# ── Deck-class derivation: bucket membership pins ─────────────────────────


@pytest.mark.fast
def test_deck_class_combo_includes_canonical_members():
    """L4238: COMBO_DECKS contains storm, depths, reanimator (Execute-emitting archetypes)."""
    import structural_grader as sg
    assert {'storm', 'depths', 'reanimator'}.issubset(sg.COMBO_DECKS)


@pytest.mark.fast
def test_deck_class_interaction_includes_canonical_members():
    """L4242: INTERACTION_DECKS contains bug, dimir, ur_delver (disruption archetypes)."""
    import structural_grader as sg
    assert {'bug', 'dimir', 'ur_delver'}.issubset(sg.INTERACTION_DECKS)


@pytest.mark.fast
def test_deck_class_aggro_includes_canonical_members():
    """L4246: AGGRO_DECKS contains burn, goblins, boros (pressure-via-combat archetypes)."""
    import structural_grader as sg
    assert {'burn', 'goblins', 'boros'}.issubset(sg.AGGRO_DECKS)


# ── Typed CombatDecision: to_token() byte-equality + bucketing ────────────


@pytest.mark.fast
def test_combat_decision_attack_to_token_format():
    """L4358: CombatDecision(attack, 2, 'goblins').to_token() == 'attack with 2 goblins'."""
    from decision import CombatDecision
    cb = CombatDecision(
        turn=3, deck='goblins', phase='combat',
        kind='attack', attacker_count=2, attacker_tag='goblins',
    )
    assert cb.to_token() == 'attack with 2 goblins'


@pytest.mark.fast
def test_typed_combat_decision_attack_buckets_into_combat():
    """L4421: a typed CombatDecision(attack) raises counts['combat'] to 1 via isinstance fast-path."""
    import structural_grader as sg
    from decision import CombatDecision
    typed = [
        CombatDecision(
            turn=3, deck='goblins', phase='combat',
            kind='attack', attacker_count=2, attacker_tag='goblins',
        ),
    ]
    counts = sg._count_structural(typed, deck1='goblins')
    assert counts['combat'] == 1


@pytest.mark.fast
def test_combat_decision_block_to_token_format():
    """L4655: CombatDecision(block, 'murktide').to_token() == 'block_murktide'."""
    from decision import CombatDecision
    cb = CombatDecision(
        turn=3, deck='bug', kind='block',
        attacker_count=1, attacker_tag='murktide',  # abstraction-allow: rules-test
    )
    assert cb.to_token() == 'block_murktide'


@pytest.mark.fast
def test_combat_decision_hold_to_token_format():
    """L4663: CombatDecision(hold, 'ragavan').to_token() == 'hold_ragavan'.

    Same prefix as ComboDecision(hold); they're disambiguated downstream by `phase`
    (combat-axis hold carries phase='combat').
    """
    from decision import CombatDecision
    cb = CombatDecision(
        turn=2, deck='ur_delver', kind='hold',
        attacker_count=1, attacker_tag='ragavan',  # abstraction-allow: rules-test
    )
    assert cb.to_token() == 'hold_ragavan'


@pytest.mark.fast
def test_typed_combat_decision_block_buckets_into_combat():
    """L4676: a typed CombatDecision(block) increments counts['combat'] to 1.

    Verifies the isinstance fast-path treats block / hold / attack identically —
    any CombatDecision counts on the combat axis.
    """
    import structural_grader as sg
    from decision import CombatDecision
    typed = [
        CombatDecision(
            turn=3, deck='bug', phase='combat',
            kind='block', attacker_count=1, attacker_tag='murktide',  # abstraction-allow: rules-test
        ),
    ]
    counts = sg._count_structural(typed, deck1='bug')
    assert counts['combat'] == 1


@pytest.mark.fast
def test_typed_combat_decision_mix_block_hold_attack_buckets_into_combat():
    """L4689: a mixed typed list of block + hold + attack raises counts['combat'] to 3."""
    import structural_grader as sg
    from decision import CombatDecision
    typed = [
        CombatDecision(turn=2, deck='bug', phase='combat', kind='hold',
                       attacker_count=1, attacker_tag='murktide'),  # abstraction-allow: rules-test
        CombatDecision(turn=3, deck='bug', phase='combat', kind='block',
                       attacker_count=1, attacker_tag='goyf'),  # abstraction-allow: rules-test
        CombatDecision(turn=4, deck='bug', phase='combat', kind='attack',
                       attacker_count=2, attacker_tag='creatures'),
    ]
    counts = sg._count_structural(typed, deck1='bug')
    assert counts['combat'] == 3
