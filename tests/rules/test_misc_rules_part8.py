"""Migrated rules tests for ticket misc_rules_part8.

Source: sim.py:run_rules_tests() lines 3481-3611. Covers two subsystems:

1. combo_plan() planner (combo_engine.py):
   - Branch 4: no satisfiable path on a storm view → NoPlan.
   - Branch 7: graveyard tags count as "available" alongside hand tags.
   - Branch 8: depths' nine assembly paths — when a view satisfies every
     required tag, Execute is returned and the picked path minimises
     (turns_to_kill, mana_cost).
   - Branch 9: combo_plan is pure — calling it twice does not mutate the
     caller's hand / graveyard / executing-mana fixture state.
   - Branch (exception-trap): the combo_plan setup block runs end-to-end
     without raising, i.e. the deck registry exposes the tags the planner
     expects and combo_plan() never throws on a well-formed view.

2. regression_sweep.diff_against_baseline() (tools/regression_sweep.py):
   - Rule 1: matched baseline + identical current WR → no regression, delta 0.
   - Rule 2: WR drop above threshold → flagged.
   - Rule 3: drop AT exactly the threshold (strict >) → NOT flagged.
   - Rule 4: WR improvement → never flagged (no upper bound).
   - Rule 5: matchup absent from baseline → not flagged, delta_pp None.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import combo_engine as _cep
from cards import DECKS
from deck_registry import get_combo_meta
from game import GameState, PlayerState
from rules import Card, CardType

# Make tools/ importable for regression_sweep helpers.
_TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from regression_sweep import (  # noqa: E402
    diff_against_baseline,
)


# ─────────────────────────────────────────────────────────────────────────────
# combo_plan() fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _mkfill() -> Card:
    c = Card(name="_filler", card_type=CardType.LAND, cmc=0,
             mana_cost={}, colors=set(), gy_type="land")
    c.tag = "filler"
    return c


@pytest.fixture
def storm_no_tendrils_view():
    """Branch 4: storm plan w/ low-threat opp + no 'tendrils' tag in hand.

    Mirrors sim.py:3474-3480. With the storm path requiring the 'tendrils'
    tag and an empty hand on p1, no path is satisfiable → NoPlan.
    """
    p1 = PlayerState(name="p1", hand=[], library=[])
    p2 = PlayerState(name="p2", hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck="storm", p2_deck="burn")
    gs.turn = 3
    gs._executing_mana = 5
    return _cep.combo_plan(p1, p2, gs)


@pytest.fixture
def reanimator_split_zone_plan():
    """Branch 7: reanimator with one piece in hand, the rest in graveyard.

    Mirrors sim.py:3504-3510. The planner must treat graveyard tags as
    available alongside hand tags ("split-zone view") and return Execute.
    """
    rean_cards = DECKS["reanimator"]()
    reanimate = next((c for c in rean_cards if c.tag == "reanimate"), None)
    darkrit = next((c for c in rean_cards if c.tag == "darkrit"), None)
    gris = next((c for c in rean_cards if c.tag == "gris"), None)
    assert reanimate and darkrit and gris, \
        "reanimator deck must expose 'reanimate', 'darkrit', 'gris' tags"

    p1 = PlayerState(name="p1", hand=[darkrit], library=[])
    p1.graveyard = [reanimate, gris]
    p2 = PlayerState(name="p2", hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck="reanimator", p2_deck="burn")
    gs.turn = 2
    gs._executing_mana = 1
    return _cep.combo_plan(p1, p2, gs)


@pytest.fixture
def depths_full_piece_set():
    """Branch 8: depths view with every required tag present (mana=99).

    Mirrors sim.py:3516-3543. Returns a dict with the plan, the assembly
    paths, and the snapshot of player/gs state used to assert purity in
    Branch 9 (sim.py:3545-3555).
    """
    depths_meta = get_combo_meta("depths")
    assert depths_meta, "depths must expose combo metadata"
    all_paths = depths_meta["assembly_paths"]

    all_tags = set()
    for path in all_paths:
        all_tags |= path.required_tags
        all_tags |= path.target_tags

    def _stub_card(tag: str) -> Card:
        c = Card(name=f"_{tag}", card_type=CardType.SORCERY, cmc=0,
                 mana_cost={}, colors=set(), gy_type="sorcery")
        c.tag = tag
        return c

    p1 = PlayerState(name="p1", hand=[_stub_card(t) for t in all_tags],
                     library=[])
    p1.graveyard = []
    p2 = PlayerState(name="p2", hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck="depths", p2_deck="burn")
    gs.turn = 3
    gs._executing_mana = 99
    plan = _cep.combo_plan(p1, p2, gs)
    return {
        "plan": plan,
        "all_paths": all_paths,
        "p1": p1,
        "gs": gs,
        "hand_snapshot": list(p1.hand),
        "gy_snapshot": list(p1.graveyard),
        "em_snapshot": gs._executing_mana,
    }


@pytest.fixture
def depths_after_second_call(depths_full_piece_set):
    """Re-invoke combo_plan() on the same fixture to test purity (Branch 9)."""
    ctx = depths_full_piece_set
    _cep.combo_plan(ctx["p1"], ctx["gs"].p2, ctx["gs"])
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# combo_plan() tests (Branches 4, 7, 8, 9)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_combo_plan_returns_noplan_when_no_path_is_satisfiable(
    storm_no_tendrils_view,
):
    """sim.py:3481 — low-threat opp + zero required tags → NoPlan."""
    assert isinstance(storm_no_tendrils_view, _cep.NoPlan)


@pytest.mark.fast
def test_combo_plan_treats_graveyard_tags_as_available(
    reanimator_split_zone_plan,
):
    """sim.py:3509 — Branch 7: graveyard tags count toward path satisfiability."""
    assert isinstance(reanimator_split_zone_plan, _cep.Execute)


@pytest.mark.fast
def test_combo_plan_executes_when_every_required_tag_is_in_view(
    depths_full_piece_set,
):
    """sim.py:3536 — maximally-satisfiable view → Execute."""
    assert isinstance(depths_full_piece_set["plan"], _cep.Execute)


@pytest.mark.fast
def test_combo_plan_picks_path_minimising_turns_then_mana(
    depths_full_piece_set,
):
    """sim.py:3542 — chosen Execute path is the (ttk, mana_cost) minimum."""
    plan = depths_full_piece_set["plan"]
    paths = depths_full_piece_set["all_paths"]
    assert isinstance(plan, _cep.Execute)
    picked = plan.path
    min_key = min((p.turns_to_kill, p.mana_cost) for p in paths)
    assert (picked.turns_to_kill, picked.mana_cost) == min_key


@pytest.mark.fast
def test_combo_plan_does_not_mutate_player_hand(depths_after_second_call):
    """sim.py:3550 — Branch 9 purity: hand unchanged across calls."""
    ctx = depths_after_second_call
    assert ctx["p1"].hand == ctx["hand_snapshot"]


@pytest.mark.fast
def test_combo_plan_does_not_mutate_player_graveyard(depths_after_second_call):
    """sim.py:3552 — Branch 9 purity: graveyard unchanged across calls."""
    ctx = depths_after_second_call
    assert ctx["p1"].graveyard == ctx["gy_snapshot"]


@pytest.mark.fast
def test_combo_plan_does_not_mutate_executing_mana(depths_after_second_call):
    """sim.py:3554 — Branch 9 purity: gs._executing_mana unchanged."""
    ctx = depths_after_second_call
    assert ctx["gs"]._executing_mana == ctx["em_snapshot"]


@pytest.mark.fast
def test_combo_plan_setup_block_does_not_raise(depths_full_piece_set):
    """sim.py:3558 — the legacy try/except never fires on well-formed views.

    The original suite wrapped the entire combo_plan block in a try/except
    that asserted False on any exception. Reaching this point with the
    fixture successfully constructed proves combo_plan never raised on the
    well-formed depths view (Execute or not).
    """
    assert depths_full_piece_set["plan"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# regression_sweep.diff_against_baseline() tests (Rules 1, 2, 3, 4, 5)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_regression_sweep_identical_wr_yields_zero_regressions():
    """sim.py:3578 — Rule 1: matched baseline + identical WR → no regression."""
    cur = {"a_vs_b": {"p1": "a", "p2": "b", "p1_wr": 0.50}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    _, reg = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert len(reg) == 0


@pytest.mark.fast
def test_regression_sweep_identical_wr_yields_zero_delta_pp():
    """sim.py:3580 — Rule 1: matched baseline + identical WR → delta_pp == 0."""
    cur = {"a_vs_b": {"p1": "a", "p2": "b", "p1_wr": 0.50}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    all_rows, _ = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert all_rows[0]["delta_pp"] == 0.0


@pytest.mark.fast
def test_regression_sweep_wr_drop_above_threshold_is_flagged():
    """sim.py:3587 — Rule 2: 10pp drop with threshold 5pp → 1 regression."""
    cur = {"a_vs_b": {"p1": "a", "p2": "b", "p1_wr": 0.40}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    _, reg = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert len(reg) == 1


@pytest.mark.fast
def test_regression_sweep_drop_at_exactly_threshold_is_not_flagged():
    """sim.py:3595 — Rule 3: strict > comparison, equal-to-threshold passes."""
    cur = {"a_vs_b": {"p1": "a", "p2": "b", "p1_wr": 0.45}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    _, reg = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert len(reg) == 0


@pytest.mark.fast
def test_regression_sweep_wr_improvement_is_never_flagged():
    """sim.py:3602 — Rule 4: positive deltas are never regressions."""
    cur = {"a_vs_b": {"p1": "a", "p2": "b", "p1_wr": 0.80}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    _, reg = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert len(reg) == 0


@pytest.mark.fast
def test_regression_sweep_new_matchup_vs_missing_baseline_is_not_flagged():
    """sim.py:3609 — Rule 5: matchup absent from baseline → 0 regressions."""
    cur = {"new_vs_other": {"p1": "new", "p2": "other", "p1_wr": 0.30}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    _, reg = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert len(reg) == 0


@pytest.mark.fast
def test_regression_sweep_new_matchup_row_has_delta_pp_none():
    """sim.py:3611 — Rule 5: new matchup row carries delta_pp = None."""
    cur = {"new_vs_other": {"p1": "new", "p2": "other", "p1_wr": 0.30}}
    bas = {"matchups": [{"p1": "a", "p2": "b", "p1_wr": 0.50}]}
    all_rows, _ = diff_against_baseline(cur, bas, threshold_pp=5.0)
    assert all_rows[0]["delta_pp"] is None
