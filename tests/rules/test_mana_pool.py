"""Migrated from sim.py:run_rules_tests() lines 2017-3501.

Covers mana-pool / mana-payment mechanics:
- CR 601.2f: a spell may only be cast if its mana cost can be paid (`can_cast`).
- ManaManager: `spend_amount(n)` deducts n from the budget and clamps at 0.
- CR 202.1 (printed mana cost): a deck's card metadata must reflect the printed
  cost; the regression that triggered this slice was a miscoded Doomsday cost
  desyncing the strategy's mana gate from the real card.
- combo_engine `ReanimatePath`: is_satisfiable iff reanimate-tag + enabler-tag +
  at least one target-tag + mana floor are simultaneously present.
- combo_engine `combo_plan`: when mana floor is below the cheapest satisfiable
  path's cost, returns `NoPlan` (no patch can execute under mana starvation).
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Module-level fixtures (shared setup for repeat-use rule probes)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def brainstorm_card():
    """A 1-mana {U} instant — the smallest castable spell."""
    from rules import Card, CardType
    return Card(name="Brainstorm",  # abstraction-allow: rules-test
                card_type=CardType.INSTANT, cmc=1,
                mana_cost={'U': 1}, colors={'U'}, gy_type='instant')


@pytest.fixture
def empty_pool():
    from rules import ManaPool
    return ManaPool()


@pytest.fixture
def one_u_pool():
    from rules import ManaPool
    pool = ManaPool()
    pool.add('U')
    return pool


@pytest.fixture
def mana_manager():
    """A ManaManager started with 5 mana, no tax effects active."""
    from engine import ManaManager
    from game import GameState, PlayerState
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
    )
    gs.trinisphere_active = False
    gs.thalia_on_board = False
    gs.eidolon_active = False
    return ManaManager(5, gs)


@pytest.fixture
def doomsday_card():
    """The printed Doomsday card from the registered deck builder."""
    from cards import make_doomsday_deck
    return next(c for c in make_doomsday_deck() if c.tag == 'dd')


@pytest.fixture
def reanimate_path():
    """A ReanimatePath requiring reanimate + darkrit + one of {gris, archon}."""
    from combo_engine import ReanimatePath
    return ReanimatePath(
        tag='rean',
        required_tags=frozenset({'reanimate', 'darkrit'}),
        mana_cost=1,
        turns_to_kill=1,
        target_tags=frozenset({'gris', 'archon'}),
        enabler_tag='darkrit',
        reanimate_tag='reanimate',
    )


def _mkview(tags, mana):
    """Build a minimal GameView for is_satisfiable probes."""
    from combo_engine import GameView
    return GameView(own_deck='x', opp_deck='y',
                    available=frozenset(tags), hand=(),
                    mana=mana, turn=1, opp_hand_size=7)


# ──────────────────────────────────────────────────────────────────────────────
# CR 601.2f — paying a spell's mana cost (`MTGRules.can_cast`)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_cannot_cast_one_cmc_spell_with_empty_pool(brainstorm_card, empty_pool):
    from rules import MTGRules
    assert MTGRules.can_cast(brainstorm_card, empty_pool) is False


@pytest.mark.fast
def test_can_cast_one_cmc_spell_when_pool_holds_matching_color(
        brainstorm_card, one_u_pool):
    from rules import MTGRules
    assert MTGRules.can_cast(brainstorm_card, one_u_pool) is True


# ──────────────────────────────────────────────────────────────────────────────
# ManaManager.spend_amount — deducts and clamps
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_mana_manager_initial_available_matches_constructor(mana_manager):
    assert mana_manager.available == 5


@pytest.mark.fast
def test_mana_manager_spend_amount_deducts(mana_manager):
    mana_manager.spend_amount(2)
    assert mana_manager.available == 3


@pytest.mark.fast
def test_mana_manager_spend_amount_clamps_at_zero(mana_manager):
    mana_manager.spend_amount(2)
    mana_manager.spend_amount(5)
    assert mana_manager.available == 0


# ──────────────────────────────────────────────────────────────────────────────
# CR 202.1 — printed mana cost on deck-builder card objects
# Mechanic: combo strategies gate execution on `card.cmc` / `card.mana_cost`.
# If a deck builder reports a different cost than the printed card, the gate
# fires at the wrong turn. Class size: every combo win-condition card.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_three_cmc_combo_finisher_has_cmc_three(doomsday_card):
    assert doomsday_card.cmc == 3


@pytest.mark.fast
def test_three_cmc_combo_finisher_has_triple_colored_cost(doomsday_card):
    assert doomsday_card.mana_cost == {'B': 3}


@pytest.mark.fast
def test_combo_deck_builder_importable_without_error():
    """The legacy Doomsday cost-check block is wrapped in try/except and logs
    `error: …` if any import raises. The pytest equivalent: building the deck
    and retrieving its win-condition card must not raise."""
    from cards import make_doomsday_deck
    dd_cards = [c for c in make_doomsday_deck() if c.tag == 'dd']
    assert len(dd_cards) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Companion-zone deploy (CR 702.139): combo deck reliably casts its companion
# off the dedicated companion_zone, not from an unlikely main-deck draw.
# Class size: every Legacy deck running a companion in 2026 meta.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_companion_deploys_from_companion_zone_at_least_once_over_20_seeds():
    import random
    from sim import run_game
    deploys = 0
    for seed in range(1, 21):
        random.seed(seed)
        r = run_game('doomsday', 'burn', trace=True)
        if any('Lurrus of the Dream-Den' in line  # abstraction-allow: rules-test
               and 'lifelink' in line.lower()
               for line in r.log_lines):
            deploys += 1
            break  # 1 deployment is sufficient for the rule assertion
    assert deploys >= 1


@pytest.mark.fast
def test_companion_zone_smoke_runs_without_error():
    """The legacy Phase E block is wrapped in try/except and logs `error: …`
    if `run_game` raises. The pytest equivalent: a single companion-deck game
    must not raise."""
    import random
    from sim import run_game
    random.seed(1)
    r = run_game('doomsday', 'burn', trace=True)
    assert r.winner in ('p1', 'p2')


# ──────────────────────────────────────────────────────────────────────────────
# combo_engine.ReanimatePath.is_satisfiable
# Mechanic: a reanimation line requires reanimate-spell tag + enabler tag +
# at least one target tag + minimum mana floor, all simultaneously.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_reanimate_path_satisfiable_when_all_pieces_present(reanimate_path):
    assert reanimate_path.is_satisfiable(
        _mkview({'reanimate', 'darkrit', 'gris'}, 1)) is True


@pytest.mark.fast
def test_reanimate_path_unsatisfiable_without_reanimate_spell(reanimate_path):
    assert reanimate_path.is_satisfiable(
        _mkview({'darkrit', 'gris'}, 1)) is False


@pytest.mark.fast
def test_reanimate_path_unsatisfiable_without_mana_enabler(reanimate_path):
    assert reanimate_path.is_satisfiable(
        _mkview({'reanimate', 'gris'}, 1)) is False


@pytest.mark.fast
def test_reanimate_path_unsatisfiable_without_any_target(reanimate_path):
    assert reanimate_path.is_satisfiable(
        _mkview({'reanimate', 'darkrit'}, 1)) is False


@pytest.mark.fast
def test_reanimate_path_target_can_be_any_one_of_target_tags(reanimate_path):
    assert reanimate_path.is_satisfiable(
        _mkview({'reanimate', 'darkrit', 'archon'}, 1)) is True


# ──────────────────────────────────────────────────────────────────────────────
# combo_engine.combo_plan — mana floor gate on a satisfiable-on-paper path
# Mechanic: when mana=0, even a hand with every required tag yields NoPlan
# because no declared path's mana_cost is met.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_combo_plan_returns_noplan_when_mana_below_path_floor():
    import combo_engine as cep
    from cards import DECKS
    from game import GameState, PlayerState

    rean_cards = DECKS['reanimator']()
    reanimate = next((c for c in rean_cards if c.tag == 'reanimate'), None)
    darkrit = next((c for c in rean_cards if c.tag == 'darkrit'), None)
    gris = next((c for c in rean_cards if c.tag == 'gris'), None)
    # The legacy harness gates this whole branch on these pieces existing;
    # if any are missing the test is structurally unrunnable.
    assert reanimate is not None and darkrit is not None and gris is not None

    p1 = PlayerState(name='p1', hand=[reanimate, darkrit], library=[])
    p1.graveyard = [gris]
    p2 = PlayerState(name='p2', hand=[], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck='reanimator', p2_deck='burn')
    gs.turn = 2
    gs._executing_mana = 0

    plan = cep.combo_plan(p1, p2, gs)
    assert isinstance(plan, cep.NoPlan)
