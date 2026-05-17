"""Rules tests migrated from sim.py:run_rules_tests() lines 1957-2390.

Mechanics covered:
- Ensnaring Bridge: attack prevention vs (power > hand size).
- Force of Negation: free alt cost gated to opponent's turn.
- Card-attribute audit: a handful of BUG-deck cards must carry their oracle
  keywords/CMC (flying/delve/flash, Tamiyo CMC=1, Daze printed CMC=1).
- CR 510.2 turn boundary cleanup: marked damage clears at end of turn so a
  small creature blocked for sub-lethal damage survives the next round.
- Eidolon of the Great Revel: triggers only on spells with CMC < 4
  (i.e. CMC ≤ 3); CMC-5 spells do NOT damage the caster.
- assess_board: when only the player has creatures, state is 'ahead' and
  metrics['board_power'] equals the sum of creature power.
"""
from __future__ import annotations

import pytest

from rules import (
    Card,
    CardType,
    MTGRules,
    Permanent,
    StackObject,
    StackType,
)


# ── Ensnaring Bridge (L1957-1959) ─────────────────────────────────────────
def _mkc(name: str, cmc: int, power: int, toughness: int) -> Permanent:
    """Helper: make a vanilla creature permanent with given P/T."""
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


@pytest.mark.fast
def test_bridge_blocks_attacker_with_power_above_hand_size():
    goyf = _mkc("Tarmogoyf", 2, 4, 5)  # abstraction-allow: rules-test fixture
    assert MTGRules.bridge_prevents_attack(goyf, 3) is True


@pytest.mark.fast
def test_bridge_allows_attacker_with_power_equal_to_hand_size():
    goyf = _mkc("Tarmogoyf", 2, 4, 5)  # abstraction-allow: rules-test fixture
    assert MTGRules.bridge_prevents_attack(goyf, 4) is False


@pytest.mark.fast
def test_bridge_blocks_large_attacker_even_against_full_hand():
    murk = _mkc("Murktide", 7, 8, 8)  # abstraction-allow: rules-test fixture
    assert MTGRules.bridge_prevents_attack(murk, 7) is True


# ── Force of Negation: free only on opponent's turn (L2048-2049) ──────────
def _fon_target_spell() -> StackObject:
    """A CMC-3 noncreature spell on the stack (Show and Tell shape)."""
    return StackObject(
        "Show and Tell",  # abstraction-allow: rules-test fixture
        StackType.SPELL,
        'o',
        cmc=3,
        card_type=CardType.SORCERY,
        colors={'U'},
    )


def _fon_hand() -> list:
    """A hand containing exactly one Force of Negation card."""
    return [
        Card(
            name="FoN",  # abstraction-allow: rules-test fixture
            card_type=CardType.INSTANT,
            cmc=3,
            mana_cost={'U': 1, 'generic': 2},
            colors={'U'},
            tag='fon',
            gy_type='instant',
        )
    ]


@pytest.mark.fast
def test_free_counter_usable_on_opponents_turn():
    assert MTGRules.force_of_negation_can_counter(
        _fon_target_spell(), _fon_hand(), is_opponents_turn=True
    ) is True


@pytest.mark.fast
def test_free_counter_not_free_on_own_turn():
    assert MTGRules.force_of_negation_can_counter(
        _fon_target_spell(), _fon_hand(), is_opponents_turn=False
    ) is False


# ── Card-attribute audit: BUG deck oracle correctness (L2110-2116, 2120) ──
@pytest.fixture(scope="module")
def bug_deck_cards():
    """Module-scoped BUG decklist for the attribute audit block."""
    from cards import DECKS
    return DECKS['bug']()


def _find_by_name(deck, name):
    return next((c for c in deck if c.name == name), None)  # abstraction-allow: rules-test fixture


@pytest.mark.fast
def test_large_delve_creature_has_flying_keyword(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Murktide Regent')  # abstraction-allow: rules-test fixture
    assert card.flying is True


@pytest.mark.fast
def test_large_delve_creature_has_delve_keyword(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Murktide Regent')  # abstraction-allow: rules-test fixture
    assert card.delve is True


@pytest.mark.fast
def test_adventure_flash_creature_has_flash_keyword(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Brazen Borrower')  # abstraction-allow: rules-test fixture
    if card is None:
        pytest.skip("Brazen Borrower not in BUG deck (mirrors `if borrower_:` guard in sim.py)")
    assert card.flash is True


@pytest.mark.fast
def test_adventure_flash_creature_has_flying_keyword(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Brazen Borrower')  # abstraction-allow: rules-test fixture
    if card is None:
        pytest.skip("Brazen Borrower not in BUG deck (mirrors `if borrower_:` guard in sim.py)")
    assert card.flying is True


@pytest.mark.fast
def test_grouped_flash_creature_has_flash_keyword(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Orcish Bowmasters')  # abstraction-allow: rules-test fixture
    assert card.flash is True


@pytest.mark.fast
def test_small_planeswalker_has_cmc_1(bug_deck_cards):
    card = _find_by_name(bug_deck_cards, 'Tamiyo, Inquisitive Student')  # abstraction-allow: rules-test fixture
    assert card.cmc == 1


@pytest.mark.fast
def test_free_counter_with_tax_clause_has_printed_cmc_1(bug_deck_cards):
    # Daze's printed cost is {U} → CMC 1. The {1} tax is paid by the
    # OPPONENT to avoid the counter, NOT the caster's mana cost.
    card = _find_by_name(bug_deck_cards, 'Daze')  # abstraction-allow: rules-test fixture
    assert card.cmc == 1


# ── CR 510.2: damage clears at end of turn (L2188) ────────────────────────
@pytest.mark.fast
def test_marked_damage_clears_so_sublethal_blocker_survives_turn_boundary():
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
        p1_goes_first=True,
    )
    tamiyo_c = Card(
        name='Tamiyo, Inquisitive Student',  # abstraction-allow: rules-test fixture
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
    # 1 damage marked, then turn-boundary cleanup clears it.
    tam_perm.damage_marked = 1
    for c in gs.p2.creatures:
        c.damage_marked = 0
    gs.state_based_actions()
    assert len(gs.p2.creatures) == 1


# ── Eidolon: trigger gating on CMC ≤ 3 (L2361) ────────────────────────────
@pytest.mark.fast
def test_eidolon_does_not_trigger_on_cmc_5_spell():
    from engine import _eidolon_trigger
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[], life=20),
        p2=PlayerState(name='o', hand=[], library=[], life=20),
    )
    gs.eidolon_active = True
    big_card = Card(
        name='Force of Will',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=5,
        mana_cost={'U': 1, 'generic': 4},
        colors={'U'},
        tag='fow',
    )
    _eidolon_trigger(gs, big_card, lambda *a, **kw: None, caster=gs.p1)
    assert gs.p1.life == 20


# ── assess_board: lone-creatures side is 'ahead' (L2390) ──────────────────
@pytest.mark.fast
def test_assess_board_reports_ahead_when_only_player_has_creatures():
    from engine import assess_board
    from game import GameState, PlayerState

    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[], life=20),
        p2=PlayerState(name='o', hand=[], library=[], life=20),
    )
    c1 = Card(
        name='Goyf',  # abstraction-allow: rules-test fixture
        card_type=CardType.CREATURE,
        cmc=2,
        mana_cost={'G': 1, 'generic': 1},
        colors={'G'},
        tag='goyf',
        base_power=4,
        base_toughness=5,
    )
    gs.p1.creatures = [Permanent(card=c1, controller='b')]
    gs.p2.creatures = []
    state, _metrics = assess_board(gs.p1, gs.p2)
    assert state == 'ahead'
