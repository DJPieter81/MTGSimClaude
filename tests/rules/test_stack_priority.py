"""Migration stub for ticket: stack_priority.

Source: sim.py:run_rules_tests() lines 2295-2295
Test count: 1
Headers covered:
- L2295: Check priority order manually
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket stack_priority")


@pytest.mark.fast
def test_placeholder_stack_priority():
    """Migration ticket: see docs/proposals/tickets/stack_priority.md."""
    assert False, "stub — migrate from sim.py:2295-2295"
