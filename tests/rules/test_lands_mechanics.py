"""Migrated rules tests for ticket: lands_mechanics.

Source: sim.py:run_rules_tests() lines 1980-4539

Covers MTG land-mechanic rules:

- Fetch lands: produce no mana when sacrificed; cost 1 life (CR 305 / fetch
  oracle).
- Wasteland (CR 305.6): activated land-destruction targets only nonbasic
  lands.
- Blood Moon (CR 614.1c — type-changing static effect): nonbasic lands
  produce only {R}.
- Back to Basics (CR 110.5b / static effect): nonbasic lands can't untap and
  therefore produce no mana when locked tapped.
- Mana budget audit: cracking a fetch must refresh the player's available
  mana count (zero before the crack, one after the dual enters untapped).
- Brainstorm fixed-card constants (3 drawn, 2 put back).
- Deck-construction invariant: Eldrazi must ship >= 4 basic lands so
  Abundant Countryside / Wasteland-immune sources actually exist.
- Structural-grader interaction signal: a land-destruction-heavy trace on an
  interaction deck win must promote the grade to 'A' (this is the
  load-bearing rule that lets Wasteland firings register as interaction).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make repo-root and scripts/ importable (mirrors sim.run_rules_tests setup
# for the structural-grader path).
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SCRIPTS = _ROOT / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rules import (  # noqa: E402
    Card,
    CardType,
    LandPermanent,
    LandType,
    MTGRules,
)


# ── Module-level fixtures: shared land permanents ────────────────────────────


@pytest.fixture
def basic_island():
    """A basic Island land permanent — produces {U}, basic-typed."""
    return LandPermanent(
        card=Card(
            name="Island",  # abstraction-allow: rules-test
            card_type=CardType.LAND, cmc=0, mana_cost={},
            colors=set(), is_basic=True, land_type=LandType.BASIC,
            produces={'U'}, gy_type='land',
        ),
        controller='o',
    )


@pytest.fixture
def underground_sea():
    """An Underground Sea dual — nonbasic, produces {U, B}."""
    return LandPermanent(
        card=Card(
            name="Underground Sea",  # abstraction-allow: rules-test
            card_type=CardType.LAND, cmc=0, mana_cost={},
            colors=set(), is_basic=False, land_type=LandType.DUAL,
            produces={'U', 'B'}, gy_type='land',
        ),
        controller='o',
    )


# ── Fetch land (CR 305) ──────────────────────────────────────────────────────


@pytest.mark.fast
def test_fetch_land_sac_produces_no_mana():
    """L1980: cracking a fetch land puts a land into play; it does NOT add mana
    to the pool. The fetch's only purpose is the search effect."""
    assert MTGRules.fetch_produces_mana() is False


@pytest.mark.fast
def test_fetch_land_sac_costs_one_life():
    """L1981: fetch land oracle: "Pay 1 life, sacrifice ~ : search …"."""
    assert MTGRules.fetch_costs_life() == 1


# ── Wasteland (CR 305.6): targets only nonbasic lands ────────────────────────


@pytest.mark.fast
def test_wasteland_cannot_target_basic_land(basic_island):
    """L2009: Wasteland's activated ability reads "target nonbasic land". A
    basic Island is not a legal target."""
    assert MTGRules.wasteland_can_target(basic_island) is False


@pytest.mark.fast
def test_wasteland_can_target_nonbasic_dual(underground_sea):
    """L2010: a nonbasic dual (Underground Sea) IS a legal Wasteland target."""
    assert MTGRules.wasteland_can_target(underground_sea) is True


# ── Blood Moon (CR 614.1c): nonbasic lands produce only {R} ──────────────────


@pytest.mark.fast
def test_blood_moon_nonbasic_produces_only_red(underground_sea):
    """L2032: under Blood Moon, every nonbasic land is treated as a Mountain
    and produces only {R}. The dual's printed colors are overwritten."""
    underground_sea.blood_moon_active = True
    assert underground_sea.effective_produces() == {'R'}


@pytest.mark.fast
def test_nonbasic_without_blood_moon_produces_printed_colors(underground_sea):
    """L2034: with Blood Moon NOT active, a dual produces its printed colors
    (Underground Sea -> {U, B}); the static effect is not always-on."""
    underground_sea.blood_moon_active = False
    assert ('U' in underground_sea.effective_produces()) is True


# ── Back to Basics (CR 614 static effect): nonbasic lands can't untap ────────


@pytest.mark.fast
def test_back_to_basics_prevents_nonbasic_untap(underground_sea):
    """L2038: Back to Basics keeps nonbasic lands tapped — they skip their
    controller's untap step."""
    underground_sea.b2b_active = True
    assert underground_sea.can_untap() is False


@pytest.mark.fast
def test_back_to_basics_locks_nonbasic_mana_production(underground_sea):
    """L2039: a nonbasic land that can't untap produces no mana (it stays
    tapped); effective_produces() must return the empty set."""
    underground_sea.b2b_active = True
    assert underground_sea.effective_produces() == set()


@pytest.mark.fast
def test_back_to_basics_does_not_affect_basic_land(basic_island):
    """L2041: Back to Basics only targets *nonbasic* lands; a basic Island
    untaps normally."""
    basic_island.b2b_active = True
    assert basic_island.can_untap() is True


# ── Mana-budget audit: fetch crack refreshes available mana ──────────────────


def _setup_fetch_budget_gs():
    """Construct a GameState where p1 controls exactly one untapped fetch and
    nothing else, then crack it. Returns (pre_fetch, post_fetch) mana counts.

    Mirrors sim.py:2197-2211. Heavy enough to share between the two pre/post
    assertions via a helper rather than re-running for each test.
    """
    from game import GameState, PlayerState as PS_
    from cards import make_bug_deck, fetch_land

    gs_budget = GameState(
        p1=PS_(name='b', hand=[], library=make_bug_deck()),
        p2=PS_(name='o', hand=[], library=[]),
        p1_goes_first=True,
    )
    fetch_c = fetch_land('Polluted Delta', ['Island', 'Swamp'])  # abstraction-allow: rules-test
    fetch_p = LandPermanent(card=fetch_c, controller='b')
    gs_budget.p1.lands.append(fetch_p)
    pre_fetch = gs_budget.p1.available_mana_count()
    gs_budget.p1.use_fetch(fetch_p)
    post_fetch = gs_budget.p1.available_mana_count()
    return pre_fetch, post_fetch


@pytest.fixture(scope='module')
def fetch_budget_counts():
    return _setup_fetch_budget_gs()


@pytest.mark.fast
def test_pre_fetch_crack_mana_budget_is_zero(fetch_budget_counts):
    """L2210: before the fetch is cracked, the controller has only the
    untapped fetch in play. Fetches tap for no mana, so the available-mana
    count is 0."""
    pre_fetch, _ = fetch_budget_counts
    assert pre_fetch == 0


@pytest.mark.fast
def test_post_fetch_crack_mana_budget_is_one(fetch_budget_counts):
    """L2211: cracking the fetch puts an untapped dual into play, lifting
    available mana from 0 to 1. This pins the budget-refresh path the engine
    relies on for same-turn casts after a fetch crack."""
    _, post_fetch = fetch_budget_counts
    assert post_fetch == 1


# ── Brainstorm constants ─────────────────────────────────────────────────────


@pytest.mark.fast
def test_brainstorm_draws_three_cards():
    """L2213: Brainstorm draws exactly 3 cards (oracle)."""
    assert MTGRules.brainstorm_draws() == 3


@pytest.mark.fast
def test_brainstorm_puts_back_two_cards():
    """L2214: Brainstorm puts exactly 2 cards back on the library (oracle)."""
    assert MTGRules.brainstorm_puts_back() == 2


# ── Deck-construction: Eldrazi must ship enough basic lands ──────────────────


@pytest.mark.fast
def test_eldrazi_deck_ships_at_least_four_basic_lands():
    """L2568: Abundant Countryside fetches a basic land; if the deck has no
    basics, every Countryside crack pays 1 life for nothing. Eldrazi must
    ship >= 4 basics (Wasteland-immune colorless mana)."""
    from cards import make_eldrazi_deck
    basics = sum(1 for c in make_eldrazi_deck() if c.is_land() and c.is_basic)
    assert (basics >= 4) is True


@pytest.mark.fast
def test_eldrazi_deck_construction_does_not_raise():
    """L2572: the legacy assertion wrapped the basics-count in try/except so a
    deck-construction crash also surfaced as a failing test. Mirror that
    invariant: building the Eldrazi deck and counting basics must complete
    without an exception."""
    from cards import make_eldrazi_deck
    try:
        _ = sum(1 for c in make_eldrazi_deck() if c.is_land() and c.is_basic)
        raised = False
    except Exception:
        raised = True
    assert raised is False


# ── Structural-grader interaction signal includes land-destruction ───────────


@pytest.mark.fast
def test_three_land_destroy_tokens_promote_interaction_deck_to_grade_a():
    """L4539: an interaction-deck winning trace with 3 land_destroy decisions
    must grade 'A'. This is the gameability-resistant path: Wasteland firings
    bucket into the interaction axis via typed DisruptionDecision objects,
    not via prose in the reason string."""
    import structural_grader as _sg2
    from decision import DisruptionDecision as _DiD

    ld3 = [
        _DiD(turn=2, deck='bug', kind='land_destroy',
             target_tag='dual', instrument_tag='wasteland'),
        _DiD(turn=3, deck='bug', kind='land_destroy',
             target_tag='dual', instrument_tag='wasteland'),
        _DiD(turn=4, deck='bug', kind='land_destroy',
             target_tag='depths', instrument_tag='wasteland'),
    ]
    ld3_counts = _sg2._count_structural(ld3, deck1='bug')
    trace_win = {'deck1': 'bug', 'winner': 'p1', 'game_length': 10}
    grade, _ = _sg2._grade_interaction(trace_win, ld3_counts)
    assert grade == 'A'
