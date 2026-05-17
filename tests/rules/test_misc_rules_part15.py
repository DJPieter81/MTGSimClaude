"""Migration stub for ticket: misc_rules_part15.

Source: sim.py:run_rules_tests() lines 4569-4829
Test count: 15
Headers covered:
- L4569: Rule M1 — to_token() byte-equality with the legacy prefix string.
- L4581: disruption fast-path that the prior PRs wired.
- L4593: written before this PR.
- L4612: backing the kill turn.
- L4628: non-combo decks fall back to the game-length rule unchanged.
- L4642: sole source-of-truth — keyword-stuffing in `reason` does nothing.
- L4714: The bucket is sole source-of-truth.
- L4728: docstring. (Same prefix as combo hold — phase disambiguates.)
- L4769: floor for tiny N) and ⌈2·sqrt(N/2)⌉ (the 2 σ binomial bound at p=0.5).
- L4773: floor for tiny N) and ⌈2·sqrt(N/2)⌉ (the 2 σ binomial bound at p=0.5).
- L4793: under ~30 seconds while still exercising the matchup-dispatch path.
- L4798: under ~30 seconds while still exercising the matchup-dispatch path.
- L4815: 1. MetaDecision.to_token() byte-format
- L4820: 2. _count_structural increments meta bucket for typed MetaDecision
- L4829: 3. Dict-path: chosen='meta_play_around_*' also increments meta
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part15")


@pytest.mark.fast
def test_placeholder_misc_rules_part15():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part15.md."""
    assert False, "stub — migrate from sim.py:4569-4829"
