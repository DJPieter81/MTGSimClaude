"""Migration stub for ticket: deck_lands.

Source: sim.py:run_rules_tests() lines 2604-2829
Test count: 8
Headers covered:
- L2604: was hardcoded to `'lands'` for months — see lessons doc).
- L2605: was hardcoded to `'lands'` for months — see lessons doc).
- L2606: was hardcoded to `'lands'` for months — see lessons doc).
- L2607: was hardcoded to `'lands'` for months — see lessons doc).
- L2608: was hardcoded to `'lands'` for months — see lessons doc).
- L2610: was hardcoded to `'lands'` for months — see lessons doc).
- L2823: CMC-1 Grindstone with Petal alone; Monolith waits for actual lands).
- L2829: CMC-1 Grindstone with Petal alone; Monolith waits for actual lands).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket deck_lands")


@pytest.mark.fast
def test_placeholder_deck_lands():
    """Migration ticket: see docs/proposals/tickets/deck_lands.md."""
    assert False, "stub — migrate from sim.py:2604-2829"
