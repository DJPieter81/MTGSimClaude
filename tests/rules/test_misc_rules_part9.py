"""Misc rules — part 9. Migrated from sim.py:3618-3734 (run_rules_tests).

Covers:
- regression_sweep harness defaults (Phase C).
- config._load_calibrated and InteractionParams wiring (Phase D).
- depths combo metadata schema (Phase 5).
- Permanent.cheat_on_combat_damage flag (Phase 4).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure tools/ is importable for regression_sweep.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


# ---------------------------------------------------------------------------
# Phase C — regression_sweep harness rule-level tests
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_regression_sweep_bottleneck_decks_in_default_matchups():
    from regression_sweep import DEFAULT_MATCHUPS
    bottleneck = {'storm', 'reanimator', 'depths', 'goblins'}
    matchup_p1 = {m[0] for m in DEFAULT_MATCHUPS}
    assert bottleneck.issubset(matchup_p1)


@pytest.mark.fast
def test_regression_sweep_default_threshold_is_positive_percentage():
    from regression_sweep import DEFAULT_THRESHOLD_PP
    assert 0 < DEFAULT_THRESHOLD_PP <= 100


@pytest.mark.fast
def test_regression_sweep_harness_imports_without_error():
    """The Phase C harness block in sim.py wraps all its rules in
    try/except and records an `error: ...` test on failure. The pytest
    equivalent: importing the harness API must not raise."""
    import importlib
    import regression_sweep
    importlib.reload(regression_sweep)
    assert hasattr(regression_sweep, 'diff_against_baseline')


# ---------------------------------------------------------------------------
# Phase D — config._load_calibrated rule-level tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _calibration_path() -> Path:
    import config as cfg
    real_dir = os.path.dirname(os.path.abspath(cfg.__file__))
    return Path(real_dir) / 'config' / 'calibration.json'


@pytest.mark.fast
def test_load_calibrated_missing_file_returns_fallback(_calibration_path):
    """When the calibration.json file is missing entirely, the loader
    must return the supplied fallback value."""
    import config as cfg
    backup = None
    bak_path = _calibration_path.with_suffix('.json.test-bak-part9-missing')
    if _calibration_path.exists():
        backup = _calibration_path.read_text()
        _calibration_path.rename(bak_path)
    try:
        assert cfg._load_calibrated('NONEXISTENT_KEY', 0.42) == 0.42
    finally:
        if backup is not None:
            bak_path.rename(_calibration_path)


@pytest.mark.fast
def test_load_calibrated_bhi_free_counter_threshold_is_numeric():
    import config as cfg
    val = cfg._load_calibrated('BHI_FREE_COUNTER_THRESHOLD', None)
    assert isinstance(val, (int, float)) and val is not None


@pytest.mark.fast
def test_load_calibrated_bhi_free_counter_threshold_in_unit_interval():
    import config as cfg
    val = cfg._load_calibrated('BHI_FREE_COUNTER_THRESHOLD', None)
    assert val is not None and 0.0 <= float(val) <= 1.0


@pytest.mark.fast
def test_load_calibrated_unknown_key_returns_fallback():
    """File present, but key not in the `values` dict → fallback returned."""
    import config as cfg
    assert cfg._load_calibrated('NOT_A_REAL_KEY', 0.99) == 0.99


@pytest.mark.fast
def test_interaction_params_bhi_free_counter_threshold_sources_from_calibration():
    import config as cfg
    from config import InteractionParams
    val = cfg._load_calibrated('BHI_FREE_COUNTER_THRESHOLD', None)
    expected = val if val is not None else 0.40
    assert InteractionParams.BHI_FREE_COUNTER_THRESHOLD == expected


@pytest.mark.fast
def test_load_calibrated_bhi_counter_threshold_in_unit_interval_when_present():
    import config as cfg
    val_c = cfg._load_calibrated('BHI_COUNTER_THRESHOLD', None)
    assert (val_c is None) or (0.0 <= float(val_c) <= 1.0)


@pytest.mark.fast
def test_interaction_params_bhi_counter_threshold_sources_from_calibration():
    import config as cfg
    from config import InteractionParams
    val_c = cfg._load_calibrated('BHI_COUNTER_THRESHOLD', None)
    expected = val_c if val_c is not None else 0.55
    assert InteractionParams.BHI_COUNTER_THRESHOLD == expected


@pytest.mark.fast
def test_calibration_json_has_required_top_level_keys(_calibration_path):
    """The schema contract: future readers can rely on `_meta`, `values`,
    `summary`, and `data` being present at the top level."""
    if not _calibration_path.exists():
        pytest.skip("calibration.json absent — schema check vacuous")
    with _calibration_path.open() as fh:
        cdata = json.load(fh)
    required = {'_meta', 'values', 'summary', 'data'}
    assert required.issubset(cdata.keys())


@pytest.mark.fast
def test_calibration_loader_block_does_not_raise():
    """Phase D wraps its rules in try/except; the pytest equivalent is
    that the calibration loader path imports cleanly."""
    import importlib
    import config as cfg
    importlib.reload(cfg)
    assert hasattr(cfg, '_load_calibrated')
    assert hasattr(cfg, 'InteractionParams')


# ---------------------------------------------------------------------------
# Phase 5 — depths combo metadata schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _depths_combo_meta():
    from deck_registry import get_combo_meta
    return get_combo_meta('depths')


@pytest.mark.fast
def test_depths_assembly_paths_reference_combo_land_tags(_depths_combo_meta):
    """Every assembly path must reference at least one of the two combo
    land tags ('depths' or 'stage') in its required_tags — the assembly
    fundamentally needs them."""
    assert _depths_combo_meta is not None
    paths = _depths_combo_meta.get('assembly_paths', ())
    land_tags = {'depths', 'stage'}
    bad_paths = [p.tag for p in paths if not (land_tags & p.required_tags)]
    assert bad_paths == []


@pytest.mark.fast
def test_depths_combo_metadata_block_does_not_raise():
    """The depths metadata fetch path must complete without exception."""
    from deck_registry import get_combo_meta
    dm = get_combo_meta('depths')
    # Equivalent of the try/except harness: no exception + dm not None.
    assert dm is not None


# ---------------------------------------------------------------------------
# Phase 4 — Permanent.cheat_on_combat_damage flag default + round-trip
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_permanent_cheat_on_combat_damage_flag_round_trips():
    """The Permanent flag is settable and round-trips on an instance
    (i.e. it is a normal attribute, not a read-only property)."""
    from rules import Card, CardType, Permanent
    card = Card(
        name='_v', card_type=CardType.CREATURE, cmc=1,
        mana_cost={'R': 1}, colors={'R'},
        base_power=1, base_toughness=1, gy_type='creature',
    )
    perm = Permanent(card=card, controller='p1')
    perm.cheat_on_combat_damage = True
    assert perm.cheat_on_combat_damage is True
