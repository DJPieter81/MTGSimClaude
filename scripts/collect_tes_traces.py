"""Phase 1c — Collect TES decision traces for the neural-pivot prototype.

Runs N games of `tes_vs_burn` with the existing heuristic strategy. The
decision-record hooks already in `decks/tes.py` emit one row per gate / pick
when `state_encoder.collect()` is active. After each game we attach the final
outcome and write the rows to JSONL.

Usage
-----
    python3 scripts/collect_tes_traces.py --n 1000 --seed 0 \
        --out traces/tes_burn.jsonl

The output JSONL is the supervised dataset for both the LLM few-shot exemplars
(Phase 2) and the small NN scorer (Phase 3).
"""

from __future__ import annotations
import argparse
import json
import os
import random
import sys
import time

# Make project importable when launched as `python3 scripts/...`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import run_game
from state_encoder import collect


def _winner_label(winner: str, tes_slot: str) -> int:
    """1 if TES won, 0 otherwise."""
    return int(winner == tes_slot)


def collect_run(n_games: int, seed_start: int, out_path: str,
                p1_deck: str = "tes", p2_deck: str = "burn") -> dict:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    written = 0
    decisions_by_type: dict[str, int] = {}
    t0 = time.time()
    with open(out_path, "w") as fh:
        for i in range(n_games):
            seed = seed_start + i
            random.seed(seed)
            with collect() as rows:
                r = run_game(p1_deck, p2_deck)
            label = _winner_label(r.winner, "p1")
            for row in rows:
                row["seed"] = seed
                row["eventual_winner"] = r.winner
                row["kill_turn"] = r.kill_turn
                row["game_length"] = r.game_length
                row["tes_won"] = label
                row["matchup"] = f"{p1_deck}_vs_{p2_deck}"
                fh.write(json.dumps(row) + "\n")
                written += 1
                decisions_by_type[row["decision_type"]] = (
                    decisions_by_type.get(row["decision_type"], 0) + 1
                )
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                print(f"  [{i+1}/{n_games}] rows={written} "
                      f"rate={rate:.1f} games/s")
    return {
        "games": n_games,
        "rows": written,
        "by_type": decisions_by_type,
        "elapsed_s": round(time.time() - t0, 1),
        "out_path": out_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=1000, help="games to play")
    ap.add_argument("--seed", type=int, default=0, help="seed start")
    ap.add_argument("--out", type=str, default="traces/tes_burn.jsonl")
    ap.add_argument("--p1", type=str, default="tes")
    ap.add_argument("--p2", type=str, default="burn")
    args = ap.parse_args()

    print(f"[collect_tes_traces] {args.p1} vs {args.p2}, n={args.n}, "
          f"seed={args.seed}, out={args.out}")
    summary = collect_run(args.n, args.seed, args.out, args.p1, args.p2)
    print("\n[summary]")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
