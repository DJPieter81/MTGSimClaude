"""1-ply action-space lookahead — Lever 2 of the neural pivot.

For an elective decision with K candidate actions, we want
`argmax_a NN.score(post_state_after(a))`.

We avoid deep-copying GameState (large + brittle). Instead we mutate the
narrow set of fields that the candidate action would touch, score, then
restore. Each action helper is a context manager that wraps a cheap
mutate/restore pair.

Usage from a strategy:

    from lookahead import score_after, hypothetical_life_delta, \
                          hypothetical_creature_removed

    score_face = score_after(
        gs, player, opponent, deck='ur_delver',
        mutator=hypothetical_life_delta(opponent, -3))
    score_kill = score_after(
        gs, player, opponent, deck='ur_delver',
        mutator=hypothetical_creature_removed(opponent, target))
    if score_face > score_kill: go_face = True
"""

from __future__ import annotations
import contextlib
from typing import Callable, ContextManager, Optional

from neural_scorer import score as _scorer


@contextlib.contextmanager
def hypothetical_life_delta(p, delta: int):
    """Temporarily change `p.life` by `delta`. Restored on exit."""
    old = p.life
    p.life = max(0, old + delta)
    try:
        yield
    finally:
        p.life = old


@contextlib.contextmanager
def hypothetical_creature_removed(p, perm):
    """Temporarily remove `perm` from `p.creatures`. Restored on exit."""
    if perm in p.creatures:
        idx = p.creatures.index(perm)
        p.creatures.pop(idx)
        try:
            yield
        finally:
            p.creatures.insert(idx, perm)
    else:
        yield


@contextlib.contextmanager
def hypothetical_card_drawn(p):
    """Temporarily +1 to hand-size feature. We don't actually draw a card
    (would mutate library state). We just bump a counter the encoder reads.
    Cheap approximation for cantrip lookahead."""
    p.hand.append(_DUMMY_CARD)
    try:
        yield
    finally:
        if _DUMMY_CARD in p.hand:
            p.hand.remove(_DUMMY_CARD)


@contextlib.contextmanager
def hypothetical_mana_spent(p, amount: int):
    """Tap `amount` of p's untapped lands; restore on exit."""
    tapped_now = []
    for land in p.lands:
        if amount <= 0:
            break
        if not land.tapped:
            land.tapped = True
            tapped_now.append(land)
            amount -= 1
    try:
        yield
    finally:
        for land in tapped_now:
            land.tapped = False


class _DummyCard:
    """Stand-in card for hypothetical hand growth — has just enough fields
    that state_encoder doesn't crash. Read-only."""
    name = "_hypothetical_"
    tag = ""
    is_cantrip = False
    cmc = 0
    win_condition = False
    is_combo_piece = False
    engine = False
    lock_piece = False
    free_cast_if_blue = False
    mana_cost: dict = {}
    colors: set = set()
    life_cost = 0

    def is_land(self): return False
    def is_creature(self): return False


_DUMMY_CARD = _DummyCard()


def score_after(gs, player, opponent, deck: str,
                mutator: ContextManager) -> Optional[float]:
    """Apply `mutator` (a context manager), score, restore. Returns None if
    the model isn't loaded for `deck`."""
    with mutator:
        return _scorer(gs, player, opponent, deck=deck)


def argmax_action(gs, player, opponent, deck: str,
                  candidates: list[tuple[str, ContextManager]],
                  default_tag: str) -> tuple[str, Optional[float]]:
    """Score each candidate's post-state and return (best_tag, score).
    Falls back to `default_tag` (with score=None) if model isn't loaded."""
    best_tag = default_tag
    best_score: Optional[float] = None
    for tag, mut in candidates:
        s = score_after(gs, player, opponent, deck=deck, mutator=mut)
        if s is None:
            return default_tag, None
        if best_score is None or s > best_score:
            best_tag, best_score = tag, s
    return best_tag, best_score
