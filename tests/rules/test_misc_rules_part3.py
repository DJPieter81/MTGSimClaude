"""Migration stub for ticket: misc_rules_part3.

Source: sim.py:run_rules_tests() lines 2686-2936
Test count: 15
Headers covered:
- L2686: (≥3) to make a hand-presence on the kill turn likely.
- L2703: a regression pulls the matchup back below ~50%.
- L2707: a regression pulls the matchup back below ~50%.
- L2728: Pre-fix the sim was 0-2/10. Set bar at ≥4/10 to catch regressions.
- L2732: Pre-fix the sim was 0-2/10. Set bar at ≥4/10 to catch regressions.
- L2769: Pre-fix the count was 0 (TS preamble consumed pitch fuel every game).
- L2775: Pre-fix the count was 0 (TS preamble consumed pitch fuel every game).
- L2865: canonical activation marker.
- L2871: canonical activation marker.
- L2901: Smoke-test the opener does not contain Lurrus (full deck draw).
- L2904: Smoke-test the opener does not contain Lurrus (full deck draw).
- L2912: Also assert deck construction has exactly 4 Cabal Therapy and 0 Lurrus
- L2914: Also assert deck construction has exactly 4 Cabal Therapy and 0 Lurrus
- L2917: Also assert deck construction has exactly 4 Cabal Therapy and 0 Lurrus
- L2936: Each subclass must inherit from Pile.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part3")


@pytest.mark.fast
def test_placeholder_misc_rules_part3():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part3.md."""
    assert False, "stub — migrate from sim.py:2686-2936"
