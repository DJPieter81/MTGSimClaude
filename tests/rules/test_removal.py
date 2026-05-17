"""Migration stub for ticket: removal.

Source: sim.py:run_rules_tests() lines 1937-3990
Test count: 21
Headers covered:
- L1937: Fatal Push CMC
- L1938: Fatal Push CMC
- L1939: Fatal Push CMC
- L1940: Fatal Push CMC
- L1941: Fatal Push CMC
- L1942: Fatal Push CMC
- L1943: Fatal Push CMC
- L1944: Fatal Push CMC
- L1997: Abrupt Decay
- L1998: Abrupt Decay
- L1999: Abrupt Decay
- L2023: L3: Dismember kills check
- L2024: L3: Dismember kills check
- L2028: L1: STP life gain = power only
- L3966: tag* + *removal-spell tag*, never a literal card name.
- L3968: tag* + *removal-spell tag*, never a literal card name.
- L3970: tag* + *removal-spell tag*, never a literal card name.
- L3972: tag* + *removal-spell tag*, never a literal card name.
- L3974: tag* + *removal-spell tag*, never a literal card name.
- L3976: tag* + *removal-spell tag*, never a literal card name.
- L3990: counts['removal']. Pin: a 3-removal trace must surface 3.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket removal")


@pytest.mark.fast
def test_placeholder_removal():
    """Migration ticket: see docs/proposals/tickets/removal.md."""
    assert False, "stub — migrate from sim.py:1937-3990"
