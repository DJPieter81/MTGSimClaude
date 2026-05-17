"""Pitch-target selection (CR 113.9 alternative costs).

When a spell with an "exile a card of color C from hand" alternative cost
resolves (FoW/FoN, Grief/Fury/Solitude/Endurance evoke, Chrome Mox imprint),
the engine must not pitch the deck's own combo pieces, tutors, finishers, or
win conditions if any lower-value card of color C is available.

Documented bug class (`docs/audits/goblins_vs_burn.md`,
`docs/audits/mardu_vs_ur_tempo.md`): pitch pickers that take the first
matching card silently exile the deck's tutors (Goblin Matron, Goblin
Ringleader) or finishers (Sling-Gang, Muxus) as Mox/Grief/Fury fuel,
neutralising the deck's own plan.

The fix is a shared `select_pitch_target` helper that filters protected
tags + `is_combo_piece`/`win_condition` cards before selecting.
"""
from __future__ import annotations

import pytest

from rules import Card, CardType


def _make_card(name: str, tag: str, colors: set[str], *,
               is_combo_piece: bool = False, win_condition: bool = False,
               cmc: int = 2) -> Card:
    """Test fixture — a creature card with the given properties."""
    return Card(
        name=name,  # abstraction-allow: rules-test fixture
        card_type=CardType.CREATURE,
        cmc=cmc,
        mana_cost={'generic': max(cmc - len(colors), 0), **{c: 1 for c in colors}},
        colors=colors,
        tag=tag,
        gy_type='creature',
        is_combo_piece=is_combo_piece,
        win_condition=win_condition,
    )


def _mox() -> Card:
    """Chrome Mox — exiles a colored non-artifact non-land card as imprint cost."""
    return Card(
        name='Chrome Mox',  # abstraction-allow: rules-test fixture
        card_type=CardType.ARTIFACT,
        cmc=0,
        mana_cost={},
        colors=set(),
        tag='chrome_mox',
        gy_type='artifact',
    )


# ── 1. Protected-tag filtering ────────────────────────────────────────────


@pytest.mark.fast
def test_pitch_selector_skips_protected_tags():
    """Tutors and finishers in `protected_tags` are never exiled when a
    non-protected pitch candidate of the same color exists."""
    from engine import select_pitch_target

    mox = _mox()
    matron = _make_card('Goblin Matron', 'matron', {'R'})   # abstraction-allow: rules-test fixture
    crater = _make_card('Goblin Cratermaker', 'cratermaker', {'R'})  # abstraction-allow: rules-test fixture
    hand = [mox, matron, crater]

    protected = frozenset({'chrome_mox', 'matron', 'ringleader', 'muxus', 'sling'})
    picked = select_pitch_target(hand, color='R', exclude_card=mox,
                                  protected_tags=protected)
    assert picked is crater, f'expected Cratermaker, got {picked.name if picked else None}'


@pytest.mark.fast
def test_pitch_selector_skips_combo_pieces():
    """Cards flagged `is_combo_piece=True` are never pitched when a
    non-combo card of the same color is available."""
    from engine import select_pitch_target

    mox = _mox()
    muxus = _make_card('Muxus, Goblin Grandee', 'muxus', {'R'},  # abstraction-allow: rules-test fixture
                       is_combo_piece=True)
    warchief = _make_card('Goblin Warchief', 'warchief', {'R'})  # abstraction-allow: rules-test fixture
    hand = [mox, muxus, warchief]

    picked = select_pitch_target(hand, color='R', exclude_card=mox)
    assert picked is warchief, f'expected Warchief, got {picked.name if picked else None}'


@pytest.mark.fast
def test_pitch_selector_skips_win_conditions():
    """Cards flagged `win_condition=True` are never pitched if alternatives exist."""
    from engine import select_pitch_target

    fow = Card(
        name='Force of Will',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT, cmc=5,
        mana_cost={'U': 1, 'generic': 4}, colors={'U'}, tag='fow',
        gy_type='instant', free_cast_if_blue=True,
    )
    oracle = _make_card('Thassa\'s Oracle', 'oracle', {'U'},  # abstraction-allow: rules-test fixture
                        win_condition=True)
    bs = _make_card('Brainstorm', 'bs', {'U'}, cmc=1)  # abstraction-allow: rules-test fixture
    hand = [fow, oracle, bs]

    picked = select_pitch_target(hand, color='U', exclude_card=fow)
    assert picked is bs, f'expected Brainstorm, got {picked.name if picked else None}'


# ── 2. Color filtering ────────────────────────────────────────────────────


@pytest.mark.fast
def test_pitch_selector_filters_by_color():
    """Off-color cards cannot satisfy the alt cost — even if everything
    else in hand is the wrong color, helper returns None."""
    from engine import select_pitch_target

    fow = Card(name='Force of Will', card_type=CardType.INSTANT, cmc=5,  # abstraction-allow: rules-test fixture
               mana_cost={'U': 1, 'generic': 4}, colors={'U'}, tag='fow',
               gy_type='instant', free_cast_if_blue=True)
    veil = _make_card('Veil of Summer', 'veil', {'G'}, cmc=1)  # abstraction-allow: rules-test fixture
    hand = [fow, veil]

    picked = select_pitch_target(hand, color='U', exclude_card=fow)
    assert picked is None


@pytest.mark.fast
def test_pitch_selector_excludes_self():
    """The spell being cast (e.g. a second copy of Grief) is never its own pitch."""
    from engine import select_pitch_target

    grief1 = _make_card('Grief', 'grief', {'B'}, cmc=3)  # abstraction-allow: rules-test fixture
    grief2 = _make_card('Grief', 'grief', {'B'}, cmc=3)  # abstraction-allow: rules-test fixture
    hand = [grief1, grief2]

    # With protected_tags={'grief'}, picker can't pitch second Grief either.
    picked = select_pitch_target(hand, color='B', exclude_card=grief1,
                                  protected_tags=frozenset({'grief'}))
    assert picked is None


# ── 3. Fallback when only protected cards exist ───────────────────────────


@pytest.mark.fast
def test_pitch_selector_skips_combo_piece_finishers_by_flag_alone():
    """Belcher's finishers (Burning Wish, Empty the Warrens, Tendrils) carry
    `is_combo_piece=True` / `win_condition=True` on the card object. The
    helper must exclude them via flags without needing a protected-tag list
    — the audit-identified `decks/belcher.py:237` bug (Wish imprinted as
    Mox fuel) becomes impossible once the helper is wired."""
    from engine import select_pitch_target

    mox = _mox()
    wish = _make_card('Burning Wish', 'burning_wish', {'R'},  # abstraction-allow: rules-test fixture
                     is_combo_piece=True)
    empty = _make_card('Empty the Warrens', 'empty', {'R'},  # abstraction-allow: rules-test fixture
                      win_condition=True)
    rite = _make_card('Rite of Flame', 'rite', {'R'})  # abstraction-allow: rules-test fixture
    hand = [mox, wish, empty, rite]

    # No protected_tags set — flags alone must keep wish/empty out of pitch.
    picked = select_pitch_target(hand, color='R', exclude_card=mox)
    assert picked is rite, f'expected Rite of Flame, got {picked.name if picked else None}'


@pytest.mark.fast
def test_pitch_selector_returns_none_when_only_protected_cards():
    """If every same-color card is protected, helper returns None.
    Caller must decide whether to skip casting or accept the cost on a
    protected card (Grief at depths.py:6477 has the latter contract via
    the existing `_grief_protected` set + `if sum(...) >= 1` gate)."""
    from engine import select_pitch_target

    mox = _mox()
    matron = _make_card('Goblin Matron', 'matron', {'R'})  # abstraction-allow: rules-test fixture
    muxus = _make_card('Muxus, Goblin Grandee', 'muxus', {'R'},  # abstraction-allow: rules-test fixture
                       is_combo_piece=True)
    hand = [mox, matron, muxus]

    protected = frozenset({'chrome_mox', 'matron', 'ringleader', 'muxus', 'sling'})
    picked = select_pitch_target(hand, color='R', exclude_card=mox,
                                  protected_tags=protected)
    assert picked is None
