"""Deck-construction rule audits.

Migrated from `sim.py:run_rules_tests()` lines 2157-2166. Each `test(...)`
call in that slice becomes one `def test_…` here; the two loop-based audits
are parametrized over every key in the deck registry so each registered
deck contributes one parametrize case.
"""
from __future__ import annotations

import pytest

from cards import DECKS

# Legacy minimum main-deck size (CR 100.2a). Sourced from the original
# assertion in sim.py: `len(deck) == 60`.
LEGACY_MAIN_DECK_SIZE = 60

# Non-BUG deck keys — the original loop in sim.py skips 'bug' because the
# BUG-specific assert lives on a separate line.
_NON_BUG_DECKS = sorted(k for k in DECKS.keys() if k != "bug")


@pytest.mark.fast
def test_bug_main_deck_is_legacy_legal_size():
    """sim.py:2157 — BUG main deck is exactly 60 cards."""
    bug_deck = DECKS["bug"]()
    assert len(bug_deck) == LEGACY_MAIN_DECK_SIZE


@pytest.mark.fast
@pytest.mark.parametrize("deck_key", _NON_BUG_DECKS)
def test_registered_deck_is_legacy_legal_size(deck_key):
    """sim.py:2164 — every registered non-BUG deck is exactly 60 cards."""
    deck = DECKS[deck_key]()
    assert len(deck) == LEGACY_MAIN_DECK_SIZE


@pytest.mark.fast
@pytest.mark.parametrize("deck_key", _NON_BUG_DECKS)
def test_registered_deck_builds_without_error(deck_key):
    """sim.py:2166 — every registered non-BUG deck builder runs cleanly."""
    # The original assertion fired only in the except branch; success here
    # means the builder function returned without raising.
    deck = DECKS[deck_key]()
    assert deck is not None
