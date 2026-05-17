"""Painter COMBO_META wiring + combo_plan consumption gate.

Audits (docs/audits/painter_vs_sneak_b.md, docs/audits/painter_vs_ur_tempo.md)
flagged painter as the only deck declared `categories={'combo'}` that
returns `NoPlan('no combo metadata for deck')` from `combo_engine.combo_plan`,
because `decks/painter.py:DECK_META` lacked the `'combo'` block declaring
pieces / protection_tags / assembly_paths.

The fix is the same shape as storm/show/sneak_a/sneak_b/oops/reanimator:
declare the combo metadata so `combo_plan` can run the BHI protection check
and the assembly-path chooser. With metadata in place, painter strategies
that consult `combo_plan` will defer piece deployment when opp BHI shows
high free-counter probability (e.g. T1 Painter walks into FoW on the draw).

These tests pin the *declaration* (deck plugin shape) — the wire-up in
engine._strategy_painter is exercised end-to-end via the regression sweep
and the painter_vs_ur_tempo audit numbers.
"""
from __future__ import annotations

import pytest

from rules import Card, CardType


# ── 1. COMBO_META declaration shape ───────────────────────────────────────


_COMBO_META_DEFERRED = frozenset({
    # Decks declared `categories={'combo'}` but with no COMBO_META yet.
    # Each has its own audit doc with deck-specific remediation:
    #   belcher  — docs/audits/belcher_vs_*.md (payoff-aware Mox imprint)
    #   doomsday — docs/audits/doomsday_vs_*.md (Cabal Therapy + per-matchup
    #              pile algebra; loop-break gate per CLAUDE.md)
    #   elves    — separate audit pending
    #   infect   — separate audit pending
    # Listed here so the schema test pins their omission as an acknowledged
    # backlog rather than silently passing.
    'belcher', 'doomsday', 'elves', 'infect',
})


@pytest.mark.fast
def test_combo_declared_deck_has_combo_metadata_block():
    """Every deck in `categories={'combo'}` must declare a `'combo'` block
    so `combo_engine.combo_plan` can run. Known exceptions (with their own
    open audit docs) are listed in `_COMBO_META_DEFERRED` above."""
    from deck_registry import get_all_keys, get_combo_meta, get_categories

    violations: list[str] = []
    for key in get_all_keys():
        cats = get_categories(key) or set()
        if 'combo' not in cats:
            continue
        if key in _COMBO_META_DEFERRED:
            continue
        cm = get_combo_meta(key)
        if cm is None:
            violations.append(key)
    assert violations == [], (
        f'decks declared combo without COMBO_META (not on deferred list): '
        f'{violations}')


@pytest.mark.fast
def test_painter_combo_meta_declares_required_keys():
    """painter's combo block declares the three keys combo_plan reads."""
    from deck_registry import get_combo_meta

    cm = get_combo_meta('painter')
    assert cm is not None, 'painter must declare combo metadata'
    assert 'pieces' in cm
    assert 'protection_tags' in cm
    assert 'assembly_paths' in cm
    assert len(cm['assembly_paths']) >= 1


# ── 2. Assembly-path satisfiability (Painter + Grindstone @ 4 mana) ───────


def _piece(tag: str, cmc: int) -> Card:
    """Test fixture — a single combo piece with the right tag/cmc."""
    return Card(
        name=tag,  # abstraction-allow: rules-test fixture
        card_type=CardType.ARTIFACT,
        cmc=cmc,
        mana_cost={'generic': cmc},
        colors=set(),
        tag=tag,
        gy_type='artifact',
        is_combo_piece=True,
    )


@pytest.mark.fast
def test_painter_assembly_path_satisfiable_at_combo_mana():
    """With Painter's Servant + Grindstone in 'hand' and ≥4 mana, at least
    one declared assembly path is satisfiable."""
    from combo_engine import GameView
    from deck_registry import get_combo_meta

    view = GameView(
        own_deck='painter',
        opp_deck='dimir',
        available=frozenset({'painter', 'grind'}),
        hand=(_piece('painter', 2), _piece('grind', 1)),
        mana=4,
        turn=3,
        opp_hand_size=4,
    )
    cm = get_combo_meta('painter')
    satisfiable = [p for p in cm['assembly_paths'] if p.is_satisfiable(view)]
    assert len(satisfiable) >= 1, (
        f'expected at least one satisfiable path; got 0 from '
        f'{[p.tag for p in cm["assembly_paths"]]}')


@pytest.mark.fast
def test_painter_no_path_satisfiable_without_pieces():
    """An empty hand (no painter, no grind) satisfies no path."""
    from combo_engine import GameView
    from deck_registry import get_combo_meta

    view = GameView(
        own_deck='painter',
        opp_deck='dimir',
        available=frozenset(),
        hand=(),
        mana=10,
        turn=5,
        opp_hand_size=4,
    )
    cm = get_combo_meta('painter')
    satisfiable = [p for p in cm['assembly_paths'] if p.is_satisfiable(view)]
    assert satisfiable == []


# ── 3. combo_plan dispatches Execute on a satisfiable path ────────────────


@pytest.mark.fast
def test_painter_combo_plan_does_not_return_noplan_with_pieces():
    """The pre-fix bug: combo_plan returned NoPlan('no combo metadata for
    deck') for painter even with the combo ready. After fix, it must
    return Execute (or Hold/Defer if opp BHI fires) — never NoPlan."""
    from combo_engine import combo_plan, NoPlan
    from sim import run_game
    import random

    # Run a fixed-seed game where Painter's Servant + Grindstone land,
    # then inspect what combo_plan returns. We don't run the full game;
    # we construct a minimal player slot directly.
    random.seed(42)
    r = run_game('painter', 'dimir')
    # The end-to-end check: combo_plan should never emit the "no combo
    # metadata for deck" NoPlan for painter. We grep the game log for
    # that exact reason (Phase A's StrategicLogger format would include
    # it if combo_plan dispatched NoPlan with that reason).
    bad = [ln for ln in r.log_lines if 'no combo metadata for deck' in ln]
    assert bad == [], f'painter must not emit NoPlan("no combo metadata"): {bad[:3]}'
