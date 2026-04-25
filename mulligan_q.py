"""Mulligan Q-net — Lever 6 of the neural pivot.

Predicts `P(win | hand, action)` for action ∈ {keep, mull}, where
`hand` is encoded by `mulligan_features.encode_hand`. At decision time
the wrapper `should_keep(hand, matchup, deck_key)` scores both actions
and returns True iff `keep` wins.

Inference fail-soft: returns `None` if checkpoint missing → caller
falls back to the heuristic keep_fn.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Sequence

import torch
import torch.nn as nn

from mulligan_features import HAND_FEATURE_ORDER, encode_hand_vec


ACTION_VOCAB = ["keep", "mull"]

CHECKPOINT_PATH = Path("models/q_mulligan.pt")
NORM_PATH       = Path("models/q_mulligan_norm.json")


class MulliganQ(nn.Module):
    def __init__(self, n_actions: int = len(ACTION_VOCAB)):
        super().__init__()
        in_dim = len(HAND_FEATURE_ORDER) + n_actions
        self.net = nn.Sequential(
            nn.Linear(in_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.net(x)).squeeze(-1)


_cache: dict[str, tuple[MulliganQ, dict]] = {}


def _load() -> Optional[MulliganQ]:
    if "model" in _cache:
        return _cache["model"][0]
    if not CHECKPOINT_PATH.exists() or not NORM_PATH.exists():
        return None
    model = MulliganQ()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu",
                                     weights_only=True))
    model.eval()
    norm = json.loads(NORM_PATH.read_text())
    _cache["model"] = (model, norm)
    return model


def _action_onehot(action: str) -> list[float]:
    out = [0.0] * len(ACTION_VOCAB)
    if action in ACTION_VOCAB:
        out[ACTION_VOCAB.index(action)] = 1.0
    return out


def _normalize(state_vec: list[float], norm: Optional[dict]) -> list[float]:
    if norm is None:
        return list(state_vec)
    mean = norm["mean"]
    std = norm["std"]
    return [(v - m) / (s if s > 1e-6 else 1.0)
            for v, m, s in zip(state_vec, mean, std)]


@torch.no_grad()
def score_action(hand: Sequence, matchup: str, action: str,
                 goes_first: bool = True) -> Optional[float]:
    """Return P(win | hand, action) ∈ [0, 1] or None if model missing."""
    model = _load()
    if model is None:
        return None
    norm = _cache["model"][1]
    state_vec = encode_hand_vec(hand, matchup, goes_first=goes_first)
    state_norm = _normalize(state_vec, norm)
    action_oh = _action_onehot(action)
    x = torch.tensor(state_norm + action_oh, dtype=torch.float32).unsqueeze(0)
    return float(model(x).item())


def should_keep(hand: Sequence, matchup: str = "",
                goes_first: bool = True,
                confidence_threshold: float = 0.10) -> Optional[bool]:
    """Q-policy for the mulligan decision.

    Returns True/False/None:
      * None  → checkpoint missing OR Q-net not confident enough to
                override the heuristic. Caller falls back to heuristic.
      * True  → Q-net confidently prefers keep
      * False → Q-net confidently prefers mull

    `confidence_threshold` (default 0.10) is the minimum |P(win|keep) -
    P(win|mull)| required to override the heuristic. Empirical learning:
    without this, the Q-net regressed `ur_delver_vs_storm` by -6.3pp by
    over-mulliganing fast hands. With τ=0.10 the Q-net only overrides
    when it's clearly more informative than the heuristic.
    """
    p_keep = score_action(hand, matchup, "keep", goes_first=goes_first)
    if p_keep is None:
        return None
    p_mull = score_action(hand, matchup, "mull", goes_first=goes_first)
    if p_mull is None:
        return None
    if abs(p_keep - p_mull) < confidence_threshold:
        return None  # defer to heuristic
    return p_keep >= p_mull
