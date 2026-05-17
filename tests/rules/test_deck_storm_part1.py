"""Migrated rules tests for ticket: deck_storm_part1.

Source: sim.py:run_rules_tests() lines 2243-2952
Test count: 15
Headers covered:
- L2243-2245: Opponent-controlled Nethergoyf reads opp graveyard for P/T.
- L2555-2558: ANT (Storm) tier-1 fast-mana density (Petal + LED).
- L2580-2582: TES tier-1 cantrip density (4 Ponder).
- L2590-2593: Belcher tier-1 ritual + cantrip density.
- L2668-2672: Cephalid vs Storm cantrip + step-through smoke test.
- L2949-2952: Doomsday Pile algebra frozen-instance invariant.
"""
from __future__ import annotations

import random

import pytest


# ---------- Shared fixtures for the Nethergoyf graveyard-type tests ----------

@pytest.fixture(scope='module')
def opp_controlled_goyf_with_three_type_gy():
    """Opponent-controlled Nethergoyf with opp GY = land + instant + creature,
    and protagonist GY = sorcery only (1 type). Mirrors sim.py:2222-2242.
    """
    from cards import make_bug_deck, make_dimir_deck, creature as mkc_ng
    from engine import update_goyf
    from game import GameState, PlayerState
    from rules import Card, CardType, Permanent

    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )
    ng_card = mkc_ng(
        'Nethergoyf',  # abstraction-allow: rules-test
        1, {'U': 1}, {'U', 'B'}, 0, 1, tag='nether',
    )
    ng_perm = Permanent(card=ng_card, controller='o')
    ng_perm.power_mod = 0
    ng_perm.toughness_mod = 0
    gs.p2.creatures.append(ng_perm)

    def gy_card(gy_type):
        return Card(name='x', card_type=CardType.INSTANT, cmc=1,
                    mana_cost={}, colors=set(), gy_type=gy_type)

    gs.p2.graveyard = [gy_card('land'), gy_card('instant'), gy_card('creature')]
    # 1 type in protagonist GY — should NOT affect opp's Nethergoyf
    gs.p1.graveyard = [gy_card('sorcery')]
    update_goyf(gs)
    return ng_perm


@pytest.mark.fast
def test_opp_controlled_graveyard_size_creature_uses_opponent_gy_for_power(
    opp_controlled_goyf_with_three_type_gy,
):
    """sim.py:2243 — graveyard-size creature uses controller's GY (3 types → P=3)."""
    assert opp_controlled_goyf_with_three_type_gy.power == 3


@pytest.mark.fast
def test_opp_controlled_graveyard_size_creature_uses_opponent_gy_for_toughness(
    opp_controlled_goyf_with_three_type_gy,
):
    """sim.py:2244 — graveyard-size creature uses controller's GY (3 types → T=4)."""
    assert opp_controlled_goyf_with_three_type_gy.toughness == 4


@pytest.mark.fast
def test_graveyard_size_creature_ignores_other_players_graveyard(
    opp_controlled_goyf_with_three_type_gy,
):
    """sim.py:2245 — opp-controlled creature ignores the protagonist's GY types."""
    # power remains 3 — the BUG-side sorcery type was not counted.
    assert opp_controlled_goyf_with_three_type_gy.power == 3


# ---------- ANT (Storm) tier-1 fast-mana density ----------------------------

@pytest.fixture(scope='module')
def storm_deck_tag_counts():
    from cards import make_storm_deck
    deck = make_storm_deck()
    return {
        'petal': sum(1 for c in deck if c.tag == 'petal'),
        'led': sum(1 for c in deck if c.tag == 'led'),
    }


@pytest.mark.fast
def test_storm_runs_four_lotus_petals(storm_deck_tag_counts):
    """sim.py:2555 — tier-1 ANT runs 4 Lotus Petal for free-mana density."""
    assert storm_deck_tag_counts['petal'] == 4


@pytest.mark.fast
def test_storm_runs_four_lions_eye_diamonds(storm_deck_tag_counts):
    """sim.py:2556 — tier-1 ANT runs 4 Lion's Eye Diamond."""
    assert storm_deck_tag_counts['led'] == 4


@pytest.mark.fast
def test_storm_deck_builder_runs_without_error():
    """sim.py:2558 — make_storm_deck() must import and execute without raising."""
    from cards import make_storm_deck
    deck = make_storm_deck()
    assert deck is not None


# ---------- TES tier-1 cantrip density --------------------------------------

@pytest.mark.fast
def test_tes_runs_four_ponders():
    """sim.py:2580 — tier-1 TES runs the full 4 Brainstorm + 4 Ponder package."""
    from cards import DECKS
    ponder_count = sum(1 for c in DECKS['tes']() if c.tag == 'ponder')
    assert ponder_count == 4


@pytest.mark.fast
def test_tes_deck_builder_runs_without_error():
    """sim.py:2582 — DECKS['tes']() must build without raising."""
    from cards import DECKS
    deck = DECKS['tes']()
    assert deck is not None


# ---------- Belcher tier-1 ritual + cantrip density -------------------------

@pytest.fixture(scope='module')
def belcher_deck_tag_counts():
    from cards import DECKS
    deck = DECKS['belcher']()
    return {
        'tinder': sum(1 for c in deck if c.tag == 'tinder'),
        'probe': sum(1 for c in deck if c.tag == 'probe'),
    }


@pytest.mark.fast
def test_belcher_runs_four_tinder_walls(belcher_deck_tag_counts):
    """sim.py:2590 — tier-1 Belcher runs 4 Tinder Wall (ritual + pitch target)."""
    assert belcher_deck_tag_counts['tinder'] == 4


@pytest.mark.fast
def test_belcher_runs_four_gitaxian_probes(belcher_deck_tag_counts):
    """sim.py:2591 — tier-1 Belcher runs 4 Gitaxian Probe (free cantrip)."""
    assert belcher_deck_tag_counts['probe'] == 4


@pytest.mark.fast
def test_belcher_deck_builder_runs_without_error():
    """sim.py:2593 — DECKS['belcher']() must build without raising."""
    from cards import DECKS
    deck = DECKS['belcher']()
    assert deck is not None


# ---------- Cephalid vs Storm smoke (cantrip + step-through fix) ------------

@pytest.mark.fast
def test_cephalid_vs_storm_fixed_seeds_meets_minimum_wins():
    """sim.py:2668 — Cephalid wins ≥ 3/10 vs Storm at fixed seeds.

    Pre-fix the deck's cantrip handler hand-rolled "draw 1" for Brainstorm and
    Ponder, halving Brainstorm's dig power. Step Through (wizardcycling) was
    also gated on the full 3-mana cast cost instead of the {U} activation.
    Regression bar: ≥ 3/10 wins at these seeds.
    """
    from sim import run_game

    wins = 0
    for seed in [42, 7, 99, 1, 2, 3, 5, 11, 13, 17]:
        random.seed(seed)
        result = run_game('cephalid', 'storm')
        if result.winner == 'p1':
            wins += 1
    assert (wins >= 3) == True, f"got {wins}/10 wins"


@pytest.mark.fast
def test_cephalid_vs_storm_smoke_run_game_does_not_raise():
    """sim.py:2672 — run_game('cephalid', 'storm') must complete without raising."""
    from sim import run_game

    random.seed(42)
    result = run_game('cephalid', 'storm')
    assert result is not None


# ---------- Doomsday Pile algebra frozen-instance invariant -----------------

@pytest.mark.fast
def test_pile_algebra_instance_is_frozen_against_mutation():
    """sim.py:2949 — Pile dataclasses are frozen; field mutation raises.

    The Pile-selection subsystem mirrors combo_engine.combo_plan's typed
    algebra. Each pile is a frozen dataclass: mutating a field must raise
    FrozenInstanceError. This is the structural discipline that prevents the
    shared-preamble class of bugs from recurring at the pile-selection layer.
    """
    from dataclasses import FrozenInstanceError
    from decks.doomsday_piles import LurrusPile

    sample = LurrusPile(
        name='lurrus',
        cards=('petal', 'bs', 'wraith', 'wraith', 'wraith'),
        draws_to_win=3,
        mana_to_execute=2,
        life_floor=4,
    )
    with pytest.raises(FrozenInstanceError):
        sample.name = 'oracle'  # type: ignore[misc]


@pytest.mark.fast
def test_pile_algebra_module_imports_cleanly():
    """sim.py:2952 — decks.doomsday_piles must import without raising."""
    from decks.doomsday_piles import (  # noqa: F401
        LurrusPile,
        OraclePile,
        Pile,
        TendrilsPile,
        WraithPile,
    )
    # Successful import is the assertion the original except-branch guarded.
    assert Pile is not None
