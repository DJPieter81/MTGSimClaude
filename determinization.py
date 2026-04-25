"""Lever 3 (lite) — Ensemble determinization over the NN-scorer lookahead.

Per Cowling, Powley, Ward (IEEE TCIAIG 2012), MCTS over imperfect-info
games benefits from running independent rollouts on multiple sampled
realisations of the hidden state, then voting / averaging.

We don't have a full MCTS rollout — but we already have a `score_after`
that computes P(win) under one-ply lookahead. The BHI module
(`bhi.HandBelief`) gives us a probability distribution over the
opponent's hand. The cheapest meaningful determinization:

  for sample in 1..N:
      perturb gs by sampling a plausible opponent hand under HandBelief
      → score_after(...) under that perturbation
  return average score across samples

Today the only feature in the encoder that depends on the opponent's
hand composition is `bhi_p_free_counter` (and its sibling probabilities).
Each sample's "perturbation" is therefore a per-sample override of those
features. If/when more hand-aware features are added to `state_encoder`
they automatically benefit.
"""

from __future__ import annotations
import contextlib
import random
from typing import ContextManager, Optional

from neural_scorer import score as _scorer


@contextlib.contextmanager
def hypothetical_bhi(gs, opponent, p_free_counter: float,
                     p_counter: float, p_removal: float, p_burn: float):
    """Temporarily override the cached HandBelief on `gs` so the encoder
    reads our sampled probabilities. Restored on exit."""
    cache_key = "_bhi_p2" if opponent is gs.p2 else "_bhi_p1"
    old = getattr(gs, cache_key, None)

    class _StubBelief:
        pass
    stub = _StubBelief()
    stub.p_free_counter = p_free_counter
    stub.p_counter = p_counter
    stub.p_removal = p_removal
    stub.p_burn = p_burn

    setattr(gs, cache_key, {
        "deck": (gs.p2_deck if opponent is gs.p2 else gs.p1_deck),
        "hand_size": len(opponent.hand),
        "turn": gs.turn,
        "belief": stub,
    })
    try:
        yield
    finally:
        if old is None:
            try:
                delattr(gs, cache_key)
            except AttributeError:
                pass
        else:
            setattr(gs, cache_key, old)


def _sample_belief_perturbations(gs, opponent, n: int = 5,
                                 jitter: float = 0.15) -> list[dict]:
    """Sample N belief vectors by perturbing the current HandBelief
    probabilities with truncated Gaussian noise (σ = jitter, clamped to [0,1]).

    Cheap stand-in for full hand-realisation sampling — the encoder reads
    only the marginal probabilities, so jittering them is equivalent to
    sampling realisations under the deck profile."""
    cache_key = "_bhi_p2" if opponent is gs.p2 else "_bhi_p1"
    cached = getattr(gs, cache_key, None)
    if cached is None or "belief" not in cached:
        return []

    base = cached["belief"]
    samples = []
    for _ in range(n):
        def _jit(v):
            return max(0.0, min(1.0, v + random.gauss(0.0, jitter)))
        samples.append({
            "p_free_counter": _jit(getattr(base, "p_free_counter", 0.0)),
            "p_counter":      _jit(getattr(base, "p_counter",      0.0)),
            "p_removal":      _jit(getattr(base, "p_removal",      0.0)),
            "p_burn":         _jit(getattr(base, "p_burn",         0.0)),
        })
    return samples


def ensemble_score_after(gs, player, opponent, deck: str,
                         action_mutator: ContextManager,
                         n_samples: int = 5) -> Optional[float]:
    """Apply `action_mutator`, then for each of `n_samples` belief
    perturbations call the scorer. Return the mean predicted P(win), or
    None if the model is missing."""
    samples = _sample_belief_perturbations(gs, opponent, n=n_samples)
    if not samples:
        # Fall back to single-sample lookahead.
        with action_mutator:
            return _scorer(gs, player, opponent, deck=deck)

    with action_mutator:
        scores = []
        for s in samples:
            with hypothetical_bhi(gs, opponent, **s):
                v = _scorer(gs, player, opponent, deck=deck)
                if v is None:
                    return None
                scores.append(v)
    return sum(scores) / max(1, len(scores))


def ensemble_argmax_action(gs, player, opponent, deck: str,
                           candidates: list[tuple[str, ContextManager]],
                           default_tag: str,
                           n_samples: int = 5) -> tuple[str, Optional[float]]:
    """Like `lookahead.argmax_action`, but each candidate is scored via
    BHI-jittered ensemble averaging."""
    best_tag = default_tag
    best_score: Optional[float] = None
    for tag, mut in candidates:
        s = ensemble_score_after(gs, player, opponent, deck, mut,
                                 n_samples=n_samples)
        if s is None:
            return default_tag, None
        if best_score is None or s > best_score:
            best_tag, best_score = tag, s
    return best_tag, best_score
