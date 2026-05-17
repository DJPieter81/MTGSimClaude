"""Pytest migration for ticket: bowmasters.

Source: sim.py:run_rules_tests() lines 1976-2278
Covers:
- L1976-1977: One trigger per draw event (CR 603)
- L2137: Trigger fires N times for N-card draw spell (engine.bowmasters_triggers)
- L2154: Orc Army token is created as a real Permanent in creatures list
- L2278: Legend rule (CR 704.5j) does NOT fire on non-legendary creatures
"""
from __future__ import annotations

import pytest

from rules import Card, CardType, MTGRules, Permanent
from game import GameState, PlayerState
from cards import make_bug_deck, make_dimir_deck
from engine import bowmasters_triggers


@pytest.mark.fast
def test_one_trigger_per_card_drawn_three_draws():
    """CR 603: each draw event triggers Bowmasters once. A 3-card draw
    spell (e.g. Brainstorm) yields 3 triggers."""
    assert MTGRules.bowmasters_trigger_count(3) == 3


@pytest.mark.fast
def test_one_trigger_per_card_drawn_single_draw():
    """CR 603: a single-card draw spell (e.g. Ponder's draw) yields 1 trigger."""
    assert MTGRules.bowmasters_trigger_count(1) == 1


@pytest.mark.fast
def test_trigger_fires_n_times_when_controller_has_bowmasters_in_play():
    """engine.bowmasters_triggers logs once per draw when a Bowmasters
    permanent is on the controller's battlefield (CR 603 triggered ability)."""
    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )
    bowm_card = next(c for c in make_bug_deck() if c.tag == 'bowm')
    gs.p1.creatures.append(Permanent(card=bowm_card, controller='b'))
    log: list = []
    # 3 draws == 3 triggers (Brainstorm-shaped draw event)
    bowmasters_triggers(3, gs, log)
    assert len(log) == 3


@pytest.mark.fast
def test_orc_army_added_to_creatures_list_as_real_permanent():
    """Bowmasters' amass ability puts an Orc Army Permanent into play —
    not merely a counter on the controller's PlayerState (CR 115.2c amass)."""
    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )
    bowm_card = next((c for c in gs.p1.hand if c.tag == 'bowm'), None)
    assert bowm_card is not None, "BUG deck must contain a Bowmasters"
    gs.p1.hand.remove(bowm_card)
    bowm_perm = Permanent(card=bowm_card, controller='b', summoning_sick=False)
    gs.p1.creatures.append(bowm_perm)
    log: list = []
    bowmasters_triggers(1, gs, log)
    orc_in_creatures = any(
        p.name == 'Orc Army'  # abstraction-allow: rules-test
        for p in gs.p1.creatures
    )
    assert orc_in_creatures is True


@pytest.mark.fast
def test_legend_rule_does_not_fire_on_non_legendary_duplicates():
    """CR 704.5j: the 'legend rule' state-based action only applies to
    permanents with the legendary supertype. Two Bowmasters (non-legendary)
    must both remain on the battlefield."""
    gs = GameState(
        p1=PlayerState(name='b', hand=make_bug_deck(), library=[]),
        p2=PlayerState(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True,
    )

    def make_tagged_creature(name: str, tag: str, cmc: int) -> Permanent:
        c = Card(
            name=name, card_type=CardType.CREATURE,
            cmc=cmc, mana_cost={}, colors={'U'},
            base_power=0, base_toughness=3,
            tag=tag, gy_type='creature',
        )
        p = Permanent(card=c, controller='o')
        p.power_mod = 0
        p.toughness_mod = 0
        return p

    gs.p2.creatures = [
        make_tagged_creature('Orcish Bowmasters', 'bowm', 2),  # abstraction-allow: rules-test
        make_tagged_creature('Orcish Bowmasters', 'bowm', 2),  # abstraction-allow: rules-test
    ]
    gs.state_based_actions()
    # Both survive — legend rule (CR 704.5j) only targets legendary permanents
    assert len(gs.p2.creatures) == 2
