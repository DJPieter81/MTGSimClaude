"""Misc rules part 2 — migrated from sim.py:2391-2682.

Covers:
- assess_board metric (board_power).
- Holistic symmetry / WR-bounds matchup balance guards (60-game sweeps).
- Sideboard plan completeness — every (protagonist, antagonist) pair in
  PROTAGONIST_SB_SWAPS must produce a legal 60-card deck.
- Bo3 smoke test — run_any_bo3 returns match_wr and game_wr.
- Combo deck composition invariants (Doomsday LED, wraith cycle count,
  spot CMC audit for Daze/Sneak Attack).
"""
from __future__ import annotations

import hashlib
import random as _ctrl_rng

import pytest


# ── Deterministic seed helper (lifted from sim.py:_det_seed) ───────────────


def _det_seed(*parts: str) -> int:
    """Stable seed across runs; mirrors sim.py:_det_seed."""
    h = hashlib.md5("|".join(parts).encode()).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def _sweep_wr(d1: str, d2: str, n: int = 60, seed_label: str | None = None) -> float:
    """Sweep returning p1 win rate. Mirrors sim.py:_sweep_wr."""
    from sim import run_game

    label = seed_label if seed_label is not None else f"{d1}|{d2}"
    seed_base = _det_seed(label)
    wins = 0
    for i in range(n):
        _ctrl_rng.seed(seed_base + i)
        r = run_game(d1, d2)
        if r.winner == 'p1':
            wins += 1
    return wins / n


# ── assess_board board_power metric ─────────────────────────────────────────


@pytest.mark.fast
def test_assess_board_reports_power_of_only_creature():
    """Mechanic: assess_board sums controller's creature power."""
    from engine import assess_board
    from game import GameState, PlayerState
    from rules import Card, CardType, Permanent

    p1 = PlayerState(name='b', hand=[], library=[], life=20)
    p2 = PlayerState(name='o', hand=[], library=[], life=20)
    gs = GameState(p1=p1, p2=p2)
    c1 = Card(  # abstraction-allow: rules-test
        name='Goyf', card_type=CardType.CREATURE, cmc=2,
        mana_cost={'G': 1, 'generic': 1}, colors={'G'}, tag='goyf',
        base_power=4, base_toughness=5,
    )
    gs.p1.creatures = [Permanent(card=c1, controller='b')]
    gs.p2.creatures = []
    _state, metrics = assess_board(gs.p1, gs.p2)
    assert metrics['board_power'] == 4


# ── Symmetry: A vs B + B vs A should sum to ~100% (paired seeds) ───────────


@pytest.mark.fast
@pytest.mark.parametrize('da,db', [
    ('burn', 'dimir'),
    ('storm', 'bug'),
    ('eldrazi', 'goblins'),
])
def test_matchup_symmetry_wr_sum_within_tolerance(da, db):
    """Mechanic: with paired seeds, sum of both directions ~= 1.0 (±0.25)."""
    pair_label = "|".join(sorted([da, db]))
    wr_ab = _sweep_wr(da, db, n=60, seed_label=pair_label)
    wr_ba = _sweep_wr(db, da, n=60, seed_label=pair_label)
    assert abs((wr_ab + wr_ba) - 1.0) <= 0.25


# ── WR bounds: no pathological 100%/0% matchups ────────────────────────────


@pytest.mark.fast
@pytest.mark.parametrize('d1,d2', [
    ('burn', 'uwx'),
    ('doomsday', 'dimir'),
    ('prison', 'dimir'),
    ('show', 'dimir'),
])
def test_matchup_win_rate_within_extremes(d1, d2):
    """Mechanic: no matchup hits 0% or 100% under 60-game sweep variance."""
    wr = _sweep_wr(d1, d2)
    assert 0.05 <= wr <= 0.95


# ── Sideboard plans: every registered plan produces a 60-card deck ─────────


@pytest.fixture(scope='module')
def _sb_plan_results():
    """Build the full set of postboard decks for every registered SB plan.
    Returns (errors, exception_or_None). Errors is a list of (p, a, len)
    triples where the postboard deck count != 60."""
    try:
        from cards import DECKS as _DECKS
        from sim import PROTAGONIST_SB_SWAPS, make_postboard_any_deck

        errors = []
        for p in PROTAGONIST_SB_SWAPS:
            if p not in _DECKS:
                continue
            for a in PROTAGONIST_SB_SWAPS[p]:
                if a not in _DECKS:
                    continue
                d = make_postboard_any_deck(p, a)
                if len(d) != 60:
                    errors.append((p, a, len(d)))
        return errors, None
    except Exception as e:
        return [], e


@pytest.mark.fast
def test_sideboard_plans_produce_60_card_decks(_sb_plan_results):
    """Mechanic: make_postboard_any_deck must always return 60 cards even
    when the plan asks to remove tags absent from the maindeck or the SB
    pool is short."""
    errors, _ = _sb_plan_results
    assert len(errors) == 0


@pytest.mark.fast
def test_sideboard_plan_check_runs_without_exception(_sb_plan_results):
    """Mechanic: the SB plan walk itself must not raise (covers missing
    decks, malformed swaps, etc.)."""
    _errors, exc = _sb_plan_results
    assert exc is None


# ── run_any_bo3 smoke test ─────────────────────────────────────────────────


@pytest.fixture(scope='module')
def _bo3_smoke_result():
    """Run a 1-match Bo3 sample; capture either the dict or the exception."""
    from sim import run_any_bo3
    try:
        return run_any_bo3('bug', 'dimir', 1), None
    except Exception as e:
        return None, e


@pytest.mark.fast
def test_run_any_bo3_result_contains_match_wr(_bo3_smoke_result):
    """Mechanic: Bo3 batch summary exposes match-level win rate."""
    r, _exc = _bo3_smoke_result
    assert ('match_wr' in r) is True


@pytest.mark.fast
def test_run_any_bo3_result_contains_game_wr(_bo3_smoke_result):
    """Mechanic: Bo3 batch summary exposes game-level win rate."""
    r, _exc = _bo3_smoke_result
    assert ('game_wr' in r) is True


@pytest.mark.fast
def test_run_any_bo3_smoke_runs_without_exception(_bo3_smoke_result):
    """Mechanic: run_any_bo3 must not raise on a minimal 1-match sample."""
    _r, exc = _bo3_smoke_result
    assert exc is None


# ── Sideboard pool / field-EV invariants ───────────────────────────────────


@pytest.mark.fast
def test_sideboard_pool_exposes_leyline_of_sanctity():
    """Mechanic: the protagonist SB pool must actually contain its enchantment
    hate copies. A stale `if 'enchantment' in dir()` guard had silently left
    the entry empty because the factory was never imported into sim."""
    from sim import _make_sb_cards
    assert len(_make_sb_cards()['leyline']) > 0


@pytest.mark.fast
def test_best_deck_for_field_resolves_default_decks_from_registry(monkeypatch):
    """Mechanic: with decks=None, best_deck_for_field enumerates the live deck
    registry, not a removed STRATEGIES global (NameError regression)."""
    import sim
    from cards import DECKS
    monkeypatch.setattr(sim, 'run_any_bo3', lambda p, a, n: {'match_wr': 0.5})
    result = sim.best_deck_for_field({'bug': 1.0}, n_per_matchup=1)
    assert {deck for deck, _ev in result} == set(DECKS)


# ── Doomsday tier-1 list invariants ────────────────────────────────────────


@pytest.fixture(scope='module')
def _doomsday_cards():
    from cards import make_doomsday_deck
    return list(make_doomsday_deck())


@pytest.mark.fast
def test_doomsday_runs_four_free_artifact_mana_rocks(_doomsday_cards):
    """Mechanic: tier-1 combo lists need 4 free-mana rocks to enable the
    same-turn win line; anything less is not a competitive build."""
    led_count = sum(1 for c in _doomsday_cards if c.tag == 'led')
    assert led_count == 4


@pytest.mark.fast
def test_doomsday_led_count_check_runs_without_exception():
    """Mechanic: deck builder import + tag-count walk must not raise."""
    from cards import make_doomsday_deck

    try:
        sum(1 for c in make_doomsday_deck() if c.tag == 'led')
        ok = True
    except Exception:
        ok = False
    assert ok is True


@pytest.mark.fast
def test_doomsday_runs_enough_cycle_cards_for_chain_reliability(_doomsday_cards):
    """Mechanic: any 'thin-via-cycle' combo deck must run >=3 cycle-cards so
    a hand-presence on the kill turn is likely."""
    wraith_count = sum(1 for c in _doomsday_cards if c.tag == 'wraith')
    assert (wraith_count >= 3) is True


# ── Card-data CMC spot audit (Daze, Sneak Attack) ──────────────────────────


@pytest.fixture(scope='module')
def _spot_cmc_audit():
    """Collect (deck, cmc) for Daze and Sneak Attack across spot-check decks."""
    from cards import DECKS

    spot_decks = ['bug', 'sneak_a', 'show', 'cephalid', 'ur_delver']
    daze_cmcs = []
    sneak_cmcs = []
    err = None
    try:
        for dn in spot_decks:
            d = DECKS[dn]()
            for c in d:
                if c.name == 'Daze':  # abstraction-allow: rules-test
                    daze_cmcs.append((dn, c.cmc))
                if c.name == 'Sneak Attack':  # abstraction-allow: rules-test
                    sneak_cmcs.append((dn, c.cmc))
    except Exception as e:
        err = e
    return daze_cmcs, sneak_cmcs, err


@pytest.mark.fast
def test_free_pitch_counter_cmc_matches_printed_cost(_spot_cmc_audit):
    """Mechanic: a free-pitch counter at {U} must have cmc=1 in every deck —
    cmc=2 silently blocks T1 free casts (pitching Island)."""
    daze_cmcs, _sneak, _err = _spot_cmc_audit
    bad = [(dn, cmc) for dn, cmc in daze_cmcs if cmc != 1]
    assert bad == []


@pytest.mark.fast
def test_three_mana_creature_cheat_cmc_matches_printed_cost(_spot_cmc_audit):
    """Mechanic: a {2}{R} creature-cheat enabler must have cmc=3 in every
    deck — cmc=4 pushes the combo turn one mana later than reality."""
    _daze, sneak_cmcs, _err = _spot_cmc_audit
    bad = [(dn, cmc) for dn, cmc in sneak_cmcs if cmc != 3]
    assert bad == []


@pytest.mark.fast
def test_free_pitch_counter_present_in_at_least_one_spot_deck(_spot_cmc_audit):
    """Mechanic: the CMC-audit spot-deck list must actually hit at least one
    Daze copy; an empty list would silently skip the prior assertion."""
    daze_cmcs, _sneak, _err = _spot_cmc_audit
    assert (len(daze_cmcs) > 0) is True


@pytest.mark.fast
def test_card_data_cmc_audit_runs_without_exception(_spot_cmc_audit):
    """Mechanic: the spot CMC audit itself must not raise."""
    _daze, _sneak, err = _spot_cmc_audit
    assert err is None
