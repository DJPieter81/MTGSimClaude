"""Tiny PyTorch MLP that predicts P(TES wins | state) — Phase 3 of the
neural pivot.

Architecture: 40 → 32 → 16 → 1 (sigmoid). ~2.4K parameters. CPU-only.

Used by `_strategy_tes` to score candidate cantrip orderings: encode the
state after each candidate, pick the one with the highest predicted win
probability.

`load_scorer()` returns a singleton; `score(gs, p, o)` returns a float in
[0, 1] or `None` if the checkpoint isn't available (caller falls back to
heuristic).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn

from state_encoder import FEATURE_ORDER, encode_state_vec

CHECKPOINT_PATH = Path("models/tes_scorer.pt")
NORM_STATS_PATH = Path("models/tes_scorer_norm.json")


class TesScorer(nn.Module):
    def __init__(self, input_dim: int = len(FEATURE_ORDER)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.net(x)).squeeze(-1)


_singleton: Optional[TesScorer] = None
_norm: Optional[dict] = None


def load_scorer() -> Optional[TesScorer]:
    """Return the trained model or None if the checkpoint is missing."""
    global _singleton, _norm
    if _singleton is not None:
        return _singleton
    if not CHECKPOINT_PATH.exists() or not NORM_STATS_PATH.exists():
        return None
    model = TesScorer()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu",
                                     weights_only=True))
    model.eval()
    _singleton = model
    _norm = json.loads(NORM_STATS_PATH.read_text())
    return model


def _normalize(vec: list[float]) -> torch.Tensor:
    """Apply mean / std normalisation from the training set."""
    if _norm is None:
        # No norm stats — fall back to identity (raw vector).
        return torch.tensor(vec, dtype=torch.float32)
    mean = _norm["mean"]
    std = _norm["std"]
    return torch.tensor(
        [(v - m) / (s if s > 1e-6 else 1.0) for v, m, s in zip(vec, mean, std)],
        dtype=torch.float32,
    )


@torch.no_grad()
def score(gs, player, opponent) -> Optional[float]:
    """Return P(TES wins | current state) ∈ [0, 1]."""
    model = load_scorer()
    if model is None:
        return None
    vec = encode_state_vec(gs, player, opponent)
    x = _normalize(vec).unsqueeze(0)
    return float(model(x).item())
