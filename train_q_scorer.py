"""Train the Q-style discriminator (Lever 5).

Reads `traces/ur_delver_q.jsonl` (from `scripts/collect_q_data.py`) and
trains one model per `decision_type` (e.g. `q_ur_bolt_mode`). The label
is `rollout_won` (1 if the protagonist won the rollout from this state
after taking this action, else 0).

Output:
  models/q_<decision_type>.pt
  models/q_<decision_type>_norm.json   (per-feature mean/std on train split)

Usage:
    python3 train_q_scorer.py --in traces/ur_delver_q.jsonl --epochs 50
"""

from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from q_scorer import QScorer, ACTION_VOCAB, _paths_for
from state_encoder import FEATURE_ORDER


def _load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _materialize(rows: Iterable[dict],
                 decision_type: str) -> tuple[torch.Tensor, torch.Tensor]:
    vocab = ACTION_VOCAB[decision_type]
    xs: list[list[float]] = []
    ys: list[float] = []
    skipped = 0
    for r in rows:
        if r.get("decision_type") != f"q_{decision_type.replace('q_','')}":
            # rows have decision_type 'q_<name>'; we accept both forms
            if r.get("decision_type") != decision_type:
                continue
        state = r.get("state")
        action = r.get("decision_value")
        if not state or action not in vocab:
            skipped += 1
            continue
        try:
            sv = [float(state[k]) for k in FEATURE_ORDER]
        except KeyError:
            skipped += 1
            continue
        oh = [0.0] * len(vocab)
        oh[vocab.index(action)] = 1.0
        xs.append(sv + oh)
        ys.append(float(r.get("rollout_won", 0)))
    if skipped:
        print(f"  [skipped {skipped} rows missing fields]")
    return (torch.tensor(xs, dtype=torch.float32),
            torch.tensor(ys, dtype=torch.float32))


def _norm_stats_state_only(x: torch.Tensor, n_state: int) -> dict:
    """Normalise the state portion only — leave one-hot action dims as-is."""
    mean = x[:, :n_state].mean(dim=0)
    std = x[:, :n_state].std(dim=0)
    return {"mean": mean.tolist(), "std": std.tolist()}


def _apply_norm_state_only(x: torch.Tensor, stats: dict, n_state: int) -> torch.Tensor:
    mean = torch.tensor(stats["mean"], dtype=torch.float32)
    std = torch.tensor(stats["std"], dtype=torch.float32)
    std = torch.where(std < 1e-6, torch.ones_like(std), std)
    state = (x[:, :n_state] - mean) / std
    return torch.cat([state, x[:, n_state:]], dim=1)


def _train_one(rows: list[dict], decision_type: str,
               epochs: int, batch_size: int, lr: float,
               val_split: float, seed: int) -> bool:
    torch.manual_seed(seed)
    n_state = len(FEATURE_ORDER)
    n_actions = len(ACTION_VOCAB[decision_type])
    print(f"\n=== {decision_type} (state={n_state} + actions={n_actions}) ===")

    x_all, y_all = _materialize(rows, decision_type)
    if x_all.size(0) < 50:
        print(f"  [skip] only {x_all.size(0)} rows — need ≥ 50")
        return False
    print(f"[shape] x={tuple(x_all.shape)}  y={tuple(y_all.shape)}")
    print(f"[label] mean={y_all.mean().item():.3f} (rollout_won rate)")

    n = x_all.size(0)
    n_val = max(10, int(n * val_split))
    perm = torch.randperm(n)
    val_idx, train_idx = perm[:n_val], perm[n_val:]
    x_tr, y_tr = x_all[train_idx], y_all[train_idx]
    x_va, y_va = x_all[val_idx], y_all[val_idx]
    print(f"[split] train={x_tr.size(0)}  val={x_va.size(0)}")

    stats = _norm_stats_state_only(x_tr, n_state)
    x_tr_n = _apply_norm_state_only(x_tr, stats, n_state)
    x_va_n = _apply_norm_state_only(x_va, stats, n_state)

    loader = DataLoader(TensorDataset(x_tr_n, y_tr),
                        batch_size=batch_size, shuffle=True)

    model = QScorer(n_actions)
    opt = optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCELoss()

    baseline_acc = float((y_va.round() == y_va.mean().round()).float().mean())
    print(f"[baseline] majority-class val acc = {baseline_acc:.3f}")

    val_acc = 0.0
    for epoch in range(epochs):
        model.train()
        for xb, yb in loader:
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred_va = model(x_va_n)
            val_loss = loss_fn(pred_va, y_va).item()
            val_acc = float(((pred_va >= 0.5).float() == y_va).float().mean())
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:3d}/{epochs}  val_loss={val_loss:.4f}  "
                  f"val_acc={val_acc:.3f}")

    ckpt_path, norm_path = _paths_for(decision_type)
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), ckpt_path)
    norm_path.write_text(json.dumps(stats))
    print(f"[save] {ckpt_path} + {norm_path}")
    print(f"[summary] {decision_type}: val_acc={val_acc:.3f}  "
          f"baseline={baseline_acc:.3f}  lift={val_acc - baseline_acc:+.3f}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="input_path", default="traces/ur_delver_q.jsonl")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = _load_rows(Path(args.input_path))
    print(f"[load] {len(rows)} rows from {args.input_path}")

    # Normalise decision_type field — strip the 'q_' prefix used in
    # collected rows so it matches ACTION_VOCAB keys.
    for r in rows:
        dt = r.get("decision_type", "")
        if dt.startswith("q_"):
            r["decision_type"] = dt[2:]

    by_type = defaultdict(int)
    for r in rows:
        by_type[r.get("decision_type", "?")] += 1
    print(f"[per-type counts] {dict(by_type)}")

    trained = 0
    for decision_type in ACTION_VOCAB:
        if _train_one(rows, decision_type, args.epochs, args.batch_size,
                      args.lr, args.val_split, args.seed):
            trained += 1
    print(f"\n[done] trained {trained} models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
