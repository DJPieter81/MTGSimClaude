"""Doomsday pile algebra, select_pile decision tree, Phase D/E wiring, and
Phase-0 lifted-constant invariants.

Migrated from sim.py:run_rules_tests() lines 2938-3140. Each assertion in the
source maps to exactly one pytest function below. Names describe the *mechanic*
(per the abstraction contract), not the card. The pile-name strings carry
``# abstraction-allow: rules-test`` where they appear in test setup.
"""
from __future__ import annotations

import random
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from cards import sorcery
from config import BurnLethal as BL, RaceThresholds as RT, WastelandPriority as WP
from decks.doomsday_piles import (
    LurrusPile,
    OraclePile,
    Pile,
    TendrilsPile,
    WraithPile,
    select_pile,
)
from sim import run_game


# ── shared test doubles for select_pile (pure-function inputs) ─────────────


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


def _card(tag):
    return sorcery(f'_{tag}', 1, {'generic': 1}, set(), tag=tag)


# ── Pile algebra: dataclass + frozen invariants (sim.py L2938, L2949) ──────


@pytest.mark.fast
@pytest.mark.parametrize(
    'cls', [TendrilsPile, LurrusPile, WraithPile, OraclePile]
)
def test_pile_subclasses_are_dataclasses(cls):
    """Each concrete Pile is a dataclass — mirrors combo_engine algebra."""
    assert is_dataclass(cls) is True


@pytest.mark.fast
def test_pile_instances_are_frozen_so_mutation_raises():
    """Frozen invariant prevents the shared-preamble class of bugs."""
    sample = LurrusPile(
        name='lurrus',  # abstraction-allow: rules-test
        cards=('petal', 'bs', 'wraith', 'wraith', 'wraith'),
        draws_to_win=3,
        mana_to_execute=2,
        life_floor=4,
    )
    with pytest.raises(FrozenInstanceError):
        sample.name = 'oracle'  # abstraction-allow: rules-test


# ── select_pile: pure-function decision tree (sim.py L3001-L3035) ─────────


@pytest.mark.fast
def test_select_pile_aggro_opp_at_low_life_with_lurrus_returns_lurrus_pile():
    p1 = _PSlot(
        hand=[_card('petal'), _card('bs'), _card('wraith')],
        life=8,
        companion=_card('lurrus'),
    )
    p2 = _PSlot()
    gs = _GSlot('doomsday', 'burn', p1, p2)  # abstraction-allow: rules-test
    assert isinstance(select_pile(p1, p2, gs), LurrusPile)


@pytest.mark.fast
def test_select_pile_combo_opp_returns_tendrils_pile():
    p1 = _PSlot(
        hand=[_card('led'), _card('darkrit')],
        life=18,
        companion=_card('lurrus'),
    )
    p2 = _PSlot()
    gs = _GSlot('doomsday', 'storm', p1, p2)  # abstraction-allow: rules-test
    assert isinstance(select_pile(p1, p2, gs), TendrilsPile)


@pytest.mark.fast
def test_select_pile_interaction_opp_with_led_and_brainstorm_returns_wraith_pile():
    p1 = _PSlot(
        hand=[_card('led'), _card('bs'), _card('wraith')],
        life=18,
        companion=_card('lurrus'),
    )
    p2 = _PSlot()
    gs = _GSlot('doomsday', 'dimir', p1, p2)  # abstraction-allow: rules-test
    assert isinstance(select_pile(p1, p2, gs), WraithPile)


@pytest.mark.fast
def test_select_pile_interaction_opp_without_led_falls_back_to_oracle_pile():
    p1 = _PSlot(
        hand=[_card('bs'), _card('ponder')],
        life=18,
        companion=_card('lurrus'),
    )
    p2 = _PSlot()
    gs = _GSlot('doomsday', 'uwx', p1, p2)  # abstraction-allow: rules-test
    assert isinstance(select_pile(p1, p2, gs), OraclePile)


@pytest.mark.fast
def test_select_pile_is_pure_consecutive_calls_return_same_pile_type():
    """Calling select_pile twice with the same inputs must yield the same
    Pile type — no hidden mutation of player / opponent / gs."""
    p1 = _PSlot(
        hand=[_card('bs'), _card('ponder')],
        life=18,
        companion=_card('lurrus'),
    )
    p2 = _PSlot()
    gs = _GSlot('doomsday', 'uwx', p1, p2)  # abstraction-allow: rules-test
    first = select_pile(p1, p2, gs)
    second = select_pile(p1, p2, gs)
    assert type(second) is type(first)


# ── Phase D wiring: combo:<pile>_pile token emitted on DD resolve ─────────


@pytest.mark.fast
def test_phase_d_wire_emits_combo_pile_token_when_doomsday_resolves():
    """Across a small seed sweep where DD reliably resolves vs Storm, the
    typed combo:<pile>_pile token must appear in the strategic log."""
    emitted_token = False
    seeds_with_dd = 0
    for seed in (42, 7, 99, 2026, 2024):
        random.seed(seed)
        r = run_game('doomsday', 'storm', trace=True)  # abstraction-allow: rules-test
        dd_resolves = any(
            '★ Doomsday resolves' in line for line in r.log_lines
        )
        if dd_resolves:
            seeds_with_dd += 1
            if any(
                'combo:' in line and '_pile' in line for line in r.log_lines
            ):
                emitted_token = True
                break
    assert (seeds_with_dd >= 1 and emitted_token) is True


# ── Phase E: companion-zone deploy + generalized death-rebuy ──────────────


@pytest.mark.fast
def test_phase_e_lurrus_deploys_from_companion_zone_at_least_once_over_20_seeds():
    """Lurrus must enter the battlefield at least once across 20 doomsday vs
    burn games — companion-zone path now ships the deploy reliably."""
    deploys = 0
    for seed in range(1, 21):
        random.seed(seed)
        r = run_game('doomsday', 'burn', trace=True)  # abstraction-allow: rules-test
        if any(
            'Lurrus of the Dream-Den' in line  # abstraction-allow: rules-test
            and 'lifelink' in line.lower()
            for line in r.log_lines
        ):
            deploys += 1
    assert deploys >= 1


# ── Half-life cost cannot self-kill (CR 119.5 + 704.5a) ───────────────────


@pytest.mark.fast
def test_half_life_cost_spell_never_self_kills_across_full_sweep():
    """A pay-half-life spell cannot be cast when the payment would reduce
    life to 0 (state-based action: 0 life = lose). 450-game sweep must
    show zero self-kill losses."""
    self_kills = 0
    for opp in (
        'burn', 'ur_delver', 'goblins', 'mardu', 'mono_black',
        'storm', 'dimir', 'oops', 'ur_aggro',
    ):
        for seed in range(50):
            random.seed(seed)
            r = run_game('doomsday', opp)  # abstraction-allow: rules-test
            if r.win_reason and 'self-kill' in r.win_reason.lower():
                self_kills += 1
    assert self_kills == 0


# ── Phase 0: lifted-constant mechanical invariants (sim.py L3129-L3140) ───


@pytest.mark.fast
def test_racing_ttk_threshold_is_a_positive_turn_count():
    assert RT.TTK_RACE >= 1


@pytest.mark.fast
def test_racing_ahead_requires_strictly_larger_board_power_gap_than_threat_gap():
    assert RT.BOARD_POWER_GAP > RT.THREAT_GAP


@pytest.mark.fast
def test_wasteland_combo_land_weight_outranks_any_per_colour_or_fix_bonus():
    assert WP.COMBO_LAND_WEIGHT > (
        WP.COLOUR_CUT_WEIGHT
        + WP.MANA_RITUAL_LAND_WEIGHT
        + WP.DUAL_LAND_WEIGHT
        + WP.FETCH_WEIGHT
    )


@pytest.mark.fast
def test_wasteland_colour_cut_outranks_dual_land_and_fetch_tiebreakers():
    assert WP.COLOUR_CUT_WEIGHT > WP.DUAL_LAND_WEIGHT > WP.FETCH_WEIGHT


@pytest.mark.fast
def test_burn_lethal_threshold_is_strictly_higher_when_racing_burn():
    assert BL.VS_BURN > BL.DEFAULT
