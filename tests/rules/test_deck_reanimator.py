"""Migrated rules tests for the reanimator-combo branch of combo_plan().

Source: sim.py:run_rules_tests() lines 3492-3495 (Branch 5 — reanimator + all
pieces present + sufficient mana → Execute).

The mechanic under test is the combo-engine planner's "reanimate target from
graveyard + cast trigger in hand + mana available" path. The planner should
return an Execute plan whose reason mentions the combo.
"""
from __future__ import annotations

import pytest

import combo_engine as _cep
from cards import DECKS
from game import GameState, PlayerState


@pytest.fixture
def reanimator_execute_plan():
    """Build the Branch-5 scenario and return the resulting plan.

    Mirrors sim.py:3437-3491:
      - p1 hand holds the reanimate trigger + a dark ritual
      - p1 graveyard holds the reanimation target (big creature)
      - p1_deck='reanimator', p2_deck='burn' (low-threat opp), mana=1, turn=2
    """
    rean_cards = DECKS['reanimator']()
    reanimate = next((c for c in rean_cards if c.tag == 'reanimate'), None)
    darkrit   = next((c for c in rean_cards if c.tag == 'darkrit'),  None)
    gris      = next((c for c in rean_cards if c.tag == 'gris'),     None)
    # The original test was gated on all three tags being present; if the deck
    # ever stops shipping one of them, fail loud rather than silently skip.
    assert reanimate and darkrit and gris, \
        "reanimator deck must expose 'reanimate', 'darkrit', 'gris' tags"

    p1 = PlayerState(name='p1', hand=[reanimate, darkrit], library=[])
    p1.graveyard = [gris]
    p2 = PlayerState(name='p2', hand=[], library=[])
    gs = GameState(p1=p1, p2=p2, p1_deck='reanimator', p2_deck='burn')
    gs.turn = 2
    gs._executing_mana = 1  # one mana available for casting (ritual covers rest)
    return _cep.combo_plan(p1, p2, gs)


@pytest.mark.fast
def test_combo_plan_returns_execute_when_reanimate_pieces_target_and_mana_present(
    reanimator_execute_plan,
):
    """Trigger + target + mana → planner commits to Execute (sim.py:3492)."""
    assert isinstance(reanimator_execute_plan, _cep.Execute)


@pytest.mark.fast
def test_combo_plan_execute_reason_mentions_combo(reanimator_execute_plan):
    """Execute.reason must surface the 'combo' keyword (sim.py:3495)."""
    assert 'combo' in reanimator_execute_plan.reason.lower()
