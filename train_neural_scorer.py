"""Supervised trainer for the TES win-probability scorer (Phase 3).

Reads `traces/tes_burn.jsonl` (from `scripts/collect_tes_traces.py`),
encodes each row into the canonical 40-feature vector, and trains the
40 → 32 → 16 → 1 MLP from `neural_scorer.py` to predict
`tes_won` (1 if TES won this game, 0 otherwise).

Outputs:
  * `models/tes_scorer.pt`              — model state_dict
  * `models/tes_scorer_norm.json`       — per-feature mean/std for inference

Usage:
    python3 train_neural_scorer.py --epochs 40 --in traces/tes_burn.jsonl
"""

from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from neural_scorer import TesScorer, CHECKPOINT_PATH as DEFAULT_CHECKPOINT
from neural_scorer import NORM_STATS_PATH as DEFAULT_NORM_STATS
from state_encoder import FEATURE_ORDER


def _load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _materialize(rows: Iterable[dict]) -> tuple[torch.Tensor, torch.Tensor]:
    xs: list[list[float]] = []
    ys: list[float] = []
    for r in rows:
        state = r.get("state")
        if not state:
            continue
        try:
            vec = [float(state[k]) for k in FEATURE_ORDER]
        except KeyError as e:
            # Older row schema — skip rather than fail the whole run.
            print(f"  [skip] missing feature {e!r}")
            continue
        xs.append(vec)
        ys.append(float(r.get("tes_won", 0)))
    return (torch.tensor(xs, dtype=torch.float32),
            torch.tensor(ys, dtype=torch.float32))


def _norm_stats(x: torch.Tensor) -> dict:
    mean = x.mean(dim=0)
    std = x.std(dim=0)
    return {"mean": mean.tolist(), "std": std.tolist()}


def _apply_norm(x: torch.Tensor, stats: dict) -> torch.Tensor:
    mean = torch.tensor(stats["mean"], dtype=torch.float32)
    std = torch.tensor(stats["std"], dtype=torch.float32)
    std = torch.where(std < 1e-6, torch.ones_like(std), std)
    return (x - mean) / std


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="input_path", default="traces/tes_burn.jsonl")
    ap.add_argument("--out-prefix", default=None,
                    help="path prefix for outputs; '<prefix>.pt' + "
                         "'<prefix>_norm.json' (default: tes_scorer)")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if args.out_prefix is None:
        ckpt_path = DEFAULT_CHECKPOINT
        norm_path = DEFAULT_NORM_STATS
    else:
        ckpt_path = Path(f"{args.out_prefix}.pt")
        norm_path = Path(f"{args.out_prefix}_norm.json")

    torch.manual_seed(args.seed)

    rows = _load_rows(Path(args.input_path))
    print(f"[load] {len(rows)} rows from {args.input_path}")

    x_all, y_all = _materialize(rows)
    print(f"[shape] x={tuple(x_all.shape)}  y={tuple(y_all.shape)}")
    print(f"[label] mean={y_all.mean().item():.3f} (TES win-rate in trace)")

    # Train / val split (deterministic via seed).
    n = x_all.size(0)
    n_val = max(1, int(n * args.val_split))
    perm = torch.randperm(n)
    val_idx, train_idx = perm[:n_val], perm[n_val:]
    x_tr, y_tr = x_all[train_idx], y_all[train_idx]
    x_va, y_va = x_all[val_idx], y_all[val_idx]
    print(f"[split] train={x_tr.size(0)}  val={x_va.size(0)}")

    # Per-feature normalization fitted on the training half only.
    stats = _norm_stats(x_tr)
    x_tr_n = _apply_norm(x_tr, stats)
    x_va_n = _apply_norm(x_va, stats)

    loader = DataLoader(TensorDataset(x_tr_n, y_tr),
                        batch_size=args.batch_size, shuffle=True)

    model = TesScorer(input_dim=len(FEATURE_ORDER))
    opt = optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCELoss()

    baseline_acc = float((y_va.round() == y_va.mean().round()).float().mean())
    print(f"[baseline] majority-class val acc = {baseline_acc:.3f}")

    for epoch in range(args.epochs):
        model.train()
        ep_loss = 0.0
        n_batches = 0
        for xb, yb in loader:
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            ep_loss += loss.item()
            n_batches += 1
        ep_loss /= max(1, n_batches)

        model.eval()
        with torch.no_grad():
            pred_va = model(x_va_n)
            val_loss = loss_fn(pred_va, y_va).item()
            pred_class = (pred_va >= 0.5).float()
            val_acc = float((pred_class == y_va).float().mean())

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:3d}/{args.epochs}  "
                  f"train_loss={ep_loss:.4f}  val_loss={val_loss:.4f}  "
                  f"val_acc={val_acc:.3f}")

    # Save model + norm stats.
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), ckpt_path)
    norm_path.write_text(json.dumps(stats))
    print(f"[save] {ckpt_path}  +  {norm_path}")
    print(f"[summary] final val_acc={val_acc:.3f}  baseline={baseline_acc:.3f}  "
          f"lift={val_acc - baseline_acc:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
