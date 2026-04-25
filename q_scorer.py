"""Q-style discriminator — Lever 5 of the neural pivot.

Predicts `P(win | state, action)` from `(state_features, action_one_hot)`.
Trained on rollout-generated counterfactual triples emitted by
`scripts/collect_q_data.py`.

Why this beats the state-value scorer (`neural_scorer.py`): the value
scorer only sees the state and is trained on the eventual game outcome.
For a decision with two candidate actions whose post-states are very
similar (e.g. "Bolt face" vs "Bolt creature"), the value scorer gives
near-identical scores. The Q-net sees both `state` AND `action`, and is
trained on the per-rollout outcome of taking that specific action — so
it can discriminate at the action level.

Architecture: (41 + |actions|) → 32 → 16 → 1, sigmoid. ~2.6K params.
Per-decision-type model: separate checkpoint per `decision_type` tag, so
the action one-hot can be small and the model specialises.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn

from state_encoder import FEATURE_ORDER, encode_state_vec


# Action vocabularies per decision type. Add to this as more decisions
# get hooked. Order is stable — never re-shuffle, only append.
ACTION_VOCAB: dict[str, list[str]] = {
    "ur_bolt_mode": ["face", "creature"],
}


class QScorer(nn.Module):
    def __init__(self, n_actions: int):
        super().__init__()
        in_dim = len(FEATURE_ORDER) + n_actions
        self.net = nn.Sequential(
            nn.Linear(in_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.net(x)).squeeze(-1)


_cache: dict[str, tuple[QScorer, dict]] = {}


def _paths_for(decision_type: str) -> tuple[Path, Path]:
    return (Path(f"models/q_{decision_type}.pt"),
            Path(f"models/q_{decision_type}_norm.json"))


def load(decision_type: str) -> Optional[QScorer]:
    if decision_type in _cache:
        return _cache[decision_type][0]
    if decision_type not in ACTION_VOCAB:
        return None
    ckpt, norm_path = _paths_for(decision_type)
    if not ckpt.exists() or not norm_path.exists():
        return None
    n_actions = len(ACTION_VOCAB[decision_type])
    model = QScorer(n_actions)
    model.load_state_dict(torch.load(ckpt, map_location="cpu",
                                     weights_only=True))
    model.eval()
    norm = json.loads(norm_path.read_text())
    _cache[decision_type] = (model, norm)
    return model


def _action_onehot(decision_type: str, action: str) -> list[float]:
    vocab = ACTION_VOCAB[decision_type]
    out = [0.0] * len(vocab)
    if action in vocab:
        out[vocab.index(action)] = 1.0
    return out


def _normalize(state_vec: list[float], norm: Optional[dict]) -> list[float]:
    if norm is None:
        return list(state_vec)
    mean = norm["mean"]
    std = norm["std"]
    return [(v - m) / (s if s > 1e-6 else 1.0)
            for v, m, s in zip(state_vec, mean, std)]


@torch.no_grad()
def score(decision_type: str, action: str, gs, player, opponent) -> Optional[float]:
    """Return P(win | state, action) ∈ [0, 1]. None if model not loaded."""
    model = load(decision_type)
    if model is None:
        return None
    norm = _cache[decision_type][1] if decision_type in _cache else None
    state_vec = encode_state_vec(gs, player, opponent)
    state_norm = _normalize(state_vec, norm)
    action_oh = _action_onehot(decision_type, action)
    x = torch.tensor(state_norm + action_oh, dtype=torch.float32).unsqueeze(0)
    return float(model(x).item())


def argmax(decision_type: str, candidates: list[str],
           gs, player, opponent,
           default: Optional[str] = None) -> tuple[Optional[str], Optional[float]]:
    """Return (best_action, best_score). Falls back to (default, None) if
    the model isn't loaded for `decision_type`."""
    model = load(decision_type)
    if model is None:
        return (default, None)
    best_action = default
    best_score: Optional[float] = None
    for action in candidates:
        s = score(decision_type, action, gs, player, opponent)
        if s is None:
            continue
        if best_score is None or s > best_score:
            best_action, best_score = action, s
    return (best_action, best_score)
