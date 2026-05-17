"""Migration stub for ticket: misc_rules_part13.

Source: sim.py:run_rules_tests() lines 4261-4366
Test count: 15
Headers covered:
- L4261: hardcoded literal set.
- L4278: silently without re-declaring its category in DECK_META.
- L4281: silently without re-declaring its category in DECK_META.
- L4285: silently without re-declaring its category in DECK_META.
- L4290: silently without re-declaring its category in DECK_META.
- L4317: consume both typed and string forms without divergence.
- L4323: Rule A2 — discard / remove kinds use the same template.
- L4327: Rule A2 — discard / remove kinds use the same template.
- L4333: 'combo:<path_tag>'; empty path_tag falls back to legacy 'kill_C'.
- L4336: 'combo:<path_tag>'; empty path_tag falls back to legacy 'kill_C'.
- L4342: the partial-credit token from PR #153.
- L4347: Rule A5 — ComboDecision.hold and defer match the legacy tokens.
- L4350: Rule A5 — ComboDecision.hold and defer match the legacy tokens.
- L4364: already uses (turn / deck / phase / candidates / chosen / reason).
- L4366: already uses (turn / deck / phase / candidates / chosen / reason).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part13")


@pytest.mark.fast
def test_placeholder_misc_rules_part13():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part13.md."""
    assert False, "stub — migrate from sim.py:4261-4366"
