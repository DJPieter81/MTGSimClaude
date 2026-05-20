"""Static guard: no undefined names in production modules.

pyflakes "undefined name" findings are genuine latent bugs — a NameError that
fires the moment the offending path executes. This test ratchets that class to
zero across the engine/AI core, deck plugins, and tooling so a stale global
reference (e.g. a removed STRATEGIES dict) cannot slip back in untested.

Only the "undefined name" category is asserted. Noisy-but-harmless categories
(unused imports, f-strings without placeholders, unused locals) are ignored.

Skips cleanly if pyflakes is not installed (it ships in requirements-dev.txt).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

import pytest

pytest.importorskip('pyflakes')

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _production_py_files() -> list:
    files = glob.glob(os.path.join(_REPO, '*.py'))
    for sub in ('decks', 'scripts', 'tools'):
        files += glob.glob(os.path.join(_REPO, sub, '*.py'))
    return sorted(files)


@pytest.mark.fast
def test_no_undefined_names_in_production_modules():
    """Mechanic: zero pyflakes 'undefined name' findings outside tests/.

    Undefined names are latent NameErrors; this is the real-bug subset of
    static analysis and must stay at zero."""
    proc = subprocess.run(
        [sys.executable, '-m', 'pyflakes', *_production_py_files()],
        capture_output=True, text=True,
    )
    offenders = [ln for ln in proc.stdout.splitlines() if 'undefined name' in ln]
    assert offenders == []
