"""Phase 4 — Ablation evaluation harness for the TES neural pivot.

Runs four configurations against the same seed sequence and produces an
HTML comparison report:
  1. heuristic only          (baseline)
  2. + LLM gate
  3. + small NN scorer
  4. + LLM gate + NN scorer

Each config plays `n` games of `tes` vs `burn` (TES is P1) and `burn`
vs `tes` (TES is P2). The combined P1+P2 win rate is the headline.

Phase 5 stop-condition (codified):
  GREEN  : avg WR delta vs baseline ≥ +5pp
  YELLOW : 0 to +5pp
  RED    : negative

Output: `results/neural_eval_<timestamp>.html`
"""

from __future__ import annotations
import argparse
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sim import run_game


@dataclass
class ConfigResult:
    name: str
    use_neural_gates: bool
    use_neural_scorer: bool
    use_ensemble: bool
    use_rollout: bool
    n_p1: int
    n_p2: int
    p1_wins: int  # protagonist as P1
    p2_wins: int  # protagonist as P2 (i.e. opponent in role P1 lost)
    avg_kill_p1: float
    avg_kill_p2: float
    elapsed_s: float
    p1_deck: str = "tes"
    p2_deck: str = "burn"
    use_q_scorer: bool = False

    @property
    def p1_wr(self) -> float:
        return self.p1_wins / max(1, self.n_p1)

    @property
    def p2_wr(self) -> float:
        return self.p2_wins / max(1, self.n_p2)

    @property
    def combined_wr(self) -> float:
        total = self.n_p1 + self.n_p2
        return (self.p1_wins + self.p2_wins) / max(1, total)


def _wr_ci(wins: int, n: int) -> tuple[float, float]:
    """Wilson 95% CI."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    z = 1.96
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    delta = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - delta), min(1.0, centre + delta))


def run_config(name: str, n: int, seed_start: int,
               use_gates: bool, use_scorer: bool,
               use_ensemble: bool = False,
               use_rollout: bool = False,
               use_q_scorer: bool = False,
               p1_deck: str = "tes", p2_deck: str = "burn") -> ConfigResult:
    t0 = time.time()
    p1_wins = 0
    p1_kt = []
    for i in range(n):
        random.seed(seed_start + i)
        r = run_game(p1_deck, p2_deck,
                     use_neural_gates=use_gates,
                     use_neural_scorer=use_scorer,
                     use_ensemble=use_ensemble,
                     use_rollout=use_rollout,
                     use_q_scorer=use_q_scorer)
        if r.winner == "p1":
            p1_wins += 1
        if r.kill_turn:
            p1_kt.append(r.kill_turn)

    p2_wins = 0
    p2_kt = []
    for i in range(n):
        random.seed(seed_start + 100_000 + i)
        r = run_game(p2_deck, p1_deck,
                     use_neural_gates=use_gates,
                     use_neural_scorer=use_scorer,
                     use_ensemble=use_ensemble,
                     use_rollout=use_rollout,
                     use_q_scorer=use_q_scorer)
        if r.winner == "p2":  # protagonist was P2 and won
            p2_wins += 1
        if r.kill_turn:
            p2_kt.append(r.kill_turn)

    return ConfigResult(
        name=name,
        use_neural_gates=use_gates,
        use_neural_scorer=use_scorer,
        use_ensemble=use_ensemble,
        use_rollout=use_rollout,
        use_q_scorer=use_q_scorer,
        p1_deck=p1_deck, p2_deck=p2_deck,
        n_p1=n, n_p2=n,
        p1_wins=p1_wins, p2_wins=p2_wins,
        avg_kill_p1=sum(p1_kt) / max(1, len(p1_kt)),
        avg_kill_p2=sum(p2_kt) / max(1, len(p2_kt)),
        elapsed_s=time.time() - t0,
    )


def _phase5_banner(delta_pp: float) -> tuple[str, str]:
    if delta_pp >= 5.0:
        return ("#1f883d", "GREEN — scale to 5 more matchups")
    if delta_pp >= 0.0:
        return ("#bf8700", "YELLOW — marginal; archive prototype, resume backlog")
    return ("#cf222e", "RED — revert toggles; document negative result")


def _row_html(cfg: ConfigResult, baseline: ConfigResult) -> str:
    delta = (cfg.combined_wr - baseline.combined_wr) * 100.0
    delta_str = f"{delta:+.1f}pp"
    p1_lo, p1_hi = _wr_ci(cfg.p1_wins, cfg.n_p1)
    p2_lo, p2_hi = _wr_ci(cfg.p2_wins, cfg.n_p2)
    return f"""
        <tr>
          <td><strong>{cfg.name}</strong></td>
          <td><code>{int(cfg.use_neural_gates)}</code></td>
          <td><code>{int(cfg.use_neural_scorer)}</code></td>
          <td><code>{int(cfg.use_ensemble)}</code></td>
          <td><code>{int(cfg.use_rollout)}</code></td>
          <td><code>{int(cfg.use_q_scorer)}</code></td>
          <td>{cfg.p1_wr*100:.1f}% <span class="ci">[{p1_lo*100:.1f}–{p1_hi*100:.1f}]</span></td>
          <td>{cfg.p2_wr*100:.1f}% <span class="ci">[{p2_lo*100:.1f}–{p2_hi*100:.1f}]</span></td>
          <td><strong>{cfg.combined_wr*100:.1f}%</strong></td>
          <td>{delta_str}</td>
          <td>{cfg.avg_kill_p1:.2f} / {cfg.avg_kill_p2:.2f}</td>
          <td>{cfg.elapsed_s:.1f}s</td>
        </tr>
    """


def render_html(results: list[ConfigResult], n: int, out_path: Path) -> None:
    baseline = results[0]
    best = max(results, key=lambda r: r.combined_wr)
    delta_pp = (best.combined_wr - baseline.combined_wr) * 100.0
    color, banner_text = _phase5_banner(delta_pp)
    rows = "\n".join(_row_html(r, baseline) for r in results)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TES Neural-Pivot Eval — {timestamp}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
            sans-serif; max-width: 1000px; margin: 2em auto; padding: 0 1em;
            color: #1f2328; background: #fff; }}
    h1 {{ font-size: 1.6em; border-bottom: 1px solid #d0d7de; padding-bottom: .3em; }}
    h2 {{ font-size: 1.2em; margin-top: 2em; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #d0d7de;
              text-align: left; }}
    th {{ background: #f6f8fa; font-weight: 600; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 3px;
            font-size: 0.9em; }}
    .ci {{ color: #656d76; font-size: 0.85em; }}
    .banner {{ padding: 1em; border-radius: 6px; color: #fff;
               font-weight: 600; font-size: 1.1em;
               background: {color}; margin: 1.5em 0; }}
    .meta {{ color: #656d76; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>TES Neural-Pivot Eval</h1>
  <p class="meta">Generated {timestamp} — n = {n} per side per config —
    matchup <code>tes_vs_burn</code> + <code>burn_vs_tes</code>.</p>

  <div class="banner">
    Phase 5 verdict: best config Δ vs baseline = {delta_pp:+.1f}pp →
    <strong>{banner_text}</strong>
  </div>

  <h2>Configurations</h2>
  <table>
    <thead>
      <tr>
        <th>Config</th>
        <th>gates</th><th>scorer</th><th>ens</th><th>roll</th><th>Q</th>
        <th>P1 WR (on play)</th>
        <th>P2 WR (on draw)</th>
        <th>Combined WR</th>
        <th>Δ vs baseline</th>
        <th>avg kill (P1/P2)</th>
        <th>wall</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>Notes</h2>
  <ul>
    <li>WR cells show 95% Wilson CI. Combined WR averages P1 + P2.</li>
    <li>LLM gate calls hit the <code>claude-opus-4-7</code> model with
        prompt caching; expect ≤ 2 K cached input tokens / call.</li>
    <li>NN scorer is a 40 → 32 → 16 → 1 MLP trained on
        <code>traces/tes_burn.jsonl</code> (val acc ~80%, baseline 70%).</li>
    <li>If a gate/scorer call errors, the strategy falls back to the
        heuristic — no game is forfeited.</li>
  </ul>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200,
                    help="games per side per config")
    ap.add_argument("--seed", type=int, default=10_000,
                    help="seed start (P1 uses seed..seed+n, "
                         "P2 uses seed+100k..seed+100k+n)")
    ap.add_argument("--out", type=str, default=None,
                    help="output HTML path (default auto-timestamped)")
    ap.add_argument("--skip-llm", action="store_true",
                    help="skip configs that require the LLM (no API key, "
                         "or you want pure-NN ablation)")
    args = ap.parse_args()

    if args.out is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        args.out = f"results/neural_eval_{ts}.html"

    print(f"[neural_eval] n={args.n}, seed={args.seed}, out={args.out}")
    print(f"[neural_eval] skip_llm={args.skip_llm}")

    configs: list[tuple[str, bool, bool]] = [
        ("heuristic only (baseline)", False, False),
    ]
    if not args.skip_llm:
        configs.append(("+ LLM gate",                True,  False))
    configs.append(    ("+ NN scorer",               False, True))
    if not args.skip_llm:
        configs.append(("+ LLM gate + NN scorer",   True,  True))

    results: list[ConfigResult] = []
    for name, use_gates, use_scorer in configs:
        print(f"  → {name} (gates={use_gates}, scorer={use_scorer})")
        r = run_config(name, args.n, args.seed, use_gates, use_scorer)
        print(f"     P1 WR {r.p1_wr*100:.1f}%  P2 WR {r.p2_wr*100:.1f}%  "
              f"combined {r.combined_wr*100:.1f}%  ({r.elapsed_s:.1f}s)")
        results.append(r)

    out_path = Path(args.out)
    render_html(results, args.n, out_path)
    print(f"\n[neural_eval] HTML report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
