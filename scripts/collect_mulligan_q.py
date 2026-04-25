"""Lever 6 — Generate counterfactual mulligan training data.

For each of N opening hands, simulate BOTH outcomes:
  * keep this hand → run game to end → label `won_keep`
  * mulligan to 6 → run game with the new (smaller) hand → label `won_mull`

Both rows share the same features (the original 7-card hand encoded by
`mulligan_features.encode_hand`). Each row's `decision_value` is `keep`
or `mull`, label is the binary game outcome.

Usage:
    python3 scripts/collect_mulligan_q.py --p1 ur_delver --multi-opp \
        --n 200 --out traces/ur_delver_mulligan_q.jsonl
"""

from __future__ import annotations
import argparse
import json
import os
import random
import sys
import time
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import DECKS
from game import GameState, PlayerState, _choose_best_n
from config import GameRules as GR
from engine import play_turn
from deck_registry import get_keep_fn
from game import opp_keep
from mulligan_features import encode_hand


_DEFAULT_OPPONENTS = ("burn", "storm", "dimir", "show", "oops")


def _shuffle_deck(deck_key: str) -> List:
    """Build + shuffle a deck."""
    deck = list(DECKS[deck_key]())
    random.shuffle(deck)
    return deck


def _play_from_hand(p1_deck: str, p2_deck: str,
                    p1_hand: list, p1_lib: list,
                    p1_goes_first: bool) -> int:
    """Play a full game with p1's opening already decided. p2 takes its
    own heuristic mulligans. Returns 1 if p1 wins, 0 if p2 wins."""
    # p2 takes its own mulligan
    p2_keep = get_keep_fn(p2_deck) or opp_keep
    from game import london_mulligan as _lm
    p2_hand, p2_lib, _mulls = _lm(DECKS[p2_deck], p2_keep, matchup=p1_deck)

    gs = GameState(
        p1=PlayerState(name='b', hand=list(p1_hand), library=list(p1_lib)),
        p2=PlayerState(name='o', hand=list(p2_hand), library=list(p2_lib)),
        p1_goes_first=p1_goes_first,
    )
    gs.p1_deck = p1_deck
    gs.p2_deck = p2_deck
    gs.matchup = p2_deck
    gs.trace = False

    for turn in range(1, GR.MAX_TURNS + 1):
        if gs.game_over:
            break
        gs.turn = turn
        first, second = ('p1', 'p2') if p1_goes_first else ('p2', 'p1')
        for who in (first, second):
            try:
                play_turn(gs, turn, who)
            except Exception:
                gs.game_over = True
                gs.winner = 'p2' if who == 'p1' else 'p1'
                break
            if gs.game_over:
                break

    if gs.game_over and gs.winner:
        return 1 if gs.winner == 'p1' else 0
    # Tiebreak (same as run_game)
    p1_score = (sum(c.power for c in gs.p1.creatures) * 2
                + len(gs.p1.creatures) * 3 + len(gs.p1.lands)
                + max(0, gs.p1.life - gs.p2.life))
    p2_score = (sum(c.power for c in gs.p2.creatures) * 2
                + len(gs.p2.creatures) * 3 + len(gs.p2.lands)
                + max(0, gs.p2.life - gs.p1.life))
    return 1 if p1_score >= p2_score else 0


def collect(p1: str, opponents: tuple[str, ...], n_per_opp: int,
            seed_start: int, out_path: str, K: int = 5) -> dict:
    """K rollouts per (hand, action). Each (hand, action) pair emits K rows
    sharing the same hand features but with independent rollout outcomes."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows_written = 0
    by_action = {"keep": 0, "mull": 0}
    wins_by_action = {"keep": 0, "mull": 0}
    t0 = time.time()
    with open(out_path, "w") as fh:
        for opp in opponents:
            print(f"  → {p1}_vs_{opp} (n={n_per_opp}, K={K})")
            for i in range(n_per_opp):
                # Alternate going-first across hands so the dataset balances.
                p1_goes_first = bool(i % 2 == 0)
                random.seed(seed_start + i)
                deck_keep = _shuffle_deck(p1)
                hand_keep = deck_keep[:7]
                lib_keep = deck_keep[7:]
                hand_features = encode_hand(hand_keep, matchup=opp,
                                            goes_first=p1_goes_first)

                # K independent "keep" rollouts (different opp draws + p2 mull)
                for k in range(K):
                    random.seed(seed_start + i + 50_000 + k * 1_000_000)
                    won = _play_from_hand(p1, opp, hand_keep, lib_keep,
                                          p1_goes_first=p1_goes_first)
                    fh.write(json.dumps({
                        "decision_type": "q_mulligan",
                        "decision_value": "keep",
                        "rollout_won": won,
                        "rollout_idx": k,
                        "state": hand_features,
                        "matchup": f"{p1}_vs_{opp}",
                        "seed": seed_start + i,
                        "p1_goes_first": p1_goes_first,
                    }) + "\n")
                    rows_written += 1; by_action["keep"] += 1
                    wins_by_action["keep"] += won

                # K independent "mull" rollouts — each re-draws a fresh 7
                for k in range(K):
                    random.seed(seed_start + i + 200_000 + k * 1_000_000)
                    deck_mull = _shuffle_deck(p1)
                    hand7 = deck_mull[:7]
                    rest = deck_mull[7:]
                    hand_mull = _choose_best_n(hand7, 6)
                    bottomed = [c for c in hand7 if c not in hand_mull]
                    lib_mull = rest + bottomed
                    won = _play_from_hand(p1, opp, hand_mull, lib_mull,
                                          p1_goes_first=p1_goes_first)
                    fh.write(json.dumps({
                        "decision_type": "q_mulligan",
                        "decision_value": "mull",
                        "rollout_won": won,
                        "rollout_idx": k,
                        "state": hand_features,  # same original-7 features
                        "matchup": f"{p1}_vs_{opp}",
                        "seed": seed_start + i,
                        "p1_goes_first": p1_goes_first,
                    }) + "\n")
                    rows_written += 1; by_action["mull"] += 1
                    wins_by_action["mull"] += won

                if (i + 1) % 50 == 0:
                    elapsed = time.time() - t0
                    print(f"     [{i+1}/{n_per_opp}] rows={rows_written} "
                          f"({elapsed:.1f}s elapsed)")
    return {
        "p1": p1,
        "opponents": list(opponents),
        "n_per_opp": n_per_opp,
        "rows": rows_written,
        "by_action": by_action,
        "wr_by_action": {a: f"{wins_by_action[a] / max(1, by_action[a]) * 100:.1f}%"
                         for a in by_action},
        "elapsed_s": round(time.time() - t0, 1),
        "out_path": out_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p1", default="ur_delver")
    ap.add_argument("--p2", default=None)
    ap.add_argument("--multi-opp", action="store_true")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="traces/ur_delver_mulligan_q.jsonl")
    ap.add_argument("--K", type=int, default=5,
                    help="rollouts per (hand, action) pair (default 5)")
    args = ap.parse_args()

    if args.multi_opp:
        opponents = _DEFAULT_OPPONENTS
    elif args.p2:
        opponents = (args.p2,)
    else:
        opponents = ("burn",)

    print(f"[collect_mulligan_q] {args.p1} vs {list(opponents)} "
          f"× n={args.n}, seed={args.seed}, out={args.out}")
    summary = collect(args.p1, opponents, args.n, args.seed, args.out, K=args.K)
    print("\n[summary]")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
