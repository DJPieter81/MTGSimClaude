"""Rules tests migrated from sim.py:run_rules_tests() lines 4569-4829.

Decision-algebra continuation: ManaDecision (ramp axis), CombatDecision
(block / hold gameability), parallel-sweep / meta-matrix parity bounds,
and MetaDecision (play_around) wiring.

Headers covered (mechanic-named):
- Rule M1:   ManaDecision(ramp, N).to_token() byte-equality.
- Rule M2:   typed ManaDecision(ramp) list bumps counts['ramp'].
- Rule M3:   legacy 'mana_ramp_*' dict token also buckets to ramp.
- Rule M4:   combo win + ≥ K_RAMP_A ramp tokens grades mana=A.
- Rule M5:   non-combo win with 0 ramp tokens still grades mana ≥ B.
- Rule M6:   prose 'ritual cabal dark mana' with chosen='pass' does
              NOT raise counts['ramp'] (gameability resistance).
- Rule CB6:  prose 'block hold defend' with chosen='pass' does NOT
              raise counts['combat'] (gameability resistance).
- Rule CB7:  legacy 'hold_<tag>' with phase='combat' buckets to combat
              only (not combo hold) — HOLD_PREFIXES collision guard.
- Parity:    run_sweep parallel vs serial within 2 σ binomial bound.
- Parity:    run_sweep parity setup completes without raising.
- Parity:    run_meta_matrix parallel vs serial within 2 σ per cell.
- Parity:    run_meta_matrix parity setup completes without raising.
- PR #160:   MetaDecision(play_around).to_token() byte-equality.
- PR #160:   typed MetaDecision raises counts['meta'].
- PR #160:   legacy 'meta_*' dict token raises counts['meta'].
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import pytest

# Make repo-root and scripts/ importable (mirrors sim.run_rules_tests setup).
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import structural_grader as _sg  # noqa: E402
from decision import (  # noqa: E402
    CombatDecision,
    ManaDecision,
    MetaDecision,
)
from sim import run_meta_matrix, run_sweep  # noqa: E402


# ── Grade-string ordering (mirrors sim.py _GS) ────────────────────────────
_GRADE_ORDER = ["A+", "A", "B+", "B", "C+", "C", "D", "F"]
_GRADE_IDX = {g: i for i, g in enumerate(_GRADE_ORDER)}


def _parity_tol(n: int) -> int:
    """Source's `_parity_tol`: max(2, ⌈2·sqrt(N/2)⌉) — 2 σ binomial @ p=0.5."""
    return max(2, int(math.ceil(2 * math.sqrt(n / 2))))


# ── Module-level fixtures: shared typed-Decision setups. ──────────────────


@pytest.fixture(scope="module")
def typed_ramp_counts():
    """Rule M2: two typed ManaDecision(ramp) for deck1='storm'."""
    typed = [
        ManaDecision(turn=1, deck="storm", kind="ramp", mana_value=1),
        ManaDecision(turn=2, deck="storm", kind="ramp", mana_value=2),
    ]
    return _sg._count_structural(typed, deck1="storm")


@pytest.fixture(scope="module")
def legacy_ramp_counts():
    """Rule M3: legacy 'mana_ramp_*' dict tokens for deck1='storm'."""
    legacy = [
        {"turn": 1, "deck": "storm", "chosen": "mana_ramp_2"},
        {"turn": 2, "deck": "storm", "chosen": "mana_ramp_3"},
    ]
    return _sg._count_structural(legacy, deck1="storm")


@pytest.fixture(scope="module")
def ramp_combo_win_grade():
    """Rule M4: combo win + 4 typed ramp tokens → _grade_mana()."""
    decisions = [
        ManaDecision(turn=1, deck="storm", kind="ramp", mana_value=1),
        ManaDecision(turn=2, deck="storm", kind="ramp", mana_value=2),
        ManaDecision(turn=2, deck="storm", kind="ramp", mana_value=2),
        ManaDecision(turn=2, deck="storm", kind="ramp", mana_value=3),
    ]
    trace = {
        "deck1": "storm", "deck2": "dnt", "winner": "p1",
        "game_length": 2, "p1_mulls": 0,
        "strategic_decisions": decisions,
    }
    counts = _sg._count_structural(decisions, deck1="storm")
    grade, _just = _sg._grade_mana(trace, counts)
    return grade


@pytest.fixture(scope="module")
def combat_no_ramp_grade():
    """Rule M5: combat-deck win, 0 ramp tokens → _grade_mana()."""
    trace = {
        "deck1": "goblins", "deck2": "uwx", "winner": "p1",
        "game_length": 6, "p1_mulls": 0,
        "strategic_decisions": [],
    }
    counts = _sg._count_structural([], deck1="goblins")
    grade, _just = _sg._grade_mana(trace, counts)
    return grade


@pytest.fixture(scope="module")
def prose_ramp_counts():
    """Rule M6: prose-only ramp keywords with chosen='pass'."""
    adversarial = [
        {"turn": 1, "deck": "storm", "chosen": "pass", "candidates": [],
         "reason": "ritual cabal dark mana led petal"},
        {"turn": 2, "deck": "storm", "chosen": "pass", "candidates": [],
         "reason": "dark ritual cabal ritual led led mana ramp"},
    ]
    return _sg._count_structural(adversarial, deck1="storm")


@pytest.fixture(scope="module")
def prose_combat_counts():
    """Rule CB6: prose-only combat keywords with chosen='pass'."""
    prose = [
        {"turn": 2, "deck": "bug", "chosen": "pass", "candidates": [],
         "reason": "block hold defend murktide back to block",
         "phase": "main"},
        {"turn": 3, "deck": "bug", "chosen": "pass", "candidates": [],
         "reason": "considered block + hold tamiyo",
         "phase": "main"},
    ]
    return _sg._count_structural(prose, deck1="bug")


@pytest.fixture(scope="module")
def combat_hold_dict_counts():
    """Rule CB7: legacy 'hold_<tag>' with phase='combat'."""
    entry = [
        {"turn": 3, "deck": "bug",
         "chosen": "hold_murktide",  # abstraction-allow: rules-test
         "candidates": ["attack", "hold"],
         "reason": "hold to block",
         "phase": "combat"},
    ]
    return _sg._count_structural(entry, deck1="bug")


# ── Parallel-parity fixtures: run once, share across two assertions each. ─


@pytest.fixture(scope="module")
def sweep_parity_result():
    """run_sweep parallel vs serial at N=60 for storm/burn @ seed 2026.

    Mirrors the sim.py try/except guard: returns (par_wins, ser_wins, error).
    If the call raises, both assertions surface the error explicitly.
    """
    n = 60
    par_wins = ser_wins = None
    error = None
    try:
        random.seed(2026)
        par = run_sweep("storm", "burn", n_games=n, parallel=True)
        random.seed(2026)
        ser = run_sweep("storm", "burn", n_games=n, parallel=False)
        par_wins = par["p1_wins"]
        ser_wins = ser["p1_wins"]
    except Exception as e:  # pragma: no cover - guards CI noise
        error = e
    return {"n": n, "par_wins": par_wins, "ser_wins": ser_wins, "error": error}


@pytest.fixture(scope="module")
def matrix_parity_result():
    """run_meta_matrix parallel vs serial on a 4-deck subset, N=30.

    Returns per-cell delta-list plus the error sentinel.
    """
    subset = ["storm", "burn", "dimir", "bug"]
    n = 30
    error = None
    bad = None
    try:
        random.seed(2026)
        par_m = run_meta_matrix(decks=subset, n_games=n, parallel=True)
        random.seed(2026)
        ser_m = run_meta_matrix(decks=subset, n_games=n, parallel=False)
        cell_tol = _parity_tol(n)
        bad = []
        for key in par_m:
            pw = round(par_m[key] * n)
            sw = round(ser_m[key] * n)
            if abs(pw - sw) > cell_tol:
                bad.append((key, pw, sw))
    except Exception as e:  # pragma: no cover
        error = e
    return {"n": n, "bad": bad, "error": error}


# ── Rule M1 — ManaDecision.to_token() byte-equality (mana_value=3) ────────


@pytest.mark.fast
def test_mana_decision_ramp_to_token_format_value_3():
    """L4569: ManaDecision(ramp, 3).to_token() == 'mana_ramp_3'."""
    md = ManaDecision(turn=1, deck="storm", kind="ramp", mana_value=3)
    assert md.to_token() == "mana_ramp_3"


# ── Rule M2 — typed-path bucketing increments counts['ramp']. ─────────────


@pytest.mark.fast
def test_typed_mana_decisions_bucket_into_ramp(typed_ramp_counts):
    """L4581: two typed ManaDecision(ramp) → counts['ramp'] == 2."""
    assert typed_ramp_counts["ramp"] == 2


# ── Rule M3 — legacy dict 'mana_ramp_*' tokens also bucket to ramp. ───────


@pytest.mark.fast
def test_legacy_mana_ramp_dict_tokens_bucket_into_ramp(legacy_ramp_counts):
    """L4593: legacy 'mana_ramp_<N>' chosen strings → counts['ramp'] == 2."""
    assert legacy_ramp_counts["ramp"] == 2


# ── Rule M4 — combo win + ≥ K_RAMP_A ramp tokens grades mana=A. ───────────


@pytest.mark.fast
def test_combo_win_with_four_ramp_tokens_grades_mana_a(ramp_combo_win_grade):
    """L4612: combo win + 4 ramp tokens → _grade_mana() returns 'A'."""
    assert ramp_combo_win_grade == "A"


# ── Rule M5 — non-combo deck win with 0 ramp tokens still grades ≥ B. ─────


@pytest.mark.fast
def test_combat_deck_win_without_ramp_tokens_grades_mana_at_least_b(
    combat_no_ramp_grade,
):
    """L4628: combat-deck win + 0 ramp tokens → mana grade index ≤ B."""
    idx = _GRADE_IDX.get(combat_no_ramp_grade, 99)
    assert idx <= _GRADE_IDX["B"]


# ── Rule M6 — prose 'ritual cabal dark mana' must NOT raise ramp. ─────────


@pytest.mark.fast
def test_prose_ramp_keywords_with_pass_chosen_do_not_raise_ramp(
    prose_ramp_counts,
):
    """L4642: prose 'ritual cabal dark mana' + chosen='pass' → ramp == 0."""
    assert prose_ramp_counts["ramp"] == 0


# ── Rule CB6 — prose 'block hold defend' must NOT raise combat. ───────────


@pytest.mark.fast
def test_prose_combat_keywords_with_pass_chosen_do_not_raise_combat(
    prose_combat_counts,
):
    """L4714: prose 'block hold defend' + chosen='pass' → combat == 0."""
    assert prose_combat_counts["combat"] == 0


# ── Rule CB7 — legacy hold_<tag> with phase='combat' → combat only. ───────


@pytest.mark.fast
def test_legacy_hold_token_with_combat_phase_buckets_to_combat_only(
    combat_hold_dict_counts,
):
    """L4728: legacy 'hold_<tag>' phase='combat' → (combat=1, hold=0)."""
    assert (
        combat_hold_dict_counts["combat"],
        combat_hold_dict_counts["hold"],
    ) == (1, 0)


# ── Parallel parity — run_sweep parallel vs serial. ───────────────────────


@pytest.mark.fast
def test_run_sweep_parallel_matches_serial_within_binomial_bound(
    sweep_parity_result,
):
    """L4769: |par_wins − ser_wins| ≤ ⌈2·sqrt(N/2)⌉ for N=60."""
    assert sweep_parity_result["error"] is None, (
        f"setup raised: {sweep_parity_result['error']}"
    )
    n = sweep_parity_result["n"]
    delta = abs(sweep_parity_result["par_wins"] - sweep_parity_result["ser_wins"])
    assert delta <= _parity_tol(n), (
        f"par={sweep_parity_result['par_wins']} ser={sweep_parity_result['ser_wins']}"
    )


@pytest.mark.fast
def test_run_sweep_parallel_parity_setup_does_not_raise(sweep_parity_result):
    """L4773: source guards the parity block with `except Exception` —
    pin the no-exception invariant explicitly."""
    assert sweep_parity_result["error"] is None


# ── Parallel parity — run_meta_matrix parallel vs serial. ─────────────────


@pytest.mark.fast
def test_run_meta_matrix_parallel_matches_serial_within_per_cell_bound(
    matrix_parity_result,
):
    """L4793: every cell satisfies |par_wins − ser_wins| ≤ _parity_tol(N)."""
    assert matrix_parity_result["error"] is None, (
        f"setup raised: {matrix_parity_result['error']}"
    )
    assert len(matrix_parity_result["bad"]) == 0, (
        f"bad cells: {matrix_parity_result['bad'][:3]}"
    )


@pytest.mark.fast
def test_run_meta_matrix_parallel_parity_setup_does_not_raise(
    matrix_parity_result,
):
    """L4798: source guards the matrix-parity block with `except Exception`;
    pin the no-exception invariant explicitly."""
    assert matrix_parity_result["error"] is None


# ── PR #160 — MetaDecision (play_around) algebra. ─────────────────────────


@pytest.mark.fast
def test_meta_decision_play_around_to_token_format():
    """L4815: MetaDecision(play_around, 'fow').to_token() byte-equality."""
    md = MetaDecision(
        turn=1, deck="storm", phase="meta",
        kind="play_around", threat_tag="fow",
    )
    assert md.to_token() == "meta_play_around_fow"


@pytest.mark.fast
def test_typed_meta_decision_buckets_into_meta_count():
    """L4820: typed MetaDecision → counts['meta'] == 1."""
    md = MetaDecision(
        turn=1, deck="storm", phase="meta",
        kind="play_around", threat_tag="fow",
    )
    counts = _sg._count_structural([md], deck1="storm")
    assert counts["meta"] == 1


@pytest.mark.fast
def test_legacy_meta_play_around_dict_token_buckets_into_meta():
    """L4829: legacy 'meta_play_around_*' chosen string → counts['meta'] == 1."""
    entry = {
        "turn": 1, "deck": "storm", "phase": "meta",
        "chosen": "meta_play_around_daze",
        "candidates": ["execute", "play_around"],
        "reason": "opp has daze up",
    }
    counts = _sg._count_structural([entry], deck1="storm")
    assert counts["meta"] == 1
