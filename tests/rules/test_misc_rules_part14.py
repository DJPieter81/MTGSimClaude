"""Migration stub for ticket: misc_rules_part14.

Source: sim.py:run_rules_tests() lines 4397-4566
Test count: 15
Headers covered:
- L4397: produces identical counts as the all-dict equivalent.
- L4399: produces identical counts as the all-dict equivalent.
- L4410: Rule A10 — typed ComboDecisions bucket to execute/hold/defer/tried_combo.
- L4433: a Decision after it's logged. FrozenInstanceError on assignment.
- L4446: list produce identical bucketing as if both were dicts.
- L4459: opponent's typed decisions don't credit deck1's grade.
- L4473: _DISRUPTION_KIND_TO_BUCKET map without grader changes.
- L4475: _DISRUPTION_KIND_TO_BUCKET map without grader changes.
- L4489: legacy path produced.
- L4491: legacy path produced.
- L4501: JSON read by older graders still parse cleanly.
- L4505: JSON read by older graders still parse cleanly.
- L4518: back-compat path even before any callsite uses typed objects.
- L4520: back-compat path even before any callsite uses typed objects.
- L4566: Rule M1 — to_token() byte-equality with the legacy prefix string.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket misc_rules_part14")


@pytest.mark.fast
def test_placeholder_misc_rules_part14():
    """Migration ticket: see docs/proposals/tickets/misc_rules_part14.md."""
    assert False, "stub — migrate from sim.py:4397-4566"
