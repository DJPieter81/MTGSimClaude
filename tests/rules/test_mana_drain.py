"""Mana Drain rules tests.

Mana Drain (UU instant): "Counter target spell.  At the beginning of your
next main phase, add an amount of {C} equal to that spell's mana value."

The simulator wires this through:
  * config.py — `'drain'` listed in `CounterLogic.COUNTER_TAGS`.
  * engine.try_reactive_counter — Drain branch (preferred over Counterspell
    when both available); on successful counter adds spell.cmc to the
    defender's treasure attr.
  * sim.py:686-695 — treasure attr is read at start of main, added to
    total_mana, then zeroed.

These tests pin both halves: detection (Drain is recognized as a counter)
and the bonus-mana store (treasure attr accumulates spell.cmc).
"""
from __future__ import annotations

import pytest

from game import GameState, PlayerState
from rules import Card, CardType, LandPermanent
from engine import try_reactive_counter


def _mana_drain_card() -> Card:
    return Card(
        name='Mana Drain',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=2,
        mana_cost={'U': 2},
        colors={'U'},
        tag='drain',
        gy_type='instant',
    )


def _untapped_island() -> LandPermanent:
    c = Card(
        name='Island',  # abstraction-allow: rules-test fixture
        card_type=CardType.LAND,
        cmc=0, mana_cost={}, colors=set(),
        is_basic=True, produces={'U'},
        subtypes={'Island'},
        tag='basic', gy_type='land',
    )
    perm = LandPermanent(card=c, controller='b')
    perm.tapped = False
    return perm


def _major_threat_spell(cmc: int = 4) -> Card:
    """A 4-cmc creature with win_condition=True — guarantees the major-threat
    gate in try_reactive_counter fires."""
    return Card(
        name='Test Threat',  # abstraction-allow: rules-test fixture
        card_type=CardType.CREATURE,
        cmc=cmc,
        mana_cost={'generic': cmc},
        colors=set(),
        base_power=4, base_toughness=4,
        tag='test_threat',
        gy_type='creature',
        win_condition=True,
    )


def _make_gs_with_drain_in_defender_hand(spell_cmc: int = 4) -> tuple[GameState, Card]:
    """Wire a minimal game state: caster=p1, defender=p2 with a Mana Drain
    in hand and 4 untapped Islands.  Returns (gs, the_drain_card)."""
    drain = _mana_drain_card()
    p1 = PlayerState(name='p1')
    p2 = PlayerState(name='p2')
    p2.hand = [drain, _major_threat_spell(1), _major_threat_spell(1),
               _major_threat_spell(1)]  # depth ≥ 4 — Counterspell branch needs it
    p2.lands = [_untapped_island() for _ in range(4)]
    gs = GameState(p1=p1, p2=p2)
    gs.turn = 4
    return gs, drain


# ── 1. Drain is recognized as a counter ──────────────────────────────────


@pytest.mark.fast
def test_mana_drain_tag_is_listed_in_counter_tags():
    """Drain must live in CounterLogic.COUNTER_TAGS or
    try_reactive_counter would skip it entirely on hand scan."""
    from config import CounterLogic as CL
    assert 'drain' in CL.COUNTER_TAGS


# ── 2. Drain counters the spell + stores treasure ────────────────────────


@pytest.mark.fast
def test_mana_drain_counters_major_threat_and_banks_treasure_equal_to_cmc():
    """A 4-cmc major-threat spell from the caster: defender's Mana Drain
    counters it, goes to graveyard, and p2_treasure becomes 4."""
    gs, drain = _make_gs_with_drain_in_defender_hand(spell_cmc=4)
    spell = _major_threat_spell(cmc=4)
    log: list[str] = []

    countered = try_reactive_counter(gs, caster=gs.p1, defender=gs.p2,
                                     spell_card=spell, log_list=log)

    assert countered is True
    # Drain itself moved hand → graveyard
    assert drain not in gs.p2.hand
    assert drain in gs.p2.graveyard
    # Bonus mana banked
    assert getattr(gs, 'p2_treasure', 0) == 4
    # Engine recorded which counter was used
    assert gs._last_counter_used == 'drain'


@pytest.mark.fast
def test_mana_drain_treasure_scales_with_countered_spell_cmc():
    """Drain banks exactly spell.cmc — a 6-cmc threat banks 6, not 4 (the
    drain's own cost) or 5 (off-by-one)."""
    gs, _drain = _make_gs_with_drain_in_defender_hand(spell_cmc=6)
    spell = _major_threat_spell(cmc=6)
    log: list[str] = []

    try_reactive_counter(gs, caster=gs.p1, defender=gs.p2,
                         spell_card=spell, log_list=log)

    assert getattr(gs, 'p2_treasure', 0) == 6


@pytest.mark.fast
def test_bowmasters_is_major_threat_in_non_mirror_matchup():
    """Orcish Bowmasters (tag 'bowm', flash, draw_trigger) generates ongoing
    value: 1/1 body + Orc Army token + ping-on-opp-draw.  It must be treated
    as a major threat by try_reactive_counter in ANY matchup once the
    defender has 2+ counters, not only mirror/dimir_only as previously gated.
    Counter density 2+ keeps the gate from depleting the entire suite on
    cheap creatures.
    """
    bowm = Card(
        name='Orcish Bowmasters',  # abstraction-allow: rules-test fixture
        card_type=CardType.CREATURE,
        cmc=2,
        mana_cost={'B': 1, 'generic': 1},
        colors={'B'},
        base_power=1, base_toughness=1,
        tag='bowm',
        gy_type='creature',
        flash=True,
        draw_trigger=True,
    )
    # Defender (mana_drain control) holds 2 Force of Will + blue pitch.
    p1 = PlayerState(name='p1')  # caster (mono_black)
    p2 = PlayerState(name='p2')  # defender (mana_drain)
    fow1 = Card(name='Force of Will', card_type=CardType.INSTANT,  # abstraction-allow
                cmc=5, mana_cost={'U': 1, 'generic': 4}, colors={'U'},
                tag='fow', gy_type='instant', free_cast_if_blue=True)
    # Second counter satisfies the total_counters >= 2 gate (we don't burn
    # a counter on Bowmasters unless we have backup left).
    drain = Card(name='Mana Drain', card_type=CardType.INSTANT,  # abstraction-allow
                 cmc=2, mana_cost={'U': 2}, colors={'U'},
                 tag='drain', gy_type='instant')
    bs = Card(name='Brainstorm', card_type=CardType.INSTANT,  # abstraction-allow
              cmc=1, mana_cost={'U': 1}, colors={'U'},
              tag='bs', gy_type='instant')
    p2.hand = [fow1, drain, bs, _major_threat_spell(1)]
    p2.lands = [_untapped_island() for _ in range(2)]
    gs = GameState(p1=p1, p2=p2)
    gs.turn = 3
    gs.matchup = 'mono_black'  # non-mirror, non-dimir_only matchup
    gs.p1_deck = 'mono_black'
    gs.p2_deck = 'mana_drain'
    log: list[str] = []

    countered = try_reactive_counter(gs, caster=gs.p1, defender=gs.p2,
                                     spell_card=bowm, log_list=log)

    assert countered is True, ("Bowmasters should be countered in non-mirror "
                                "matchups when defender has 2+ counters")


@pytest.mark.fast
def test_cryptic_command_counters_and_draws_a_card():
    """Cryptic Command (1UUU): counter target spell, draw a card.  Engine
    branch in try_reactive_counter fires when defender has 4+ mana, 3+
    Islands available, and 3+ cards in hand."""
    cryptic = Card(
        name='Cryptic Command',  # abstraction-allow: rules-test fixture
        card_type=CardType.INSTANT,
        cmc=4,
        mana_cost={'U': 3, 'generic': 1},
        colors={'U'},
        tag='cryptic',
        gy_type='instant',
    )
    p1 = PlayerState(name='p1')
    p2 = PlayerState(name='p2')
    p2.hand = [cryptic, _major_threat_spell(1), _major_threat_spell(1),
               _major_threat_spell(1)]
    p2.lands = [_untapped_island() for _ in range(4)]
    # Library needs a card to draw
    p2.library = [_major_threat_spell(1)]
    gs = GameState(p1=p1, p2=p2)
    gs.turn = 4
    spell = _major_threat_spell(cmc=5)
    log: list[str] = []

    pre_hand_size = len(p2.hand)
    countered = try_reactive_counter(gs, caster=gs.p1, defender=gs.p2,
                                     spell_card=spell, log_list=log)

    assert countered is True
    assert cryptic in gs.p2.graveyard
    # Hand size: pre - 1 (cryptic exit) + 1 (draw) = pre.  Plus the cantrip
    # also adds 1 from library, so net is +0 against pre.  But pre had the
    # cryptic — after cast it's gone but a new card was drawn → hand size
    # is pre_hand_size - 1 + 1 = pre_hand_size.  Library is now empty.
    assert len(gs.p2.hand) == pre_hand_size  # -1 cryptic, +1 from library
    assert len(gs.p2.library) == 0
    assert gs._last_counter_used == 'cryptic'


@pytest.mark.fast
def test_mana_drain_treasure_routes_to_correct_player_slot():
    """When p1 (not p2) holds the Drain, the treasure must land on
    p1_treasure — the engine inspects defender identity to pick the attr."""
    drain = _mana_drain_card()
    p1 = PlayerState(name='p1')
    p2 = PlayerState(name='p2')
    # Defender is p1 this time
    p1.hand = [drain, _major_threat_spell(1), _major_threat_spell(1),
               _major_threat_spell(1)]
    p1.lands = [_untapped_island() for _ in range(4)]
    gs = GameState(p1=p1, p2=p2)
    gs.turn = 4
    spell = _major_threat_spell(cmc=5)
    log: list[str] = []

    countered = try_reactive_counter(gs, caster=gs.p2, defender=gs.p1,
                                     spell_card=spell, log_list=log)

    assert countered is True
    assert getattr(gs, 'p1_treasure', 0) == 5
    # Other player's pool stayed empty
    assert getattr(gs, 'p2_treasure', 0) == 0
