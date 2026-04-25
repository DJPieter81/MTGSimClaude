"""Lever 5 — Generate (state, action, rollout-outcome) Q-data for training a
per-decision discriminator.

Runs N games of `ur_delver_vs_<opp>` with `collect_q_data=True`. At every
elective decision the strategy hooks (`record_q` in `state_encoder.py`)
fork the game K times per candidate via `rollout_to_end`, label each fork's
outcome, and emit one row per rollout. The Q-net trains on these triples
to predict P(win | state, action).

Usage
-----
    python3 scripts/collect_q_data.py --p1 ur_delver --p2 burn --n 200 \
        --out traces/ur_delver_burn_q.jsonl
    python3 scripts/collect_q_data.py --p1 ur_delver --multi-opp \
        --n 100 --out traces/ur_delver_multi_q.jsonl
"""

from __future__ import annotations
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import run_game
from state_encoder import collect


_DEFAULT_OPPONENTS = ("burn", "storm", "dimir", "show", "oops")


def collect_run(p1: str, opponents: tuple[str, ...], n_per_opp: int,
                seed_start: int, out_path: str) -> dict:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows_written = 0
    by_action: dict[str, int] = {}
    t0 = time.time()
    with open(out_path, "w") as fh:
        for opp in opponents:
            print(f"  → {p1}_vs_{opp} (n={n_per_opp})")
            for i in range(n_per_opp):
                random.seed(seed_start + i)
                with collect() as rows:
                    r = run_game(p1, opp, collect_q_data=True)
                # Annotate each row with game-level metadata
                for row in rows:
                    if not row["decision_type"].startswith("q_"):
                        continue
                    row["matchup"] = f"{p1}_vs_{opp}"
                    row["seed"] = seed_start + i
                    row["game_winner"] = r.winner
                    row["game_kill_turn"] = r.kill_turn
                    fh.write(json.dumps(row) + "\n")
                    rows_written += 1
                    by_action[row["decision_value"]] = (
                        by_action.get(row["decision_value"], 0) + 1
                    )
                if (i + 1) % 50 == 0:
                    elapsed = time.time() - t0
                    print(f"     [{i+1}/{n_per_opp}] rows={rows_written} "
                          f"({elapsed:.1f}s elapsed)")
    return {
        "p1": p1,
        "opponents": list(opponents),
        "n_per_opp": n_per_opp,
        "total_games": n_per_opp * len(opponents),
        "rows": rows_written,
        "by_action": by_action,
        "elapsed_s": round(time.time() - t0, 1),
        "out_path": out_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p1", default="ur_delver")
    ap.add_argument("--p2", default=None,
                    help="single opponent (mutually exclusive with --multi-opp)")
    ap.add_argument("--multi-opp", action="store_true",
                    help=f"run vs all of {list(_DEFAULT_OPPONENTS)}")
    ap.add_argument("--n", type=int, default=100, help="games per opponent")
    ap.add_argument("--seed", type=int, default=0, help="seed start")
    ap.add_argument("--out", default="traces/ur_delver_q.jsonl")
    args = ap.parse_args()

    if args.multi_opp:
        opponents = _DEFAULT_OPPONENTS
    elif args.p2:
        opponents = (args.p2,)
    else:
        opponents = ("burn",)

    print(f"[collect_q_data] {args.p1} vs {list(opponents)} "
          f"× n={args.n}, seed={args.seed}, out={args.out}")
    summary = collect_run(args.p1, opponents, args.n, args.seed, args.out)
    print("\n[summary]")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
