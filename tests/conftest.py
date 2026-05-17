"""Shared fixtures for the pytest suite.

Every test gets a freshly-seeded RNG and a clean GameState so xdist workers
can run in parallel without mutating shared globals.
"""
from __future__ import annotations

import os
import random
import sys

import pytest

# Make the repo root importable regardless of where pytest is invoked from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _isolated_rng():
    """Each test starts with a deterministic seed and restores state on exit."""
    state = random.getstate()
    random.seed(0)
    try:
        yield
    finally:
        random.setstate(state)


@pytest.fixture
def fresh_gs():
    """Default p1=bug, p2=storm GameState — cheap, no run_game()."""
    from cards import DECKS
    from game import GameState, PlayerState
    p1 = PlayerState(name="P1", library=list(DECKS["bug"]()))
    p2 = PlayerState(name="P2", library=list(DECKS["storm"]()))
    return GameState(p1=p1, p2=p2)


@pytest.fixture
def make_gs():
    """Factory: make_gs('storm', 'burn') -> GameState."""
    from cards import DECKS
    from game import GameState, PlayerState

    def _make(d1: str = "bug", d2: str = "storm"):
        return GameState(
            p1=PlayerState(name="P1", library=list(DECKS[d1]())),
            p2=PlayerState(name="P2", library=list(DECKS[d2]())),
        )

    return _make
