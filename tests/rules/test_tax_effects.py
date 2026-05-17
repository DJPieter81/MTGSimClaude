"""Pytest migration for ticket: tax_effects.

Source: sim.py:run_rules_tests() lines 1987-2483
Covers tax/lock rule mechanics:

- Chalice of the Void CMC matching (printed CMC, CR 614 replacement)
- Trinisphere "all spells cost at least {3}" (CR 601.2f)
- Thalia +1 generic tax on noncreature spells (cost-increase replacement)
- Chalice X=0 blocks CMC-0 spells (mana-value match)
- Static-lock persistence: Chalice/Trinisphere/Thalia survive turn-over
  and are honored by opp_can_cast / apply_lock_effects / restore_lock_effects.

One assertion per test function. Function names describe the mechanic.
Card names appear only in test bodies (each marked abstraction-allow).
"""
from __future__ import annotations

import pytest

from rules import (
    Card,
    CardType,
    Permanent,
    LandPermanent,
    StackObject,
    StackType,
    MTGRules,
)
from game import GameState, PlayerState


# ─── Shared module-level fixtures ────────────────────────────────────────


@pytest.fixture
def trinisphere_mm():
    """GameState with Trinisphere active and a ManaManager bound to it."""
    from engine import ManaManager
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
    )
    gs.trinisphere_active = True
    gs.thalia_on_board = False
    return ManaManager(10, gs)


@pytest.fixture
def thalia_mm():
    """GameState with a Thalia creature on opponent's board (computed property)."""
    from engine import ManaManager
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
    )
    gs.trinisphere_active = False
    thalia_card = Card(
        name='Thalia',  # abstraction-allow: rules-test
        card_type=CardType.CREATURE, cmc=2,
        mana_cost={'W': 1, 'generic': 1}, colors={'W'}, tag='thalia',
        base_power=2, base_toughness=1,
    )
    gs.p2.creatures.append(Permanent(card=thalia_card, controller='o'))
    return ManaManager(10, gs)


@pytest.fixture
def static_lock_state():
    """Burn-deck Bolt + Mountain + opp PlayerState wired up.

    Yields a dict with the GameState, the spell card, the caster (p2),
    and the controller (p1) so tests can assert opp_can_cast /
    apply_lock_effects / restore_lock_effects round-trips.
    """
    from cards import DECKS
    burn = DECKS['burn']()
    bolt = next(c for c in burn if c.name == 'Lightning Bolt')  # abstraction-allow: rules-test
    mountain = next(c for c in burn if c.name == 'Mountain')  # abstraction-allow: rules-test
    p1 = PlayerState(name='b', hand=[], library=[])
    p2 = PlayerState(name='o', hand=[bolt], library=[])
    gs = GameState(p1=p1, p2=p2)
    for _ in range(3):
        p2.lands.append(LandPermanent(card=mountain, controller='o'))
    return {'gs': gs, 'bolt': bolt, 'p1': p1, 'p2': p2}


# ─── Chalice CMC check (printed CMC) — L1987-1990 ────────────────────────


@pytest.mark.fast
def test_chalice_x_equals_spell_cmc_one_counters_cmc_one():
    """CR 614 replacement: Chalice@X counters spells whose printed CMC == X."""
    bs_spell = StackObject(
        'Brainstorm',  # abstraction-allow: rules-test
        StackType.SPELL, 'o', cmc=1,
    )
    assert MTGRules.chalice_counters_spell(bs_spell, 1) is True


@pytest.mark.fast
def test_chalice_x_equals_one_does_not_counter_cmc_two_spell():
    """CR 614: Chalice@X only matches the exact mana-value (X), not higher."""
    daze_spell = StackObject(
        'Daze',  # abstraction-allow: rules-test
        StackType.SPELL, 'o', cmc=2,
    )
    assert MTGRules.chalice_counters_spell(daze_spell, 1) is False


@pytest.mark.fast
def test_chalice_x_equals_two_counters_cmc_two_spell():
    """CR 614: Chalice@X matches CMC X exactly, regardless of mana cost shape."""
    daze_spell = StackObject(
        'Daze',  # abstraction-allow: rules-test
        StackType.SPELL, 'o', cmc=2,
    )
    assert MTGRules.chalice_counters_spell(daze_spell, 2) is True


@pytest.mark.fast
def test_chalice_x_equals_one_does_not_counter_higher_cmc_spell():
    """CR 614: Chalice@1 does NOT counter a CMC-5 spell (no overshoot match)."""
    fow_spell = StackObject(
        'FoW',  # abstraction-allow: rules-test
        StackType.SPELL, 'o', cmc=5,
    )
    assert MTGRules.chalice_counters_spell(fow_spell, 1) is False


# ─── Trinisphere: all spells cost at least {3} — L2317, 2320, 2323 ───────


@pytest.mark.fast
def test_trinisphere_taxes_cmc_one_spell_up_to_three(trinisphere_mm):
    """CR 601.2f: under Trinisphere, a CMC-1 spell's effective cost is 3."""
    bolt = Card(
        name='Lightning Bolt',  # abstraction-allow: rules-test
        card_type=CardType.INSTANT, cmc=1,
        mana_cost={'R': 1}, colors={'R'}, tag='bolt',
    )
    assert trinisphere_mm.effective_cmc(bolt) == 3


@pytest.mark.fast
def test_trinisphere_taxes_cmc_zero_artifact_up_to_three(trinisphere_mm):
    """CR 601.2f: Trinisphere lifts CMC-0 artifacts (e.g. Mox-class) to 3."""
    mox = Card(
        name='Mox Diamond',  # abstraction-allow: rules-test
        card_type=CardType.ARTIFACT, cmc=0,
        mana_cost={}, colors=set(), tag='diamond',
    )
    assert trinisphere_mm.effective_cmc(mox) == 3


@pytest.mark.fast
def test_trinisphere_does_not_reduce_cmc_above_three(trinisphere_mm):
    """CR 601.2f sets a floor of 3 — it never reduces a more-expensive spell."""
    fow = Card(
        name='Force of Will',  # abstraction-allow: rules-test
        card_type=CardType.INSTANT, cmc=5,
        mana_cost={'U': 1, 'generic': 4}, colors={'U'}, tag='fow',
    )
    assert trinisphere_mm.effective_cmc(fow) == 5


# ─── Thalia +1 tax on noncreature spells — L2336, 2340 ───────────────────


@pytest.mark.fast
def test_thalia_adds_one_generic_to_noncreature_spell(thalia_mm):
    """Cost-increase: noncreature spells cost +1 generic under Thalia."""
    bolt = Card(
        name='Lightning Bolt',  # abstraction-allow: rules-test
        card_type=CardType.INSTANT, cmc=1,
        mana_cost={'R': 1}, colors={'R'}, tag='bolt',
    )
    assert thalia_mm.effective_cmc(bolt) == 2


@pytest.mark.fast
def test_thalia_does_not_tax_creature_spells(thalia_mm):
    """Thalia's tax is restricted to noncreature spells — creatures pass through."""
    guide = Card(
        name='Goblin Guide',  # abstraction-allow: rules-test
        card_type=CardType.CREATURE, cmc=1,
        mana_cost={'R': 1}, colors={'R'}, tag='guide',
        base_power=2, base_toughness=2,
    )
    assert thalia_mm.effective_cmc(guide) == 1


# ─── Chalice at X=0: blocks CMC-0 spells — L2347-2348 ────────────────────


@pytest.mark.fast
def test_chalice_x_zero_blocks_cmc_zero_spell():
    """CR 614: Chalice@0 matches and counters CMC-0 spells (the X=0 trap)."""
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
    )
    gs.chalice_x = 0
    assert gs.spell_blocked_by_chalice(0) is True


@pytest.mark.fast
def test_chalice_x_zero_does_not_block_cmc_one_spell():
    """CR 614: Chalice@0 does not catch CMC-1 spells (exact-match only)."""
    gs = GameState(
        p1=PlayerState(name='b', hand=[], library=[]),
        p2=PlayerState(name='o', hand=[], library=[]),
    )
    gs.chalice_x = 0
    assert gs.spell_blocked_by_chalice(1) is False


# ─── Static-lock persistence: Chalice@1 — L2464, 2466, 2468 ──────────────


@pytest.mark.fast
def test_chalice_active_makes_opp_can_cast_reject_matching_spell(static_lock_state):
    """opp_can_cast must honour an active Chalice@X (gs.chalice_x == spell CMC)."""
    from engine import opp_can_cast
    s = static_lock_state
    s['gs'].chalice_x = 1
    assert opp_can_cast(s['bolt'], 5, s['gs'], s['p2']) is False


@pytest.mark.fast
def test_apply_lock_effects_removes_chalice_blocked_spell_from_hand(static_lock_state):
    """apply_lock_effects pulls blocked spells out of the caster's hand
    so downstream code sees the lock as a pre-cast veto."""
    from engine import apply_lock_effects
    s = static_lock_state
    s['gs'].chalice_x = 1
    apply_lock_effects(s['gs'], s['p2'], lambda x: None)
    assert (s['bolt'] in s['p2'].hand) is False


@pytest.mark.fast
def test_restore_lock_effects_returns_blocked_spell_to_hand(static_lock_state):
    """restore_lock_effects must invert apply_lock_effects: blocked spells
    return to the caster's hand for the next turn boundary."""
    from engine import apply_lock_effects, restore_lock_effects
    s = static_lock_state
    s['gs'].chalice_x = 1
    adj = apply_lock_effects(s['gs'], s['p2'], lambda x: None)
    restore_lock_effects(s['p2'], adj)
    assert (s['bolt'] in s['p2'].hand) is True


# ─── Static-lock persistence: Trinisphere mana floor — L2472-2473 ────────


@pytest.mark.fast
def test_trinisphere_active_allows_cast_when_mana_meets_floor(static_lock_state):
    """CR 601.2f: with 3 mana available, the taxed CMC-3 cost is payable."""
    from engine import opp_can_cast
    s = static_lock_state
    s['gs'].chalice_x = None
    s['gs'].trinisphere_active = True
    assert opp_can_cast(s['bolt'], 3, s['gs'], s['p2']) is True


@pytest.mark.fast
def test_trinisphere_active_blocks_cast_below_mana_floor(static_lock_state):
    """CR 601.2f: with only 2 mana, the taxed 3-mana floor cannot be paid."""
    from engine import opp_can_cast
    s = static_lock_state
    s['gs'].chalice_x = None
    s['gs'].trinisphere_active = True
    assert opp_can_cast(s['bolt'], 2, s['gs'], s['p2']) is False


# ─── Static-lock persistence: Thalia +1 tax — L2478, 2480 ────────────────


@pytest.mark.fast
def test_thalia_in_play_allows_noncreature_cast_when_mana_covers_tax(static_lock_state):
    """Thalia +1 tax: a CMC-1 noncreature spell is castable at 2 mana."""
    from cards import DECKS
    from engine import opp_can_cast
    s = static_lock_state
    s['gs'].chalice_x = None
    s['gs'].trinisphere_active = False
    thalia = next(
        c for c in DECKS['dnt']()
        if c.name == 'Thalia, Guardian of Thraben'  # abstraction-allow: rules-test
    )
    s['p1'].creatures.append(Permanent(card=thalia, controller='b'))
    assert opp_can_cast(s['bolt'], 2, s['gs'], s['p2']) is True


@pytest.mark.fast
def test_thalia_in_play_blocks_noncreature_cast_when_mana_short_of_tax(static_lock_state):
    """Thalia +1 tax: a CMC-1 noncreature spell cannot be cast with only 1 mana."""
    from cards import DECKS
    from engine import opp_can_cast
    s = static_lock_state
    s['gs'].chalice_x = None
    s['gs'].trinisphere_active = False
    thalia = next(
        c for c in DECKS['dnt']()
        if c.name == 'Thalia, Guardian of Thraben'  # abstraction-allow: rules-test
    )
    s['p1'].creatures.append(Permanent(card=thalia, controller='b'))
    assert opp_can_cast(s['bolt'], 1, s['gs'], s['p2']) is False


# ─── Static-lock persistence setup sentinel — L2483 ──────────────────────


@pytest.mark.fast
def test_static_lock_persistence_setup_runs_without_exception():
    """The full Chalice/Trinisphere/Thalia static-lock fixture must build
    end-to-end without raising. Matches the L2483 sentinel that the original
    rules suite uses to ensure none of the upstream helpers (DECKS['burn'],
    apply_lock_effects, restore_lock_effects, opp_can_cast) regress."""
    from cards import DECKS
    from engine import opp_can_cast, apply_lock_effects, restore_lock_effects
    burn = DECKS['burn']()
    bolt = next(c for c in burn if c.name == 'Lightning Bolt')  # abstraction-allow: rules-test
    mountain = next(c for c in burn if c.name == 'Mountain')  # abstraction-allow: rules-test
    p1 = PlayerState(name='b', hand=[], library=[])
    p2 = PlayerState(name='o', hand=[bolt], library=[])
    gs = GameState(p1=p1, p2=p2)
    for _ in range(3):
        p2.lands.append(LandPermanent(card=mountain, controller='o'))
    gs.chalice_x = 1
    opp_can_cast(bolt, 5, gs, p2)
    adj = apply_lock_effects(gs, p2, lambda x: None)
    restore_lock_effects(p2, adj)
    gs.chalice_x = None
    gs.trinisphere_active = True
    opp_can_cast(bolt, 3, gs, p2)
    opp_can_cast(bolt, 2, gs, p2)
    gs.trinisphere_active = False
    thalia = next(
        c for c in DECKS['dnt']()
        if c.name == 'Thalia, Guardian of Thraben'  # abstraction-allow: rules-test
    )
    p1.creatures.append(Permanent(card=thalia, controller='b'))
    opp_can_cast(bolt, 2, gs, p2)
    opp_can_cast(bolt, 1, gs, p2)
    # Setup completed without raising — mirrors L2483 sentinel.
    assert True
