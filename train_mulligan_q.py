"""Train the mulligan Q-net (Lever 6).

Reads `traces/<deck>_mulligan_q.jsonl` (from `scripts/collect_mulligan_q.py`).
Saves `models/q_mulligan.pt` + `models/q_mulligan_norm.json`.

Usage:
    python3 train_mulligan_q.py --in traces/ur_delver_mulligan_q.jsonl --epochs 80
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from mulligan_features import HAND_FEATURE_ORDER
from mulligan_q import MulliganQ, ACTION_VOCAB, CHECKPOINT_PATH, NORM_PATH


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="input_path",
                    default="traces/ur_delver_mulligan_q.jsonl")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    torch.manual_seed(args.seed)

    rows = [json.loads(l) for l in Path(args.input_path).open() if l.strip()]
    print(f"[load] {len(rows)} rows from {args.input_path}")

    n_state = len(HAND_FEATURE_ORDER)
    n_actions = len(ACTION_VOCAB)

    xs = []
    ys = []
    skipped = 0
    for r in rows:
        state = r.get("state")
        action = r.get("decision_value")
        if not state or action not in ACTION_VOCAB:
            skipped += 1
            continue
        try:
            sv = [float(state[k]) for k in HAND_FEATURE_ORDER]
        except KeyError:
            skipped += 1
            continue
        oh = [0.0] * n_actions
        oh[ACTION_VOCAB.index(action)] = 1.0
        xs.append(sv + oh)
        ys.append(float(r.get("rollout_won", 0)))
    if skipped:
        print(f"  [skipped {skipped} rows]")

    x_all = torch.tensor(xs, dtype=torch.float32)
    y_all = torch.tensor(ys, dtype=torch.float32)
    print(f"[shape] x={tuple(x_all.shape)}  y={tuple(y_all.shape)}  "
          f"label_mean={y_all.mean().item():.3f}")

    n = x_all.size(0)
    n_val = max(50, int(n * args.val_split))
    perm = torch.randperm(n)
    val_idx, train_idx = perm[:n_val], perm[n_val:]
    x_tr, y_tr = x_all[train_idx], y_all[train_idx]
    x_va, y_va = x_all[val_idx], y_all[val_idx]
    print(f"[split] train={x_tr.size(0)}  val={x_va.size(0)}")

    # Normalise the state portion only — pass action one-hots through.
    mean = x_tr[:, :n_state].mean(dim=0)
    std = x_tr[:, :n_state].std(dim=0)
    std = torch.where(std < 1e-6, torch.ones_like(std), std)
    def _norm(x: torch.Tensor) -> torch.Tensor:
        s = (x[:, :n_state] - mean) / std
        return torch.cat([s, x[:, n_state:]], dim=1)
    x_tr_n = _norm(x_tr)
    x_va_n = _norm(x_va)

    loader = DataLoader(TensorDataset(x_tr_n, y_tr),
                        batch_size=args.batch_size, shuffle=True)

    model = MulliganQ()
    opt = optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCELoss()

    baseline_acc = float((y_va.round() == y_va.mean().round()).float().mean())
    print(f"[baseline] majority-class val acc = {baseline_acc:.3f}")

    # Early-stopping: keep the model with the lowest val_loss seen.
    val_acc = 0.0
    best_val_loss = float("inf")
    best_val_acc = 0.0
    best_state: dict | None = None
    best_epoch = 0
    for epoch in range(args.epochs):
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
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = epoch + 1
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:3d}/{args.epochs}  "
                  f"val_loss={val_loss:.4f}  val_acc={val_acc:.3f}")

    # Restore best-checkpoint weights before saving.
    if best_state is not None:
        model.load_state_dict(best_state)
        val_acc = best_val_acc
        print(f"[early-stop] restored epoch {best_epoch} "
              f"(val_loss={best_val_loss:.4f}, val_acc={best_val_acc:.3f})")

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), CHECKPOINT_PATH)
    NORM_PATH.write_text(json.dumps({"mean": mean.tolist(), "std": std.tolist()}))
    print(f"[save] {CHECKPOINT_PATH} + {NORM_PATH}")
    print(f"[summary] val_acc={val_acc:.3f}  baseline={baseline_acc:.3f}  "
          f"lift={val_acc - baseline_acc:+.3f}")

    # Sanity — log a few example decisions on the val set
    model.eval()
    print("\n[examples] (first 6 val rows)")
    n_state_idx = n_state
    for i in range(min(6, x_va.size(0))):
        v = x_va[i].tolist()
        action_idx = v[n_state_idx:].index(1.0) if 1.0 in v[n_state_idx:] else 0
        action = ACTION_VOCAB[action_idx]
        with torch.no_grad():
            p = float(model(x_va_n[i:i+1]).item())
        won = int(y_va[i].item())
        print(f"  action={action:5s}  predicted P(win)={p:.2f}  actual won={won}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
