"""Pytest migration for ticket: misc_rules_part7.

Source: sim.py:run_rules_tests() lines 3298-3449.

Covers:
- Phase B GameView immutability invariant.
- Phase B2 AssemblyPath subtype taxonomy (StormPath / ReanimatePath /
  LandComboPath / TribalPath) — existence + inheritance.
- LandComboPath.is_satisfiable rules for trivial and tutor lines.
- TribalPath.is_satisfiable rules for cheat and hardcast lines.
- combo_plan() returns NoPlan for decks without combo metadata.

All assertions are pure (no game loop).
"""
from __future__ import annotations

import pytest

import combo_engine as _ce
from combo_engine import (
    AssemblyPath,
    GameView,
    LandComboPath,
    NoPlan,
    StormPath,
    ReanimatePath,
    TribalPath,
    combo_plan,
)
from game import GameState, PlayerState
from rules import Card, CardType


# ── Module-level fixtures ─────────────────────────────────────────────

def _mkview(tags, mana):
    """Build a GameView with the given available tag set and mana floor."""
    return GameView(
        own_deck='x', opp_deck='y',
        available=frozenset(tags), hand=(),
        mana=mana, turn=1, opp_hand_size=7,
    )


@pytest.fixture(scope='module')
def gameview_from_real_state():
    """GameView.from_state populated from a real (empty) GameState."""
    v_p1 = PlayerState(name='p1', hand=[], library=[])
    v_p2 = PlayerState(name='p2', hand=[], library=[])
    v_gs = GameState(p1=v_p1, p2=v_p2, p1_deck='storm', p2_deck='dimir')
    v_gs.turn = 3
    v_gs._executing_mana = 5
    return GameView.from_state(v_p1, v_p2, v_gs)


@pytest.fixture(scope='module')
def landcombo_trivial_path():
    """LandComboPath: trivial line (both lands required, no enabler tutor)."""
    return LandComboPath(
        tag='triv',
        required_tags=frozenset({'depths', 'stage'}),
        mana_cost=2, turns_to_kill=1,
        required_lands=frozenset({'depths', 'stage'}),
        enabler_tag=None,
    )


@pytest.fixture(scope='module')
def landcombo_tutor_path():
    """LandComboPath: tutor line (one land held, enabler tutors the other)."""
    return LandComboPath(
        tag='crop_stage',
        required_tags=frozenset({'depths', 'crop'}),
        mana_cost=3, turns_to_kill=1,
        required_lands=frozenset({'depths'}),
        enabler_tag='crop',
    )


@pytest.fixture(scope='module')
def tribal_cheat_path():
    """TribalPath: cheat line (Lackey-style enabler + tribe payoff in hand)."""
    return TribalPath(
        tag='lackey_cheat',
        required_tags=frozenset({'lackey'}),
        mana_cost=1, turns_to_kill=2,
        target_tags=frozenset({'muxus', 'matron'}),  # abstraction-allow: rules-test
        tribe_tags=frozenset({'muxus', 'matron'}),   # abstraction-allow: rules-test
        cheat_enabler_tag='lackey',
    )


@pytest.fixture(scope='module')
def tribal_hardcast_path():
    """TribalPath: hardcast line (no cheat enabler, generic required_tags)."""
    return TribalPath(
        tag='hardcast',
        required_tags=frozenset({'muxus'}),  # abstraction-allow: rules-test
        mana_cost=6, turns_to_kill=1,
        tribe_tags=frozenset(), cheat_enabler_tag='',
    )


# ── L3298: GameView is frozen (immutable) ─────────────────────────────

@pytest.mark.fast
def test_gameview_dataclass_is_frozen(gameview_from_real_state):
    """Phase B: GameView must be a frozen dataclass — callers may not mutate."""
    assert type(gameview_from_real_state).__dataclass_params__.frozen is True


# ── L3305: AssemblyPath subtype exists in combo_engine ────────────────

@pytest.mark.fast
@pytest.mark.parametrize(
    'subtype_name',
    ['StormPath', 'ReanimatePath', 'LandComboPath', 'TribalPath'],
)
def test_assembly_path_subtype_is_exported(subtype_name):
    """Phase B2: each deck-shape subtype is exported from combo_engine."""
    assert hasattr(_ce, subtype_name) is True


# ── L3307: AssemblyPath subtype extends AssemblyPath ──────────────────

@pytest.mark.fast
@pytest.mark.parametrize(
    'subtype_name',
    ['StormPath', 'ReanimatePath', 'LandComboPath', 'TribalPath'],
)
def test_assembly_path_subtype_extends_base(subtype_name):
    """Phase B2: each subtype is a true subclass of AssemblyPath."""
    assert issubclass(getattr(_ce, subtype_name), AssemblyPath) is True


# ── L3311: combo_engine architecture invariants import cleanly ────────

@pytest.mark.fast
def test_combo_engine_architecture_invariants_importable():
    """The Phase B / B2 surface imports without raising.

    Mirrors the `except` fallback in sim.run_rules_tests(): if any of the
    architecture invariants above raise, sim.py records a failure. Pytest
    encodes the same guarantee by re-importing the public surface here.
    """
    from combo_engine import (  # noqa: F401
        AssemblyPath, Execute, Hold, Defer, NoPlan,
        StormPath, ReanimatePath, LandComboPath, TribalPath,
        GameView, combo_plan,
    )
    assert True


# ── L3362: LandComboPath trivial — satisfiable when both lands present

@pytest.mark.fast
def test_landcombo_trivial_satisfied_when_both_lands_and_mana(landcombo_trivial_path):
    """LandComboPath trivial line: needs both required lands + mana floor."""
    assert landcombo_trivial_path.is_satisfiable(
        _mkview({'depths', 'stage'}, 2)
    ) is True


# ── L3364: LandComboPath trivial — unsatisfiable when one land missing

@pytest.mark.fast
def test_landcombo_trivial_unsatisfied_when_one_land_missing(landcombo_trivial_path):
    """LandComboPath trivial line: missing either required land → not satisfied."""
    assert landcombo_trivial_path.is_satisfiable(
        _mkview({'depths'}, 2)
    ) is False


# ── L3373: LandComboPath tutor — satisfied when held-land+enabler+mana

@pytest.mark.fast
def test_landcombo_tutor_satisfied_when_held_land_enabler_and_mana(landcombo_tutor_path):
    """LandComboPath tutor line: held-land + enabler tag + mana → satisfied."""
    assert landcombo_tutor_path.is_satisfiable(
        _mkview({'depths', 'crop'}, 3)
    ) is True


# ── L3375: LandComboPath tutor — unsatisfied when held-land missing ──

@pytest.mark.fast
def test_landcombo_tutor_unsatisfied_when_held_land_missing(landcombo_tutor_path):
    """LandComboPath tutor line: enabler alone cannot replace the held land."""
    assert landcombo_tutor_path.is_satisfiable(
        _mkview({'stage', 'crop'}, 3)
    ) is False


# ── L3377: LandComboPath tutor — unsatisfied when enabler missing ────

@pytest.mark.fast
def test_landcombo_tutor_unsatisfied_when_enabler_missing(landcombo_tutor_path):
    """LandComboPath tutor line: held-land alone is not enough without the tutor."""
    assert landcombo_tutor_path.is_satisfiable(
        _mkview({'depths'}, 3)
    ) is False


# ── L3387: TribalPath cheat — satisfied with enabler+tribe+mana ──────

@pytest.mark.fast
def test_tribal_cheat_satisfied_when_enabler_and_tribe_and_mana(tribal_cheat_path):
    """TribalPath cheat line: enabler tag + at least one tribe payoff + mana."""
    assert tribal_cheat_path.is_satisfiable(
        _mkview({'lackey', 'muxus'}, 1)  # abstraction-allow: rules-test
    ) is True


# ── L3389: TribalPath cheat — unsatisfied when cheat_enabler missing ─

@pytest.mark.fast
def test_tribal_cheat_unsatisfied_when_cheat_enabler_missing(tribal_cheat_path):
    """TribalPath cheat line: tribe payoff alone cannot cheat without enabler."""
    assert tribal_cheat_path.is_satisfiable(
        _mkview({'muxus'}, 1)  # abstraction-allow: rules-test
    ) is False


# ── L3391: TribalPath cheat — unsatisfied when no tribe payoff ───────

@pytest.mark.fast
def test_tribal_cheat_unsatisfied_when_no_tribe_payoff(tribal_cheat_path):
    """TribalPath cheat line: enabler with no tribe payoff in view → not satisfied."""
    assert tribal_cheat_path.is_satisfiable(
        _mkview({'lackey'}, 1)
    ) is False


# ── L3399: TribalPath hardcast — satisfied with required tag + mana ──

@pytest.mark.fast
def test_tribal_hardcast_satisfied_with_required_tag_and_mana(tribal_hardcast_path):
    """TribalPath hardcast: with no cheat enabler, required_tags + mana suffice."""
    assert tribal_hardcast_path.is_satisfiable(
        _mkview({'muxus'}, 6)  # abstraction-allow: rules-test
    ) is True


# ── L3401: TribalPath hardcast — unsatisfied when mana floor not met ─

@pytest.mark.fast
def test_tribal_hardcast_unsatisfied_when_mana_floor_not_met(tribal_hardcast_path):
    """TribalPath hardcast: required tag present but mana below cost → not satisfied."""
    assert tribal_hardcast_path.is_satisfiable(
        _mkview({'muxus'}, 5)  # abstraction-allow: rules-test
    ) is False


# ── L3449: combo_plan — deck without combo metadata returns NoPlan ───

@pytest.mark.fast
def test_combo_plan_no_metadata_returns_noplan():
    """combo_plan: a deck with no combo metadata short-circuits to NoPlan."""
    def _mkfill():
        c = Card(
            name='_filler', card_type=CardType.LAND, cmc=0,
            mana_cost={}, colors=set(), gy_type='land',
        )
        c.tag = 'filler'
        return c

    p1 = PlayerState(name='p1', hand=[], library=[])
    p2 = PlayerState(name='p2', hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck='bug', p2_deck='dimir')
    gs.turn = 3
    gs._executing_mana = 5
    plan = combo_plan(p1, p2, gs)
    assert isinstance(plan, NoPlan) is True
