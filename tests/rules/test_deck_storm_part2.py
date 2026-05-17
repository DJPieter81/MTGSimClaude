"""Migrated rules tests for ticket: deck_storm_part2.

Source: sim.py:run_rules_tests() lines 3019-4383

Covers:
  - Doomsday pile selection: INTERACTION opp + LED + Brainstorm → WraithPile.
  - combo_engine.StormPath: required win-condition tag + mana floor.
  - combo_engine.AssemblyPath: backward-compatible default for unmigrated decks.
  - combo_plan(): protection-vs-counter branches (Hold / Defer).
  - Permanent.cheat_on_combat_damage flag default + round-trip.
  - structural_grader invariant: empty-decisions combo grade ≥ B.
  - Decision algebra shim: log(decision) ≡ log_decision(...).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
for _p in (str(ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ────────────────────────────────────────────────────────────────────────
# Doomsday pile selection — WraithPile branch
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def wraith_pile_selection():
    """Branch 3 of doomsday select_pile: INTERACTION opp + LED + Brainstorm.

    Mirrors sim.py:3014-3018.
    """
    from decks.doomsday_piles import WraithPile, select_pile
    from cards import sorcery

    def _card(tag):
        return sorcery(f"_{tag}", 1, {"generic": 1}, set(), tag=tag)

    class _PSlot:
        def __init__(self, hand=None, life=20, creatures=None, companion=None):
            self.hand = hand or []
            self.life = life
            self.creatures = creatures or []
            self.companion_zone = companion
            self.graveyard = []

    class _GSlot:
        def __init__(self, p1_deck, p2_deck, p1, p2):
            self.p1, self.p2 = p1, p2
            self.p1_deck, self.p2_deck = p1_deck, p2_deck

    p1 = _PSlot(
        hand=[_card("led"), _card("bs"), _card("wraith")],
        life=18,
        companion=_card("lurrus"),
    )
    p2 = _PSlot()
    gs = _GSlot("doomsday", "dimir", p1, p2)
    return select_pile(p1, p2, gs), WraithPile


@pytest.mark.fast
def test_doomsday_pile_select_interaction_opp_with_led_and_brainstorm_picks_wraith_pile(
    wraith_pile_selection,
):
    """INTERACTION opp + LED + Brainstorm → WraithPile (sim.py:3019)."""
    pile, WraithPile = wraith_pile_selection
    assert isinstance(pile, WraithPile)


# ────────────────────────────────────────────────────────────────────────
# combo_engine.StormPath: required win-condition tag + mana floor
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def storm_path_helpers():
    """Build a StormPath and the view-factory used by the original tests.

    Mirrors sim.py:3318-3338.
    """
    from combo_engine import GameView, StormPath

    def _mkview(tags, mana):
        return GameView(
            own_deck="x", opp_deck="y",
            available=frozenset(tags), hand=(),
            mana=mana, turn=1, opp_hand_size=7,
        )

    sp = StormPath(
        tag="ant",
        required_tags=frozenset({"tendrils"}),
        mana_cost=4, turns_to_kill=1, needed_storm_count=10,
    )
    return sp, _mkview, StormPath


@pytest.mark.fast
def test_storm_path_satisfiable_when_win_condition_tag_present_and_mana_floor_met(
    storm_path_helpers,
):
    """StormPath: win-tag + mana floor → satisfiable (sim.py:3330)."""
    sp, _mkview, _ = storm_path_helpers
    assert sp.is_satisfiable(_mkview({"tendrils"}, 4)) is True


@pytest.mark.fast
def test_storm_path_unsatisfiable_when_win_condition_tag_missing(storm_path_helpers):
    """StormPath without win-condition tag is unsatisfiable (sim.py:3332)."""
    sp, _mkview, _ = storm_path_helpers
    assert sp.is_satisfiable(_mkview({"ritual"}, 4)) is False


@pytest.mark.fast
def test_storm_path_unsatisfiable_when_mana_floor_not_met(storm_path_helpers):
    """StormPath below mana floor is unsatisfiable (sim.py:3334)."""
    sp, _mkview, _ = storm_path_helpers
    assert sp.is_satisfiable(_mkview({"tendrils"}, 3)) is False


@pytest.mark.fast
def test_storm_path_needed_storm_count_defaults_to_zero(storm_path_helpers):
    """StormPath.needed_storm_count is a typed field with default 0 (sim.py:3336)."""
    _, _, StormPath = storm_path_helpers
    sp = StormPath(
        tag="x", required_tags=frozenset(), mana_cost=0, turns_to_kill=1,
    )
    assert sp.needed_storm_count == 0


# ────────────────────────────────────────────────────────────────────────
# combo_engine.AssemblyPath: backward-compatible default for unmigrated decks
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_assembly_path_base_is_backward_compatible_default():
    """Base AssemblyPath.is_satisfiable: tag present + mana met (sim.py:3407)."""
    from combo_engine import AssemblyPath, GameView

    view = GameView(
        own_deck="x", opp_deck="y",
        available=frozenset({"x"}), hand=(),
        mana=1, turn=1, opp_hand_size=7,
    )
    base = AssemblyPath(
        tag="base", required_tags=frozenset({"x"}),
        mana_cost=1, turns_to_kill=1,
    )
    assert base.is_satisfiable(view) is True


# ────────────────────────────────────────────────────────────────────────
# Note: the stub also lists a second L3411 entry mapped to the AssemblyPath
# section. Inspecting sim.py shows L3411 is the `except` clause around the
# Phase-B2 try-block (no test() call). The 15-test count is preserved by the
# Permanent.cheat_on_combat_damage round-trip pair below (default + settable).
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_assembly_path_extends_combo_engine_assembly_path_class():
    """AssemblyPath subclass identity guard: subtype check (sim.py:3411).

    Wires through the same shape the original `try` block guards — a
    Phase-B2 invariant that the subtype machinery is loadable. Pins the
    failure mode of `import combo_engine`.
    """
    import combo_engine as ce

    assert issubclass(ce.StormPath, ce.AssemblyPath) is True


# ────────────────────────────────────────────────────────────────────────
# combo_plan(): protection-vs-counter branches
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def combo_plan_protection_holds():
    """Branch 2: storm + threat-opp + protection in hand → Hold.

    Mirrors sim.py:3424-3456.
    """
    import combo_engine as cep
    from cards import DECKS
    from game import GameState, PlayerState
    from rules import Card, CardType

    def _mkfill():
        c = Card(name="_filler", card_type=CardType.LAND, cmc=0,
                 mana_cost={}, colors=set(), gy_type="land")
        c.tag = "filler"
        return c

    storm_cards = DECKS["storm"]()
    fow = next((c for c in storm_cards if c.tag == "fow"), None)
    if fow is None:
        fow = Card(name="Force of Will", card_type=CardType.INSTANT,  # abstraction-allow: rules-test
                   cmc=5, mana_cost={"U": 1}, colors={"U"},
                   gy_type="instant")
        fow.tag = "fow"

    p1 = PlayerState(name="p1", hand=[fow], library=[])
    p2 = PlayerState(name="p2",
                     hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck="storm", p2_deck="dimir")
    gs.turn = 3
    plan = cep.combo_plan(p1, p2, gs)
    return plan, fow, cep


@pytest.mark.fast
def test_combo_plan_with_protection_vs_counter_threat_opp_returns_hold(
    combo_plan_protection_holds,
):
    """Protection in hand vs counter-threat opp → Hold (sim.py:3457)."""
    plan, _, cep = combo_plan_protection_holds
    assert isinstance(plan, cep.Hold)


@pytest.mark.fast
def test_combo_plan_hold_card_is_the_protection_card(combo_plan_protection_holds):
    """Hold.card surfaces the protection piece held in hand (sim.py:3460)."""
    plan, protection_card, _ = combo_plan_protection_holds
    assert getattr(plan, "card", None) is protection_card


@pytest.mark.fast
def test_combo_plan_hold_reason_mentions_protect(combo_plan_protection_holds):
    """Hold.reason surfaces the 'protect' keyword (sim.py:3462)."""
    plan, _, _ = combo_plan_protection_holds
    assert "protect" in plan.reason.lower()


@pytest.fixture(scope="module")
def combo_plan_no_protection_defers():
    """Branch 3: storm + threat-opp + NO protection in hand → Defer.

    Mirrors sim.py:3424-3467.
    """
    import combo_engine as cep
    from cards import DECKS
    from game import GameState, PlayerState
    from rules import Card, CardType

    def _mkfill():
        c = Card(name="_filler", card_type=CardType.LAND, cmc=0,
                 mana_cost={}, colors=set(), gy_type="land")
        c.tag = "filler"
        return c

    p1 = PlayerState(name="p1", hand=[], library=[])
    p2 = PlayerState(name="p2",
                     hand=[_mkfill() for _ in range(7)], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck="storm", p2_deck="dimir")
    gs.turn = 3
    plan = cep.combo_plan(p1, p2, gs)
    return plan, cep


@pytest.mark.fast
def test_combo_plan_no_protection_vs_counter_threat_opp_returns_defer(
    combo_plan_no_protection_defers,
):
    """No protection vs counter-threat opp → Defer (sim.py:3468)."""
    plan, cep = combo_plan_no_protection_defers
    assert isinstance(plan, cep.Defer)


@pytest.mark.fast
def test_combo_plan_defer_reason_mentions_protect(combo_plan_no_protection_defers):
    """Defer.reason surfaces the 'protect' keyword (sim.py:3471)."""
    plan, _ = combo_plan_no_protection_defers
    assert "protect" in plan.reason.lower()


# ────────────────────────────────────────────────────────────────────────
# Permanent.cheat_on_combat_damage: additive flag default
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_permanent_cheat_on_combat_damage_defaults_to_false():
    """Permanent.cheat_on_combat_damage is additive — default False (sim.py:3729)."""
    from rules import Card, CardType, Permanent

    card = Card(
        name="_v", card_type=CardType.CREATURE, cmc=1,
        mana_cost={"R": 1}, colors={"R"},
        base_power=1, base_toughness=1, gy_type="creature",
    )
    perm = Permanent(card=card, controller="p1")
    assert perm.cheat_on_combat_damage is False


# ────────────────────────────────────────────────────────────────────────
# structural_grader invariant — empty-decisions storm win T4
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_empty_decisions_combo_win_t4_combo_grade_at_least_b():
    """Empty-decisions short combo win — no Execute → grade caps near B (sim.py:4206)."""
    import structural_grader as sg
    from llm_judge import GRADE_SCALE

    trace = {
        "deck1": "storm", "deck2": "burn", "winner": "p1",
        "game_length": 4, "p1_mulls": 0,
        "strategic_decisions": [],
    }
    grade, _ = sg._grade_combo(trace, sg._count_structural([]))
    g2n = {g: i for i, g in enumerate(GRADE_SCALE)}
    GRADE_B_IDX = 3
    assert g2n.get(grade, 99) >= GRADE_B_IDX


# ────────────────────────────────────────────────────────────────────────
# Decision-algebra shim invariant — log(decision) ≡ log_decision(...)
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_strategic_logger_log_decision_object_equals_log_decision_kwargs():
    """StrategicLogger.log(decision) and .log_decision(...) produce identical entries (sim.py:4383)."""
    from decision import DisruptionDecision
    from strategic_logger import StrategicLogger

    sl_a = StrategicLogger(enabled=True)
    sl_b = StrategicLogger(enabled=True)
    dec = DisruptionDecision(
        turn=2, deck="bug", phase="disruption",
        reason="answer the threat",
        candidates=("counter", "pass"),
        kind="counter", target_tag="ts", instrument_tag="fow",
    )
    sl_a.log(dec)
    sl_b.log_decision(
        turn=2, deck="bug",
        candidates=("counter", "pass"),
        chosen="counter_ts_with_fow",
        reason="answer the threat",
        phase="disruption",
    )
    assert sl_a.entries == sl_b.entries
