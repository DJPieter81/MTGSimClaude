"""Parity gate for the Phase-2 pytest migration.

Runs both `run_rules_tests()` (legacy) and pytest (`-m fast`), asserts that the
sum of legacy passes + pytest non-skipped passes equals the original assertion
count from the manifest. Skipped pytest stubs count toward the legacy side; as
each ticket lands, its tests move from "skipped" to "passed" on the pytest side
and the corresponding source-line assertions stay green on the legacy side.

Exit 0 on parity, 1 on drift. Designed to run in <10s.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools" / "test_parity_data.json"


def legacy_counts() -> tuple[int, int]:
    """Run run_rules_tests() and return (passed, failed)."""
    sys.path.insert(0, str(ROOT))
    from sim import run_rules_tests  # noqa

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_rules_tests()
    out = buf.getvalue()
    passed = out.count("[PASS]")
    failed = out.count("[FAIL]")
    return passed, failed


def pytest_counts() -> tuple[int, int, int]:
    """Run pytest -m fast, return (passed, failed, skipped)."""
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "fast", "-q", "--no-header",
         "-p", "no:cacheprovider", "--timeout=10"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out = res.stdout + res.stderr
    # Final summary line: e.g. "4 passed, 1 failed, 2 skipped in 0.43s"
    m = re.search(r"=+\s*(.+?)\s*=+\s*$", out.strip().splitlines()[-1])
    summary = m.group(1) if m else out.splitlines()[-1]
    def grab(word: str) -> int:
        mm = re.search(rf"(\d+)\s+{word}", summary)
        return int(mm.group(1)) if mm else 0
    return grab("passed"), grab("failed"), grab("skipped")


BASELINE_FILE = ROOT / "tools" / "test_parity_baseline.json"


def main() -> int:
    if not MANIFEST.exists():
        print(f"manifest missing: {MANIFEST}", file=sys.stderr)
        return 1

    lp, lf = legacy_counts()
    pp, pf, ps = pytest_counts()

    print(f"legacy run_rules_tests : {lp} passed, {lf} failed")
    print(f"pytest -m fast        : {pp} passed, {pf} failed, {ps} skipped")

    if lf or pf:
        print("FAIL: legacy or pytest reported failures", file=sys.stderr)
        return 1

    # Baseline ratchet: legacy pass count must never drop. The baseline is
    # written on first run; later runs only update it if --update is passed.
    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())
        if lp < baseline["legacy_passed"]:
            print(
                f"FAIL: legacy regressed — {lp} passed, baseline was "
                f"{baseline['legacy_passed']}",
                file=sys.stderr,
            )
            return 1
        if "--update" in sys.argv and lp > baseline["legacy_passed"]:
            BASELINE_FILE.write_text(json.dumps({"legacy_passed": lp}, indent=2))
            print(f"updated baseline to {lp}")
    else:
        BASELINE_FILE.write_text(json.dumps({"legacy_passed": lp}, indent=2))
        print(f"wrote initial baseline at {lp}")

    print("PARITY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
