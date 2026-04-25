"""Tiny PyTorch MLP that predicts P(active player wins | state).

Architecture: 41 → 32 → 16 → 1 (sigmoid). ~2.4K parameters. CPU-only.

Now deck-aware: callers `score(gs, p, o, deck="tes")` to load the right
checkpoint. `models/<deck>_scorer.pt` + `models/<deck>_scorer_norm.json`.
The legacy single-checkpoint path (`load_scorer()` / `score()` without
`deck=`) defaults to "tes" for back-compat.

`score(...)` returns a float ∈ [0, 1], or `None` if the checkpoint is
missing (callers fall back to heuristic).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn

from state_encoder import FEATURE_ORDER, encode_state_vec

# Legacy path defaults — kept so old code that imports CHECKPOINT_PATH
# / NORM_STATS_PATH still works (used by train_neural_scorer.py default).
CHECKPOINT_PATH = Path("models/tes_scorer.pt")
NORM_STATS_PATH = Path("models/tes_scorer_norm.json")


class TesScorer(nn.Module):
    """Original 41 → 32 → 16 → 1 architecture. The class name is kept for
    back-compat with `train_neural_scorer.py`; it is deck-agnostic."""
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


# ── Deck-keyed cache for loaded models ────────────────────────────────────
_cache: dict[str, tuple[TesScorer, dict]] = {}


def _paths_for(deck: str) -> tuple[Path, Path]:
    return Path(f"models/{deck}_scorer.pt"), Path(f"models/{deck}_scorer_norm.json")


def load_scorer(deck: str = "tes") -> Optional[TesScorer]:
    """Return the trained model for `deck` or None if the checkpoint is missing."""
    if deck in _cache:
        return _cache[deck][0]
    ckpt_path, norm_path = _paths_for(deck)
    if not ckpt_path.exists() or not norm_path.exists():
        return None
    model = TesScorer()
    model.load_state_dict(torch.load(ckpt_path, map_location="cpu",
                                     weights_only=True))
    model.eval()
    norm = json.loads(norm_path.read_text())
    _cache[deck] = (model, norm)
    return model


def _normalize(vec: list[float], norm: Optional[dict]) -> torch.Tensor:
    if norm is None:
        return torch.tensor(vec, dtype=torch.float32)
    mean = norm["mean"]
    std = norm["std"]
    return torch.tensor(
        [(v - m) / (s if s > 1e-6 else 1.0) for v, m, s in zip(vec, mean, std)],
        dtype=torch.float32,
    )


@torch.no_grad()
def score(gs, player, opponent, deck: str = "tes") -> Optional[float]:
    """Return P(<deck> wins | current state) ∈ [0, 1]."""
    model = load_scorer(deck)
    if model is None:
        return None
    vec = encode_state_vec(gs, player, opponent)
    norm = _cache[deck][1] if deck in _cache else None
    x = _normalize(vec, norm).unsqueeze(0)
    return float(model(x).item())
