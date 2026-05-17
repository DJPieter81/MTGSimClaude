"""Migration stub for ticket: cr_305.

Source: sim.py:run_rules_tests() lines 2063-2066
Test count: 4
Headers covered:
- L2063: Audit: Wasteland targeting (CR 305.6)
- L2064: Audit: Wasteland targeting (CR 305.6)
- L2065: Audit: Wasteland targeting (CR 305.6)
- L2066: Audit: Wasteland targeting (CR 305.6)
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket cr_305")


@pytest.mark.fast
def test_placeholder_cr_305():
    """Migration ticket: see docs/proposals/tickets/cr_305.md."""
    assert False, "stub — migrate from sim.py:2063-2066"
