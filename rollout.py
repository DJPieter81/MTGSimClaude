"""Forward simulation of a (cloned) GameState — Lever 4 of the neural pivot.

`rollout_to_end(gs)` plays from `gs.turn + 1` onward through the heuristic
strategies and returns the outcome (1 if `p1` wins, 0 if `p2` wins).
Caller is expected to pass a CLONE of the live state (use
`gamestate_clone.clone_game_state`) — `rollout_to_end` mutates `gs` in
place.

The "skip the rest of the current turn" semantics (we resume at `turn+1`,
running both players' next turns) is intentional: the candidate action
under evaluation has already been applied in-place on the clone, and the
rest of the current half-turn would have been the same in both branches
anyway. What we want from the rollout is "what does the next K half-turns
look like under each candidate?" — which this gives us cleanly.
"""

from __future__ import annotations
import random
from typing import Optional

from engine import play_turn
from config import GameRules as GR


def _resolve_outcome(gs) -> int:
    """1 = p1 wins, 0 = p2 wins. Uses the same tiebreak logic as
    `sim.run_game` for timeouts."""
    if gs.game_over and gs.winner:
        return 1 if gs.winner == "p1" else 0
    p1_score = (sum(c.power for c in gs.p1.creatures) * 2
                + len(gs.p1.creatures) * 3 + len(gs.p1.lands)
                + max(0, gs.p1.life - gs.p2.life))
    p2_score = (sum(c.power for c in gs.p2.creatures) * 2
                + len(gs.p2.creatures) * 3 + len(gs.p2.lands)
                + max(0, gs.p2.life - gs.p1.life))
    return 1 if p1_score >= p2_score else 0


def rollout_to_end(gs, max_turns_remaining: int = 5,
                   rng_seed: Optional[int] = None) -> int:
    """Play `gs` forward from `gs.turn + 1` for up to `max_turns_remaining`
    full turns (each turn = both players act). Returns 1 if p1 wins, 0
    otherwise.

    `rng_seed` (optional): if set, seed the global `random` for the
    duration of the rollout, restoring the prior state on return.
    Reproducibility for a given (seed, candidate, k) triple.
    """
    saved_state = random.getstate()
    try:
        if rng_seed is not None:
            random.seed(rng_seed)

        # Disable trace + strategic logging on the clone — we only care about
        # the winner, not any side-channel.
        gs.trace = False
        if hasattr(gs, "strat_log"):
            gs.strat_log.enabled = False
        # Defuse ALL neural toggles inside the rollout — we want the heuristic
        # policy as the rollout policy, not nested neural calls. Most
        # critically, `collect_q_data` MUST be False here: otherwise each
        # rollout's strategy call would itself trigger `record_q` which forks
        # K more rollouts → infinite recursion.
        gs.use_neural_gates = False
        gs.use_neural_scorer = False
        gs.use_ensemble = False
        gs.use_rollout = False
        gs.use_q_scorer = False
        gs.use_q_mulligan = False
        gs.collect_q_data = False

        starting_turn = gs.turn + 1
        end_turn = min(starting_turn + max_turns_remaining,
                       GR.MAX_TURNS + 1)
        p1_first = gs.p1_goes_first

        for turn in range(starting_turn, end_turn):
            if gs.game_over:
                break
            gs.turn = turn
            first, second = ("p1", "p2") if p1_first else ("p2", "p1")
            for who in (first, second):
                try:
                    play_turn(gs, turn, who)
                except Exception:
                    # Strategy crash inside a rollout — treat the active
                    # player as having forfeited the rest of the game.
                    gs.game_over = True
                    gs.winner = "p2" if who == "p1" else "p1"
                    break
                if gs.game_over:
                    break
        return _resolve_outcome(gs)
    finally:
        random.setstate(saved_state)
