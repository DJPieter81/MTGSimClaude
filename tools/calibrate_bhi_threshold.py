#!/usr/bin/env python3
"""
calibrate_bhi_threshold.py — Phase D of the post-Phase-6 re-architecture.

Sweeps `config.InteractionParams.BHI_FREE_COUNTER_THRESHOLD` across a
candidate range and measures the per-matchup win-rate impact on the
Phase C regression-sweep matchup set. Picks the value that maximises
average win rate and writes the supporting data + chosen value to
`config/calibration.json`.

Usage:
    # Run the calibration sweep + print table (read-only)
    python3 tools/calibrate_bhi_threshold.py

    # Write the chosen value to config/calibration.json
    python3 tools/calibrate_bhi_threshold.py --write

The threshold gates Hold/Defer in `combo_engine.combo_plan` (Phase B).
A higher value defers less often (riskier — combo fires through opp
counters more); a lower value defers more (safer — but wastes turns
when opp doesn't actually have a counter).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'tools'))


# Candidate threshold values to sweep. The current main is 0.40.
CANDIDATES: tuple[float, ...] = (0.30, 0.35, 0.40, 0.45, 0.50)

CALIBRATION_PATH = REPO_ROOT / 'config' / 'calibration.json'


def run_sweep_at_threshold(threshold: float) -> dict[str, float]:
    """Run the regression sweep in a SEPARATE process with the
    threshold override applied at startup. Returns {matchup_key: p1_wr}.

    A fresh subprocess is used because the sim accumulates implicit
    state between consecutive in-process sweeps (the source of the
    leak hasn't been hunted down yet; subprocess isolation is the
    pragmatic fix). Without isolation, threshold=0.40 sweeps that
    follow a threshold=0.30 sweep produce different WRs than a
    fresh-process baseline — defeating calibration.
    """
    import subprocess
    # Run a one-shot script that overrides the constant, runs the
    # sweep, and emits JSON on stdout.
    child = subprocess.run(
        [sys.executable, '-c', _CHILD_PROGRAM, str(threshold)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    # The child prints progress to stderr and the final JSON to stdout.
    return json.loads(child.stdout)


_CHILD_PROGRAM = """
import contextlib, json, os, sys
sys.path.insert(0, 'tools')
from config import InteractionParams as IP
IP.BHI_FREE_COUNTER_THRESHOLD = float(sys.argv[1])
from regression_sweep import run_sweep_matrix, DEFAULT_MATCHUPS
# Redirect the sweep's progress prints to stderr; emit the result
# JSON cleanly on stdout for parent json.loads().
with contextlib.redirect_stdout(sys.stderr):
    results = run_sweep_matrix(DEFAULT_MATCHUPS, n_games=200)
print(json.dumps({k: v['p1_wr'] for k, v in results.items()}))
"""


def collect_calibration_data() -> dict:
    """Run the sweep at every candidate, return raw + aggregated data."""
    t0 = time.time()
    print(f"=== BHI threshold calibration: "
          f"sweeping {len(CANDIDATES)} candidates × 10 matchups × n=200 ===",
          flush=True)

    per_threshold: dict[float, dict[str, float]] = {}
    for thr in CANDIDATES:
        print(f"\n  -- threshold = {thr:.2f} --", flush=True)
        per_threshold[thr] = run_sweep_at_threshold(thr)

    print(f"\n  total calibration time: {time.time() - t0:.1f}s", flush=True)
    return per_threshold


def print_table(per_threshold: dict[float, dict[str, float]]) -> None:
    """Print a per-matchup × per-threshold comparison table."""
    candidates = sorted(per_threshold.keys())
    matchups = sorted(per_threshold[candidates[0]].keys())
    print()
    header = '  matchup'.ljust(32) + ''.join(f'  {c:>7.2f}' for c in candidates)
    print(header)
    print('  ' + '-' * (30 + 9 * len(candidates)))
    for m in matchups:
        row = '  ' + m.ljust(30)
        for c in candidates:
            wr = per_threshold[c][m]
            row += f'  {wr:>7.1%}'
        print(row)
    print('  ' + '-' * (30 + 9 * len(candidates)))
    avg_row = '  ' + 'AVG (10 matchups)'.ljust(30)
    for c in candidates:
        avg = sum(per_threshold[c].values()) / len(matchups)
        avg_row += f'  {avg:>7.1%}'
    print(avg_row)
    print()


def pick_best(per_threshold: dict[float, dict[str, float]]) -> tuple[float, dict]:
    """Choose the threshold that maximises mean p1_wr across matchups.

    Tiebreaks: closer to current main (0.40), then lower (more conservative).
    Returns (chosen, summary_dict).
    """
    candidates = sorted(per_threshold.keys())
    n = len(per_threshold[candidates[0]])

    averages = {c: sum(per_threshold[c].values()) / n for c in candidates}
    best_avg = max(averages.values())

    # Find all candidates within 0.1pp of best (treat as ties).
    ties = [c for c in candidates if best_avg - averages[c] < 0.001]
    # Tiebreak: closest to 0.40 (current), then lower.
    ties.sort(key=lambda c: (abs(c - 0.40), c))
    chosen = ties[0]

    summary = {
        'candidates_avg_wr': {f'{c:.2f}': round(averages[c], 4)
                              for c in candidates},
        'chosen': chosen,
        'chosen_avg_wr': round(averages[chosen], 4),
        'tiebreak_rule': 'closest_to_0.40_then_lower',
        'tied_candidates': [f'{c:.2f}' for c in ties],
    }
    return chosen, summary


def write_calibration_file(
    per_threshold: dict[float, dict[str, float]],
    chosen: float,
    summary: dict,
    path: Path,
) -> None:
    """Write the calibration JSON: chosen value + supporting data."""
    import subprocess
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=str(REPO_ROOT), text=True,
        ).strip()
    except subprocess.CalledProcessError:
        sha = 'unknown'

    out = {
        '_meta': {
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'main_sha': sha,
            'n_games_per_matchup': 200,
            'comment': (
                'Phase D calibration output. Reading order: `values` dict '
                'is the canonical source of truth for the listed config '
                'constants. `data` is the raw sweep result the choice was '
                'derived from. To recalibrate after a behaviour change, '
                'run `python3 tools/calibrate_bhi_threshold.py --write`.'
            ),
            'hash_seed_note': (
                'The absolute WRs in `data` are produced by a fresh '
                'subprocess per threshold, which uses Python\'s default '
                '(randomized) PYTHONHASHSEED. Sim outcomes are mildly '
                'sensitive to hash-iteration order, so absolute values '
                'may not match `config/sweep_baseline.json` (generated '
                'via `python3 tools/regression_sweep.py` directly). The '
                'RELATIVE comparison across thresholds is valid — that\'s '
                'what `chosen` is based on. See the in-flight bug note '
                'in docs/design/2026-05-15_post-phase-6-re-architecture.md.'
            ),
        },
        'values': {
            'BHI_FREE_COUNTER_THRESHOLD': chosen,
        },
        'summary': summary,
        'data': {
            f'{thr:.2f}': per_threshold[thr]
            for thr in sorted(per_threshold.keys())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(f"  wrote calibration to {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    ap.add_argument('--write', action='store_true',
                    help='write the chosen value to config/calibration.json')
    args = ap.parse_args()

    per_threshold = collect_calibration_data()
    print_table(per_threshold)
    chosen, summary = pick_best(per_threshold)
    print(f"  chosen threshold: {chosen:.2f}  "
          f"(avg WR {summary['chosen_avg_wr']:.1%})")
    print(f"  ties: {summary['tied_candidates']}, tiebreak: "
          f"{summary['tiebreak_rule']}")

    if args.write:
        write_calibration_file(per_threshold, chosen, summary,
                               CALIBRATION_PATH)
    else:
        print(f"\n  (read-only — pass --write to update "
              f"{CALIBRATION_PATH.relative_to(REPO_ROOT)})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
