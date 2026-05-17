"""Migration stub for ticket: legend_rule.

Source: sim.py:run_rules_tests() lines 2267-2268
Test count: 2
Headers covered:
- L2267: Two Tamiyos -> legend rule fires
- L2268: Two Tamiyos -> legend rule fires
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket legend_rule")


@pytest.mark.fast
def test_placeholder_legend_rule():
    """Migration ticket: see docs/proposals/tickets/legend_rule.md."""
    assert False, "stub — migrate from sim.py:2267-2268"
