"""Monte Carlo policy improvement via cloned-rollout — Lever 4 of the neural pivot.

`argmax_rollout(...)` is the rollout-based analogue of
`lookahead.argmax_action`:

  for each candidate action:
      for k in 1..K:
          clone = clone_game_state(gs)
          apply_fn(clone, clone_player, clone_opponent)   # apply candidate
          rollout_to_end(clone)                           # heuristic policy
      mean_outcome[candidate] = wins / K
  return argmax(mean_outcome)

The candidate's `apply_fn` is a callable that takes the clone's
(gs, player, opponent) so it can mutate the cloned objects rather than
the live ones referenced by the strategy. The strategy is responsible
for capturing any per-original references (e.g. `target_idx` into the
opponent's creatures list) and using them inside the closure.
"""

from __future__ import annotations
from typing import Callable, Optional

from gamestate_clone import clone_game_state
from rollout import rollout_to_end


def argmax_rollout(gs, player, opponent,
                   candidates: list[tuple[str, Callable]],
                   K: int = 5,
                   max_turns_remaining: int = 5,
                   rng_seed_base: int = 0) -> tuple[str, Optional[float]]:
    """Score each candidate by averaging K independent rollouts.

    Args:
        candidates: list of (tag, apply_fn) where
            apply_fn(cloned_gs, cloned_player, cloned_opponent) -> None
            mutates the clone to reflect the candidate's effect.
        K: rollouts per candidate.
        max_turns_remaining: cap rollout depth (each turn = both players).
        rng_seed_base: combined with (candidate_idx, k) for per-rollout seed.

    Returns: (best_tag, best_mean_outcome). `best_mean_outcome` is the
    fraction of rollouts where the protagonist (= the side `player`
    refers to) won, in [0, 1].
    """
    if not candidates:
        return ("", None)

    proto_label = 1 if player is gs.p1 else 0

    best_tag = candidates[0][0]
    best_mean: Optional[float] = None

    for ci, (tag, apply_fn) in enumerate(candidates):
        wins = 0
        for k in range(K):
            clone = clone_game_state(gs)
            cp = clone.p1 if player is gs.p1 else clone.p2
            co = clone.p2 if opponent is gs.p2 else clone.p1
            try:
                apply_fn(clone, cp, co)
            except Exception:
                # Apply fn raised — treat as a losing rollout for this
                # candidate (penalises malformed apply functions).
                continue
            outcome = rollout_to_end(
                clone,
                max_turns_remaining=max_turns_remaining,
                rng_seed=rng_seed_base * 1000 + ci * 100 + k,
            )
            if outcome == proto_label:
                wins += 1
        mean = wins / max(1, K)
        if best_mean is None or mean > best_mean:
            best_tag, best_mean = tag, mean
    return best_tag, best_mean
