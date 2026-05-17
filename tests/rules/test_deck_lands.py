"""Migrated rules tests for ticket: deck_lands.

Source: sim.py:run_rules_tests() lines 2604-2829

Two mechanic clusters:

1. **MatchupCategory deck-membership** — when `sim._pick_land` /
   `sim._execute_turn` gate mechanic-specific behavior on
   `MatchupCategory.{ARTIFACT,DEPTHS_COMBO,TS_DEFER}`, those categories must
   contain the originally-hardcoded decks. The Class-D regression that
   prompted these assertions was a depths-combo land-priority gate that had
   been keyed on the literal string `'lands'` for months, so when the
   `depths` deck shipped it silently fell through and slipped the combo by
   one turn (depths vs burn dropped to 35%).
2. **Fast-mana sources are not double-counted** — CR 106 / 605: a mana
   ability that produces N mana is counted ONCE per activation. Before the
   structural fix, the shared `_execute_turn` preamble pre-credited Lotus
   Petal mana to `total_mana` AND let strategies "crack" the same Petal,
   double-counting it. The regression test: with an opener of 0 lands +
   1 Petal + Grim Monolith + Painter's Servant, the strategy must NOT cast
   a CMC-2 spell on T1 (Petal alone provides 1 mana; Monolith stays in hand
   waiting for actual lands; only the CMC-1 Grindstone is castable).
"""
from __future__ import annotations

import random

import pytest

from config import MatchupCategory
from sim import run_game


# ── MatchupCategory deck-membership ──────────────────────────────────────────


@pytest.mark.fast
def test_artifact_category_contains_affinity_deck():
    """MC.ARTIFACT gates artifact-mirror behavior; affinity must be a member."""
    assert ('affinity' in MatchupCategory.ARTIFACT) is True


@pytest.mark.fast
def test_artifact_category_contains_eight_cast_deck():
    """MC.ARTIFACT gates artifact-mirror behavior; eight_cast must be a member."""
    assert ('eight_cast' in MatchupCategory.ARTIFACT) is True


@pytest.mark.fast
def test_depths_combo_category_contains_lands_deck():
    """MC.DEPTHS_COMBO gates Dark Depths + Stage land-priority for any deck
    running the combo; the `lands` deck must be a member."""
    assert ('lands' in MatchupCategory.DEPTHS_COMBO) is True


@pytest.mark.fast
def test_depths_combo_category_contains_depths_deck():
    """MC.DEPTHS_COMBO gates Dark Depths + Stage land-priority; the `depths`
    deck must be a member (pre-fix it was hardcoded to only `'lands'`, slipping
    Depths' combo by one turn against fast clocks)."""
    assert ('depths' in MatchupCategory.DEPTHS_COMBO) is True


@pytest.mark.fast
def test_ts_defer_category_contains_reanimator_deck():
    """MC.TS_DEFER lists decks whose Thoughtseize branch must defer when the
    same-turn combo line would consume the only available ritual mana."""
    assert ('reanimator' in MatchupCategory.TS_DEFER) is True


@pytest.mark.fast
def test_matchup_category_exposes_all_sim_gate_attributes():
    """Mirror of the legacy except-wrapper: the three categories used by
    sim.py gates must be importable and non-empty. If any of these attributes
    disappear, the gates in `_pick_land` / `_execute_turn` silently stop
    firing — exactly the failure mode the original assertions guarded."""
    for attr in ('ARTIFACT', 'DEPTHS_COMBO', 'TS_DEFER'):
        category = getattr(MatchupCategory, attr)
        assert len(category) >= 1, f"MatchupCategory.{attr} is empty"


# ── Fast-mana sources must not be double-counted (CR 106 / 605) ──────────────


def _count_phantom_cmc2_painter_casts() -> tuple[int, int]:
    """Replay the Painter-vs-Burn loop from sim.py:2790-2820.

    Returns (phantom_cmc2_casts, qualifying_games). A qualifying opener has
    0 lands + >= 1 Lotus Petal + >= 1 Grim Monolith + Painter's Servant. A
    'phantom' cast is a T1 RESOLVES log entry for Painter's Servant (CMC 2),
    which is illegal under correct mana accounting when only a single Petal
    is available.
    """
    phantom_cmc2_casts = 0
    qualifying_games = 0
    # Same fixed seed slice the legacy assertion used.
    for seed in range(1, 16):
        random.seed(seed)
        r = run_game('painter', 'burn', trace=True)
        opener = r.p1_opening_hand
        # Painter's lands: Ancient Tomb, Planar Nexus, Urza's Saga,
        # Urza's Tower, Urza's Workshop. Mishra's Research Desk is an
        # artifact cantrip, NOT a land.
        painter_lands = {  # abstraction-allow: rules-test
            'Ancient Tomb', 'Planar Nexus',
            "Urza's Saga", "Urza's Tower", "Urza's Workshop",
        }
        n_lands = sum(1 for n in opener if n in painter_lands)
        n_petals = sum(1 for n in opener if n == 'Lotus Petal')  # abstraction-allow: rules-test
        n_monoliths = sum(1 for n in opener if n == 'Grim Monolith')  # abstraction-allow: rules-test
        has_painter = any("Painter's Servant" in n for n in opener)  # abstraction-allow: rules-test
        if n_lands == 0 and n_petals >= 1 and n_monoliths >= 1 and has_painter:
            qualifying_games += 1
            # T1 trace check: 60-line slice covers the first turn's plays.
            t1_painter_cast = any(
                "Painter's Servant" in line and 'RESOLVES' in line  # abstraction-allow: rules-test
                for line in r.log_lines[:60]
            )
            if t1_painter_cast:
                phantom_cmc2_casts += 1
    return phantom_cmc2_casts, qualifying_games


@pytest.mark.fast
def test_lotus_petal_not_double_counted_on_zero_land_painter_opener():
    """A 0-land + 1-Petal opener cannot cast CMC-2 Painter's Servant on T1.

    Pre-fix the shared preamble added +1 mana per Petal in hand to total_mana
    BEFORE the strategy ran, so each strategy then double-counted Petal when
    it "cracked" them. The fix routes Petal mana through the strategy's own
    crack-event only, restoring CR 605's once-per-activation accounting.
    """
    phantom_cmc2_casts, _ = _count_phantom_cmc2_painter_casts()
    assert (phantom_cmc2_casts == 0) is True


@pytest.mark.fast
def test_painter_vs_burn_qualifying_loop_runs_without_raising():
    """Mirror of the legacy except-wrapper around sim.py:2790-2828: the
    Painter-vs-Burn replay loop must complete cleanly so the double-count
    assertion above is actually exercising real game state, not silently
    no-op'ing on an exception."""
    _, qualifying_games = _count_phantom_cmc2_painter_casts()
    # The original test's correctness depends on at least one qualifying
    # opener appearing in the 15-seed slice; assert that invariant too.
    assert qualifying_games >= 1
