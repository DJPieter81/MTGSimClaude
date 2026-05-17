"""Migrated rules tests for ticket: deck_depths.

Source: sim.py:run_rules_tests() lines 3700-3704
Section: Phase 5: depths deck declares combo metadata + path coverage
"""
from __future__ import annotations

import pytest

from deck_registry import get_combo_meta


@pytest.mark.fast
def test_depths_deck_declares_combo_metadata_block():
    """A combo deck registered in deck_registry must expose a combo-meta block."""
    meta = get_combo_meta('depths')  # abstraction-allow: rules-test
    assert (meta is not None) == True


@pytest.mark.fast
def test_depths_deck_declares_at_least_one_assembly_path():
    """A combo deck's metadata must enumerate at least one assembly_path."""
    meta = get_combo_meta('depths')  # abstraction-allow: rules-test
    assert meta is not None, "precondition: combo meta block exists"
    paths = meta.get('assembly_paths', ())
    assert (len(paths) >= 1) == True
