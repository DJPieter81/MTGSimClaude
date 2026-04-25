"""GameState fork helper for multi-step rollout — Lever 4 of the neural pivot.

`clone_game_state(gs)` returns a deep copy of `gs` (and its `p1`/`p2`
PlayerStates and all permanents) suitable for forward simulation without
mutating the caller's state.

Caveats baked in:
* The BHI cache attributes (`_bhi_p1` / `_bhi_p2`) are deep-copied by
  `copy.deepcopy` automatically — but since the clone is going to mutate
  hand sizes and turn numbers, the cache will naturally invalidate on
  next access and `state_encoder._bhi_features` will recompute.
* `strat_log` is shared by reference would be a bug — `copy.deepcopy`
  walks it, which is what we want.
* `log` (list of LogEntry) is deep-copied. Rollouts can append freely
  without polluting the caller's transcript.
"""

from __future__ import annotations
import copy

from game import GameState


def clone_game_state(gs: GameState) -> GameState:
    """Return an independent deep copy of `gs`.

    Mutating the clone (life, hand, lands, creatures, log) does NOT
    affect the original. Verified by `test_clone_roundtrip()` below.
    """
    return copy.deepcopy(gs)


def test_clone_roundtrip() -> tuple[int, int]:
    """Self-test: clone a fresh game state, mutate the clone, assert
    the original is untouched. Returns (passed, failed) counts.

    Called from `run_rules_tests` to keep regression coverage tight.
    """
    import random as _r
    from sim import run_game  # noqa: F401  — proves sim imports cleanly
    from game import GameState as _GS, PlayerState
    from cards import DECKS

    _r.seed(123)
    deck1 = DECKS['ur_delver']() if callable(DECKS['ur_delver']) else list(DECKS['ur_delver'])
    deck2 = DECKS['burn']() if callable(DECKS['burn']) else list(DECKS['burn'])
    p1 = PlayerState(name='b', hand=deck1[:7], library=deck1[7:])
    p2 = PlayerState(name='o', hand=deck2[:7], library=deck2[7:])
    gs = _GS(p1=p1, p2=p2, p1_goes_first=True)
    gs.turn = 3
    gs.p1.life = 14
    gs.p2.life = 9

    failed: list[str] = []

    clone = clone_game_state(gs)

    # 1) Identity: clone is a distinct object
    if clone is gs:
        failed.append("clone is gs (not a copy)")

    # 2) Equality of leaf state
    if clone.p1.life != 14 or clone.p2.life != 9 or clone.turn != 3:
        failed.append("clone leaf state != original")

    # 3) Independence of hand list
    clone.p1.hand.pop()
    if len(gs.p1.hand) == len(clone.p1.hand):
        failed.append("clone hand mutation leaked back to original")

    # 4) Independence of life
    clone.p1.life -= 5
    if gs.p1.life != 14:
        failed.append("clone life mutation leaked back to original")

    # 5) Independence of log
    clone.log.append(None)
    if len(gs.log) == len(clone.log):
        failed.append("clone log mutation leaked back to original")

    if failed:
        for f in failed:
            print(f"  ✗ {f}")
        return 0, len(failed)
    return 1, 0


if __name__ == "__main__":  # pragma: no cover
    p, f = test_clone_roundtrip()
    print(f"clone_roundtrip: {p} passed, {f} failed")
