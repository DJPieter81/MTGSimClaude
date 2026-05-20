#!/usr/bin/env python3
"""
regression_sweep.py — Phase C of the post-Phase-6 re-architecture.

Runs a fixed-matchup, fixed-N sweep and compares the resulting per-
matchup win rates against a frozen baseline. Fails when any matchup's
WR drops more than `threshold_pp` percentage points vs baseline.

Usage:
    # Run the sweep and print the diff table
    python3 tools/regression_sweep.py

    # Custom baseline / override N
    python3 tools/regression_sweep.py --baseline config/sweep_baseline.json
    python3 tools/regression_sweep.py --n 100

    # Overwrite the baseline (use only after intentional WR change)
    python3 tools/regression_sweep.py --update-baseline

Exit codes:
    0 — sweep ran and no matchup regressed beyond threshold
    1 — at least one matchup dropped > threshold_pp vs baseline
    2 — baseline file missing or unparseable
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


# ── Default matchup set ─────────────────────────────────────────────
# Ten matchups chosen to exercise the four bottleneck decks (Storm,
# Reanimator, Depths, Goblins) against both fast aggro and counter-heavy
# opponents. Two interaction-vs-combo matchups round out the set.
DEFAULT_MATCHUPS: tuple[tuple[str, str], ...] = (
    ('storm',      'burn'),
    ('storm',      'dimir'),
    ('reanimator', 'burn'),
    ('reanimator', 'dimir'),
    ('depths',     'burn'),
    ('depths',     'dimir'),
    ('goblins',    'uwx'),
    ('goblins',    'dimir'),
    ('bug',        'storm'),
    ('ur_delver',  'dimir'),
)

DEFAULT_N_GAMES = 200
DEFAULT_THRESHOLD_PP = 5.0   # max allowed WR drop in percentage points

BASELINE_PATH = REPO_ROOT / 'config' / 'sweep_baseline.json'


def run_sweep_matrix(
    matchups: tuple[tuple[str, str], ...],
    n_games: int,
    seed: int = 2026,
) -> dict:
    """Run each matchup at n_games (sequential, fixed-seed), return a
    dict keyed by 'p1_vs_p2'.

    Uses `parallel=False` so the RNG stream is single-process and the
    result is byte-reproducible between runs. The regression gate
    depends on this — without it, parallel partitioning would produce
    different WRs on each invocation and the 5pp threshold would
    catch noise instead of real regressions.
    """
    import random
    from sim import run_sweep

    results: dict[str, dict] = {}
    t0 = time.time()
    for i, (d1, d2) in enumerate(matchups, start=1):
        m_start = time.time()
        # Re-seed per matchup so any future change to the matchup list
        # (adding/removing) doesn't shift downstream matchups' RNG.
        random.seed(seed + i)
        sweep = run_sweep(d1, d2, n_games=n_games, parallel=False)
        results[f'{d1}_vs_{d2}'] = {
            'p1': d1,
            'p2': d2,
            'p1_wr': round(sweep['p1_wr'], 4),
            'p1_wins': sweep['p1_wins'],
            'p2_wins': sweep['p2_wins'],
            'avg_kill': round(sweep.get('avg_kill', 0) or 0, 2),
            'avg_length': round(sweep.get('avg_length', 0) or 0, 2),
        }
        elapsed = time.time() - m_start
        print(f"  [{i}/{len(matchups)}] {d1} vs {d2}: "
              f"p1_wr={results[f'{d1}_vs_{d2}']['p1_wr']:.1%} "
              f"({elapsed:.1f}s)", flush=True)
    print(f"  total sweep time: {time.time() - t0:.1f}s", flush=True)
    return results


def load_baseline(path: Path) -> dict | None:
    """Load the baseline file. Returns None if missing."""
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read baseline at {path}: {e}", file=sys.stderr)
        sys.exit(2)


def diff_against_baseline(
    current: dict,
    baseline: dict,
    threshold_pp: float,
) -> tuple[list[dict], list[dict]]:
    """Compute per-matchup diffs. Returns (all_diffs, regressions).

    `regressions` is the subset of `all_diffs` where the p1_wr drop
    exceeded `threshold_pp` percentage points.
    """
    all_diffs = []
    regressions = []
    baseline_matchups = {m['p1'] + '_vs_' + m['p2']: m
                         for m in baseline.get('matchups', [])}

    for key, cur in current.items():
        base = baseline_matchups.get(key)
        if base is None:
            # New matchup added to the set — record but don't fail.
            all_diffs.append({
                'matchup': key,
                'current_wr': cur['p1_wr'],
                'baseline_wr': None,
                'delta_pp': None,
                'note': 'new matchup (no baseline)',
            })
            continue
        delta = (cur['p1_wr'] - base['p1_wr']) * 100  # to percentage points
        row = {
            'matchup': key,
            'current_wr': cur['p1_wr'],
            'baseline_wr': base['p1_wr'],
            'delta_pp': round(delta, 2),
        }
        all_diffs.append(row)
        if delta < -threshold_pp:
            regressions.append(row)

    return all_diffs, regressions


def print_diff_table(diffs: list[dict]) -> None:
    """Pretty-print the per-matchup diff table."""
    print()
    print(f"  {'matchup':<32}  {'baseline':>10}  {'current':>10}  {'Δpp':>7}")
    print(f"  {'-' * 32}  {'-' * 10}  {'-' * 10}  {'-' * 7}")
    for row in diffs:
        base = (f"{row['baseline_wr']:.1%}"
                if row['baseline_wr'] is not None else '  (new)')
        cur = f"{row['current_wr']:.1%}"
        delta = (f"{row['delta_pp']:+.1f}"
                 if row['delta_pp'] is not None else '   —')
        marker = ''
        if row.get('delta_pp') is not None:
            if row['delta_pp'] <= -5:
                marker = '  ⚠'
            elif row['delta_pp'] >= 5:
                marker = '  ↑'
        print(f"  {row['matchup']:<32}  {base:>10}  {cur:>10}  {delta:>7}{marker}")
    print()


def write_baseline(
    results: dict,
    path: Path,
    n_games: int,
    threshold_pp: float,
) -> None:
    """Write/overwrite the baseline file."""
    import subprocess
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        sha = 'unknown'

    out = {
        '_meta': {
            'n_games': n_games,
            'threshold_pp': threshold_pp,
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'main_sha': sha,
            'comment': (
                'Phase C regression-sweep baseline. The CI gate '
                'tools/regression_sweep.py fails when any matchup '
                'win rate drops > threshold_pp vs the values here. '
                'Update only after an intentional WR change (rebuild '
                'the file with `python3 tools/regression_sweep.py '
                '--update-baseline`).'
            ),
        },
        'matchups': sorted(results.values(),
                           key=lambda r: (r['p1'], r['p2'])),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(f"  wrote baseline to {path}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    ap.add_argument('--baseline', type=Path, default=BASELINE_PATH,
                    help='path to baseline JSON (default: config/sweep_baseline.json)')
    ap.add_argument('--n', type=int, default=None,
                    help='override n_games per matchup (default: baseline value or %d)' % DEFAULT_N_GAMES)
    ap.add_argument('--threshold-pp', type=float, default=None,
                    help='override regression threshold in percentage points')
    ap.add_argument('--update-baseline', action='store_true',
                    help='overwrite the baseline file with the current results')
    ap.add_argument('--no-fail', action='store_true',
                    help='print regressions but exit 0 regardless')
    args = ap.parse_args()

    baseline = load_baseline(args.baseline)
    n_games = (args.n
               or (baseline['_meta']['n_games'] if baseline else None)
               or DEFAULT_N_GAMES)
    threshold_pp = (args.threshold_pp
                    or (baseline['_meta']['threshold_pp'] if baseline else None)
                    or DEFAULT_THRESHOLD_PP)

    print(f"=== regression sweep: {len(DEFAULT_MATCHUPS)} matchups × "
          f"n={n_games} (threshold ±{threshold_pp}pp) ===")
    print(f"  starting at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    current = run_sweep_matrix(DEFAULT_MATCHUPS, n_games)

    if args.update_baseline:
        write_baseline(current, args.baseline, n_games, threshold_pp)
        return 0

    if baseline is None:
        print(f"\nNo baseline at {args.baseline}. Re-run with "
              f"--update-baseline to create one.")
        return 2

    all_diffs, regressions = diff_against_baseline(
        current, baseline, threshold_pp,
    )
    print_diff_table(all_diffs)

    if regressions and not args.no_fail:
        print(f"  FAIL: {len(regressions)} matchup(s) regressed more "
              f"than {threshold_pp}pp:")
        for r in regressions:
            print(f"    {r['matchup']}: {r['delta_pp']:+.1f}pp "
                  f"({r['baseline_wr']:.1%} → {r['current_wr']:.1%})")
        return 1

    if regressions:
        print(f"  WARN: {len(regressions)} regression(s) suppressed by --no-fail")
        return 0

    print(f"  PASS: all {len(all_diffs)} matchups within ±{threshold_pp}pp")
    return 0


if __name__ == '__main__':
    sys.exit(main())
