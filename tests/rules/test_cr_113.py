"""Migrated from sim.py:run_rules_tests() lines 1919-1924.

CR 113.9 — stack types: spells are counterable by counterspells; triggered
and activated abilities are not. Marit Lage (token) enters via a triggered
ability and so is not "countered" by counterspells. Wasteland's land-drop
is not on the stack and therefore not counterable.
"""
from __future__ import annotations

import pytest

from rules import StackObject, StackType, MTGRules


@pytest.fixture
def spell_obj() -> StackObject:
    # abstraction-allow: rules-test
    return StackObject("Show and Tell", StackType.SPELL, 'o', cmc=3)


@pytest.fixture
def triggered_obj() -> StackObject:
    # abstraction-allow: rules-test
    return StackObject("Marit Lage", StackType.TRIGGERED, 'o')


@pytest.fixture
def activated_obj() -> StackObject:
    # abstraction-allow: rules-test
    return StackObject("Wasteland", StackType.ACTIVATED, 'o')


@pytest.mark.fast
def test_spell_is_counterable_by_spell(spell_obj):
    # CR 113.9: a spell on the stack is counterable by counterspells.
    assert spell_obj.is_counterable_by_spell() is True


@pytest.mark.fast
def test_triggered_ability_is_not_counterable_by_spell(triggered_obj):
    # CR 113.9: triggered abilities are not spells; counterspells can't target them.
    assert triggered_obj.is_counterable_by_spell() is False


@pytest.mark.fast
def test_activated_ability_is_not_counterable_by_spell(activated_obj):
    # CR 113.9: activated abilities are not spells; counterspells can't target them.
    assert activated_obj.is_counterable_by_spell() is False


@pytest.mark.fast
def test_marit_lage_token_uses_triggered_stack_type():
    # CR 113.9: the Marit Lage token enters via Dark Depths' triggered ability.
    assert MTGRules.marit_lage_stack_type() == StackType.TRIGGERED


@pytest.mark.fast
def test_marit_lage_trigger_is_not_counterable_by_spell():
    # CR 113.9: triggered ability → not counterable by a counterspell.
    assert MTGRules.marit_lage_is_counterable() is False


@pytest.mark.fast
def test_wasteland_land_drop_is_not_counterable_by_spell():
    # CR 113.9: special action / land drop is not a spell, never on the stack
    # in a counterable way.
    assert MTGRules.wasteland_is_counterable() is False
