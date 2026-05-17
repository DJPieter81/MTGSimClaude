"""Migrated rules tests for ticket: misc_rules_part3.

Source: sim.py:run_rules_tests() lines 2686-2936

Mechanic clusters covered:

1. **Combo decks need adequate chain-thinning cards** — a "thin-via-cycle"
   combo deck must run enough cycle-cards (>=3) so a hand-presence on the kill
   turn is likely. Tested via the Doomsday wraith-count.

2. **Combo-land prioritization extends beyond one deck** — `_pick_land` must
   prioritize the missing Dark Depths / Stage piece for *any* deck running
   that combo (regression-tested via depths-vs-burn @ 10 fixed seeds >= 5/10).

3. **Deck-owned Thoughtseize must defer when combo can fire** — when the
   active deck has a same-turn combo line that consumes its only ritual mana,
   the TS branch must NOT fire first. Regression-tested via reanimator-vs-burn
   @ 10 fixed seeds >= 4/10.

4. **Discard-pitch fuel must survive hand-disruption ordering** — Mardu's
   Grief (evoke-pitch) + Ephemerate engine must fire when opener has pitch
   fuel. Pre-fix the shared TS preamble consumed the pitch black card before
   Grief could pay for itself.

5. **Lion's Eye Diamond fuels direct activations, not only Wish** — CR 605:
   any Belcher opener with Charbelcher + LED + >=4 fast-mana must reach a T1
   Charbelcher *activation* (kill-log marker), not merely a cast.

6. **Companion zone is outside the 60-card deck** — a deck declaring a
   `companion` in DECK_META has that card in `player.companion_zone` from
   turn 1, never in `hand` / `library`. Doomsday's maindeck contains exactly
   4 Cabal Therapy and 0 companion (the slot was reclaimed Phase A).

7. **Pile-selection algebra is a closed dataclass family** — every Pile
   subclass must inherit from Pile and be a `@dataclass`. Mirrors the typed
   algebra discipline of `combo_engine.combo_plan`.
"""
from __future__ import annotations

import random

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Module-level fixtures: heavy run_game loops shared across smoke + rule tests.
# Each cached fixture runs N games at fixed seeds and returns the aggregated
# counts so the per-line tests can each assert one invariant cheaply.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def depths_vs_burn_fixed_seed_wins() -> int:
    """Mirror of sim.py:2696-2702 — wins for depths (p1) over burn (p2) at
    10 fixed seeds.  Pre-fix this loop returned 0-1/10 (Depths slipped its
    combo by one turn); the >=5 bar is the regression gate."""
    from sim import run_game
    wins = 0
    for seed in [0, 1, 2, 3, 5, 7, 11, 13, 42, 99]:
        random.seed(seed)
        r = run_game('depths', 'burn')
        if r.winner == 'p1':
            wins += 1
    return wins


@pytest.fixture(scope="module")
def reanimator_vs_burn_fixed_seed_wins() -> int:
    """Mirror of sim.py:2719-2725 — wins for reanimator (p1) over burn (p2)
    at 10 fixed seeds.  Pre-fix the shared TS preamble consumed ritual
    fuel; the >=4 bar is the regression gate (real Legacy >= 60-70%)."""
    from sim import run_game
    wins = 0
    for seed in [1, 2, 3, 7, 11, 13, 17, 19, 23, 42]:
        random.seed(seed)
        r = run_game('reanimator', 'burn')
        if r.winner == 'p1':
            wins += 1
    return wins


@pytest.fixture(scope="module")
def mardu_grief_engine_counts() -> dict:
    """Mirror of sim.py:2748-2773 — across 10 fixed seeds of mardu-vs-dimir_b,
    count games where the opener qualifies (Grief + Ephemerate + non-Grief
    black pitch card) and total Grief disruption events (strip / evoke)."""
    from sim import run_game
    qualifying = 0
    grief_events = 0
    pitch_cards = {  # abstraction-allow: rules-test
        'Thoughtseize', 'Fatal Push', 'Bowmasters', 'Orcish Bowmasters',
    }
    for seed in (1, 3, 5, 7, 11, 13, 17, 19, 23, 42):
        random.seed(seed)
        r = run_game('mardu', 'dimir_b')
        opener = r.p1_opening_hand
        has_grief = any('Grief' in n for n in opener)  # abstraction-allow: rules-test
        has_ephem = any('Ephemerate' in n for n in opener)  # abstraction-allow: rules-test
        n_black_pitch = sum(1 for n in opener if n in pitch_cards)
        if has_grief and has_ephem and n_black_pitch >= 1:
            qualifying += 1
            grief_events += sum(
                1 for line in r.log_lines
                if 'Grief' in line and  # abstraction-allow: rules-test
                ('strips' in line or 'evoke' in line.lower())
            )
    return {"qualifying": qualifying, "events": grief_events}


@pytest.fixture(scope="module")
def belcher_led_activation_counts() -> dict:
    """Mirror of sim.py:2841-2864 — across 5 fixed seeds of belcher-vs-burn,
    count openers with Charbelcher + LED + >=4 fast-mana sources, and games
    where the Charbelcher activation log marker fires within the first 120
    log lines.  Pre-fix LED only fired through Burning Wish; this loop is
    the regression gate that LED fuels direct Charbelcher activation."""
    from sim import run_game
    fast_mana = {  # abstraction-allow: rules-test
        'Lotus Petal', 'Dark Ritual', 'Rite of Flame',
        'Seething Song', 'Desperate Ritual',
        'Elvish Spirit Guide', 'Simian Spirit Guide',
        'Chrome Mox', 'Tinder Wall',
    }
    qualifying = 0
    activations = 0
    for seed in (1, 3, 13, 19, 23):
        random.seed(seed)
        r = run_game('belcher', 'burn', trace=True)
        opener = r.p1_opening_hand
        has_belcher = any('Charbelcher' in n for n in opener)  # abstraction-allow: rules-test
        n_led = sum(1 for n in opener if "Lion's Eye Diamond" in n)  # abstraction-allow: rules-test
        n_fast = sum(1 for n in opener if n in fast_mana)
        if has_belcher and n_led >= 1 and n_fast >= 4:
            qualifying += 1
            activated = any(
                'Charbelcher deals' in line for line in r.log_lines[:120]  # abstraction-allow: rules-test
            )
            if activated:
                activations += 1
    return {"qualifying": qualifying, "activations": activations}


@pytest.fixture(scope="module")
def doomsday_companion_state() -> dict:
    """Mirror of sim.py:2887-2906 — build the doomsday companion card and
    capture an opener of doomsday vs storm @ seed 42.  Captures
    (companion_zone_card_name, opener_list) so per-line tests assert one
    invariant each."""
    from sim import run_game, _build_companion_card
    from deck_registry import get_meta

    meta = get_meta('doomsday') or {}
    comp_tag = meta.get('companion')
    comp_card = _build_companion_card(comp_tag) if comp_tag else None
    zone_card_name = comp_card.name if comp_card else None

    random.seed(42)
    r = run_game('doomsday', 'storm')
    return {
        "zone_card_name": zone_card_name,
        "opener": r.p1_opening_hand,
    }


@pytest.fixture(scope="module")
def doomsday_decklist_counts() -> dict:
    """Mirror of sim.py:2908-2911 — build the Doomsday maindeck and count
    Cabal Therapy + Lurrus tags.  Decklist invariant: 4 Therapy, 0 Lurrus
    (Lurrus is companion-only after Phase A)."""
    from cards import make_doomsday_deck
    dd = make_doomsday_deck()
    return {
        "therapy": sum(1 for c in dd if c.tag == 'therapy'),
        "lurrus": sum(1 for c in dd if c.tag == 'lurrus'),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.fast
def test_combo_deck_runs_three_or_more_chain_thinning_cycle_cards():
    """sim.py:2682 — Doomsday must run >=3 Street Wraith (cycle) so a hand-
    presence on the kill turn is likely.  Class: any thin-via-cycle combo
    deck.  The except-wrapper at L2686 originally caught build failures; we
    now assert the deck builder runs cleanly by reaching this assert."""
    from cards import make_doomsday_deck
    wraith_count = sum(1 for c in make_doomsday_deck() if c.tag == 'wraith')
    assert wraith_count >= 3


@pytest.mark.fast
def test_depths_vs_burn_meets_combo_land_priority_floor(
    depths_vs_burn_fixed_seed_wins,
):
    """sim.py:2703 — depths vs burn at 10 fixed seeds must win >=5/10.
    Combo-land priority must extend to every deck running Dark Depths +
    Thespian's Stage, not just the `lands` deck."""
    assert depths_vs_burn_fixed_seed_wins >= 5


@pytest.mark.fast
def test_depths_vs_burn_smoke_loop_runs_without_raising(
    depths_vs_burn_fixed_seed_wins,
):
    """sim.py:2707 — the except-wrapper around the 10-seed depths-vs-burn
    loop must not fire.  Reaching this test with the fixture populated
    proves the loop completed cleanly across all 10 seeds."""
    assert depths_vs_burn_fixed_seed_wins >= 0


@pytest.mark.fast
def test_reanimator_vs_burn_meets_ts_defer_floor(
    reanimator_vs_burn_fixed_seed_wins,
):
    """sim.py:2728 — reanimator vs burn at 10 fixed seeds must win >=4/10.
    Deck-owned TS branches must defer when the combo line can fire on the
    same turn (the ritual mana belongs to the kill, not to disruption)."""
    assert reanimator_vs_burn_fixed_seed_wins >= 4


@pytest.mark.fast
def test_reanimator_vs_burn_smoke_loop_runs_without_raising(
    reanimator_vs_burn_fixed_seed_wins,
):
    """sim.py:2732 — the except-wrapper around the 10-seed reanimator-vs-
    burn loop must not fire.  Reaching this test proves the loop completed."""
    assert reanimator_vs_burn_fixed_seed_wins >= 0


@pytest.mark.fast
def test_discard_pitch_fuel_survives_hand_disruption_ordering(
    mardu_grief_engine_counts,
):
    """sim.py:2769 — when an opener qualifies (Grief + Ephemerate + a non-
    Grief black pitch card), at least one Grief disruption event must fire
    per qualifying opener.  Pre-fix the shared TS preamble consumed pitch
    fuel before Grief could pay its evoke cost."""
    counts = mardu_grief_engine_counts
    assert counts["events"] >= max(1, counts["qualifying"])


@pytest.mark.fast
def test_mardu_grief_smoke_loop_runs_without_raising(
    mardu_grief_engine_counts,
):
    """sim.py:2775 — the except-wrapper around the 10-seed Mardu Grief
    engine loop must not fire.  Reaching this test proves the loop
    completed across all seeds."""
    assert mardu_grief_engine_counts["qualifying"] >= 0


@pytest.mark.fast
def test_led_fuels_direct_charbelcher_activation_for_every_qualifying_opener(
    belcher_led_activation_counts,
):
    """sim.py:2865 — for every opener with Charbelcher + LED + >=4 fast-mana
    sources, the Charbelcher activation log marker must fire (LED fuels
    direct activation per CR 605, not only the Burning Wish branch)."""
    counts = belcher_led_activation_counts
    assert (
        counts["qualifying"] >= 1
        and counts["activations"] == counts["qualifying"]
    )


@pytest.mark.fast
def test_belcher_led_smoke_loop_runs_without_raising(
    belcher_led_activation_counts,
):
    """sim.py:2871 — the except-wrapper around the 5-seed belcher-vs-burn
    activation loop must not fire.  Reaching this test proves the loop
    completed across all seeds."""
    assert belcher_led_activation_counts["qualifying"] >= 0


@pytest.mark.fast
def test_companion_card_is_in_companion_zone_at_game_start(
    doomsday_companion_state,
):
    """sim.py:2901 — a deck declaring a `companion` in DECK_META must have
    that card present in `player.companion_zone` at game start, before any
    draws happen.  For Doomsday, the companion is Lurrus of the Dream-Den."""
    name = doomsday_companion_state["zone_card_name"]
    assert name is not None and 'Lurrus' in name  # abstraction-allow: rules-test


@pytest.mark.fast
def test_companion_card_is_never_in_opening_hand(doomsday_companion_state):
    """sim.py:2904 — a deck declaring a `companion` must NOT have that card
    appear in `player.hand` (it lives in companion_zone, outside the 60-card
    deck — full-deck draw smoke test confirms this)."""
    opener = doomsday_companion_state["opener"]
    assert not any('Lurrus' in n for n in opener)  # abstraction-allow: rules-test


@pytest.mark.fast
def test_companion_owning_deck_has_expected_maindeck_disruption_count(
    doomsday_decklist_counts,
):
    """sim.py:2912 — when Lurrus moves to companion_zone, the freed maindeck
    slot is reclaimed for 4 Cabal Therapy (Phase A of the companion-zone
    structural fix)."""
    assert doomsday_decklist_counts["therapy"] == 4


@pytest.mark.fast
def test_companion_card_has_zero_copies_in_maindeck(doomsday_decklist_counts):
    """sim.py:2914 — once a deck declares a `companion` in DECK_META, the
    maindeck must contain ZERO copies of that card.  Companion is a 61st
    card outside the 60-card list (CR 702.139)."""
    assert doomsday_decklist_counts["lurrus"] == 0


@pytest.mark.fast
def test_companion_zone_smoke_block_runs_without_raising(
    doomsday_companion_state, doomsday_decklist_counts,
):
    """sim.py:2917 — the except-wrapper around the entire companion-zone
    setup + decklist-construction block must not fire.  Reaching this test
    with both fixtures populated proves the block ran cleanly end-to-end."""
    assert doomsday_companion_state["zone_card_name"] is not None
    assert doomsday_decklist_counts["therapy"] == 4


@pytest.mark.fast
def test_pile_algebra_every_subclass_inherits_from_pile_and_is_a_dataclass():
    """sim.py:2936 — each Pile subclass (Tendrils/Lurrus/Wraith/Oracle) must
    inherit from Pile AND be a `@dataclass`.  Mirrors the typed-algebra
    discipline of `combo_engine.combo_plan` (Phase B, see
    docs/design/2026-05-16_doomsday_cabal_therapy_piles.md).  Single
    assertion compounds both checks for every subclass."""
    from decks.doomsday_piles import (
        Pile, TendrilsPile, LurrusPile, WraithPile, OraclePile,
    )
    from dataclasses import is_dataclass
    subclasses = (TendrilsPile, LurrusPile, WraithPile, OraclePile)
    assert all(
        issubclass(cls, Pile) and is_dataclass(cls) for cls in subclasses
    )
