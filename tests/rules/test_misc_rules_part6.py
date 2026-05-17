"""Combo-engine Phase-B re-architecture invariants.

Migrated from sim.py:run_rules_tests() lines 3232-3296. These pin the
public surface of `combo_engine.py` and the deck-registry combo schema:

- `deck_registry.get_combo_meta` accepts every registered deck key.
- `AssemblyPath` is a four-field dataclass.
- The Plan algebra (`Execute`, `Hold`, `Defer`, `NoPlan`) has replaced the
  old predicate trio (`is_combo_ready_this_turn`, `combo_protection_check`,
  `fastest_assemble_plan`, `ProtectionDecision`).
- `GameView.from_state` constructs an immutable view of a real `GameState`.

See docs/design/2026-05-15_post-phase-6-re-architecture.md (Phase B).
"""
from __future__ import annotations

import pytest

import combo_engine as _ce
from combo_engine import AssemblyPath
from deck_registry import get_all_keys, get_combo_meta
from game import GameState, PlayerState


# ---------------------------------------------------------------------------
# Module-level fixtures shared across multiple tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope='module')
def sample_assembly_path() -> AssemblyPath:
    """An AssemblyPath with every required field populated."""
    return AssemblyPath(
        tag='hexmage',
        required_tags=frozenset({'depths', 'hexmage'}),
        mana_cost=2,
        turns_to_kill=1,
    )


@pytest.fixture(scope='module')
def gameview_from_real_state():
    """GameView built from a real (minimal) GameState with mana floor 5."""
    p1 = PlayerState(name='p1', hand=[], library=[])
    p2 = PlayerState(name='p2', hand=[], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck='storm', p2_deck='dimir')
    gs.turn = 3
    gs._executing_mana = 5
    return _ce.GameView.from_state(p1, p2, gs)


# ---------------------------------------------------------------------------
# 1. Deck-registry combo-meta schema (sim.py L3232).
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_combo_meta_schema_validates_for_every_registered_deck():
    """get_combo_meta() never raises KeyError for any registered deck key."""
    violations: list[tuple[str, str]] = []
    for key in get_all_keys():
        try:
            get_combo_meta(key)
        except KeyError as exc:
            violations.append((key, str(exc)))
    assert violations == []


# ---------------------------------------------------------------------------
# 2. AssemblyPath dataclass shape (sim.py L3245, L3252).
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_assembly_path_accepts_all_four_required_fields(sample_assembly_path):
    ap = sample_assembly_path
    ok = (
        ap.tag == 'hexmage'
        and ap.mana_cost == 2
        and ap.turns_to_kill == 1
        and 'depths' in ap.required_tags
    )
    assert ok is True


@pytest.mark.fast
def test_assembly_path_rejects_partial_construction():
    """Constructing with only one positional must raise TypeError."""
    with pytest.raises(TypeError):
        AssemblyPath(tag='x')


# ---------------------------------------------------------------------------
# 3. Phase B invariants — old predicate trio retired (sim.py L3258-L3266).
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_combo_plan_is_callable_on_combo_engine():
    assert callable(getattr(_ce, 'combo_plan', None)) is True


@pytest.mark.fast
def test_is_combo_ready_this_turn_is_retired():
    assert hasattr(_ce, 'is_combo_ready_this_turn') is False


@pytest.mark.fast
def test_combo_protection_check_is_retired():
    assert hasattr(_ce, 'combo_protection_check') is False


@pytest.mark.fast
def test_fastest_assemble_plan_is_retired():
    assert hasattr(_ce, 'fastest_assemble_plan') is False


@pytest.mark.fast
def test_protection_decision_is_retired():
    """Replaced by the Hold/Defer Plan variants."""
    assert hasattr(_ce, 'ProtectionDecision') is False


# ---------------------------------------------------------------------------
# 4. Plan algebra variants and `reason` field (sim.py L3272, L3275, L3278, L3281).
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize('variant', ['Execute', 'Hold', 'Defer', 'NoPlan'])
def test_plan_algebra_variant_exists_on_combo_engine(variant):
    assert hasattr(_ce, variant) is True


@pytest.mark.fast
def test_noplan_carries_reason_field():
    np_ = _ce.NoPlan(reason='no metadata')
    assert np_.reason == 'no metadata'


@pytest.mark.fast
def test_hold_carries_card_and_reason_fields():
    hp = _ce.Hold(reason='hold force', card=None)
    assert (hp.card, hp.reason) == (None, 'hold force')


@pytest.mark.fast
def test_execute_carries_path_and_reason_fields(sample_assembly_path):
    ep = _ce.Execute(reason='combo:tag', path=sample_assembly_path)
    assert (ep.path is sample_assembly_path, ep.reason) == (True, 'combo:tag')


# ---------------------------------------------------------------------------
# 5. GameView.from_state (sim.py L3292, L3294, L3296).
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_gameview_from_state_populates_own_deck(gameview_from_real_state):
    assert gameview_from_real_state.own_deck == 'storm'


@pytest.mark.fast
def test_gameview_from_state_populates_opp_deck(gameview_from_real_state):
    assert gameview_from_real_state.opp_deck == 'dimir'


@pytest.mark.fast
def test_gameview_from_state_surfaces_mana_floor(gameview_from_real_state):
    assert gameview_from_real_state.mana == 5
