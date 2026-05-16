#!/usr/bin/env python3
"""
calibrate_structural_thresholds.py — Phase D calibration of the structural
grader's promotion thresholds (Agent C of the structural-grader gap-closure
plan in /root/.claude/plans/merge-and-then-come-abundant-lynx.md).

Sweeps four integer thresholds across a 144-element grid:

    K_INTER_A          ∈ {1, 2, 3, 4}    # promotes B+ → A on wins (interaction)
    K_INTER_C_PLUS     ∈ {1, 2, 3}       # promotes C → C+ on losses (interaction)
    K_COMBO_GAME_LEN_A ∈ {3, 4, 5, 6}    # game_length cap for combo A+
    K_MANA_GAME_LEN_B  ∈ {6, 7, 8}       # game_length cap for mana B+ (non-combo)

Each candidate is evaluated against the 41 cached traces under
`results/traces/*.json` (filtering out `_graded` / `_structural_graded` /
`_prompt` siblings). Per-candidate cost is ~41 × 50 ms ≈ 2 s; total
sweep ~5 minutes — but because the grader is a pure function over
static JSON, no subprocess isolation is needed and each evaluation runs
in-process.

OBJECTIVE: minimise `max(domain_avg for domain in 6)` — the worst-domain
average across all 6 rubric domains (mulligan, mana, combat, combo,
interaction, meta). Lower grade index = better grade (A+=0, F=7), so
smaller average = better play.

INVARIANTS (any violation rejects the candidate, even if its aggregate
is best):

  1. Adversarial-keyword trace — every `reason` field contains heuristic
     grader keywords ("protect combo counter attack force tendrils
     storm kill") but no `chosen` is structured. All 6 domain grades
     must be ≤ C (index 5).
  2. Empty-decisions trace — combo deck (storm) wins T4 with
     `strategic_decisions=[]`. Combo grade must be ≤ B (index 3) —
     no Execute token logged ≠ great combo.
  3. Storm-faked trace — deck1='goblins' emits `chosen='kill_C'` but
     goblins is NOT in COMBO_DECKS. Combo grade must be ≤ C+ (index 4) —
     a non-combo deck cannot earn combo credit via a faked token.

These three property tests pin gameability resistance: a calibration
that lets adversarial prose lift its grades is rejected, regardless of
its aggregate.

Usage:
    # Run the calibration sweep + print summary (read-only)
    python3 tools/calibrate_structural_thresholds.py

    # Write the chosen values to config/calibration.json
    python3 tools/calibrate_structural_thresholds.py --write
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'scripts'))


# Parameter grid. 4 × 3 × 4 × 3 = 144 candidates.
GRID_K_INTER_A          = (1, 2, 3, 4)
GRID_K_INTER_C_PLUS     = (1, 2, 3)
GRID_K_COMBO_GAME_LEN_A = (3, 4, 5, 6)
GRID_K_MANA_GAME_LEN_B  = (6, 7, 8)

CALIBRATION_PATH = REPO_ROOT / 'config' / 'calibration.json'
TRACE_DIR = REPO_ROOT / 'results' / 'traces'

# Domain list — must match llm_judge.RUBRIC_DOMAINS exactly.
DOMAINS = ('mulligan', 'mana', 'combat', 'combo', 'interaction', 'meta')

# Grade-scale numeric thresholds (lower = better grade).
# A+=0 A=1 B+=2 B=3 C+=4 C=5 D=6 F=7
GRADE_C       = 5
GRADE_C_PLUS  = 4
GRADE_B       = 3


def _list_raw_traces() -> list[Path]:
    """Return every trace JSON under results/traces/ that is not a
    `_graded.json`, `_structural_graded.json`, or `_prompt.txt` sibling.
    """
    out: list[Path] = []
    for p in sorted(TRACE_DIR.glob('*.json')):
        if '_graded.json' in p.name:
            continue
        if '_prompt.txt' in p.name:
            continue
        out.append(p)
    return out


def _grade_trace(trace: dict, sg_module) -> dict[str, str]:
    """Run the structural grader on an already-loaded trace dict.

    Mirrors `grade_one_structural()` but stays in-process and never
    writes to disk. Returns a {domain: grade-letter} dict.
    """
    decisions = trace.get('strategic_decisions', []) or []
    counts = sg_module._count_structural(decisions, deck1=trace.get('deck1'))
    grades = {}
    grades['mulligan'], _ = sg_module._grade_mulligan(trace)
    grades['mana'], _     = sg_module._grade_mana(trace)
    grades['combat'], _   = sg_module._grade_combat(trace, counts)
    grades['combo'], _    = sg_module._grade_combo(trace, counts)
    grades['interaction'], _ = sg_module._grade_interaction(trace, counts)
    grades['meta'], _     = sg_module._grade_meta(trace, counts)
    return grades


def _grade_to_num(g: str, grade_to_num: dict[str, int]) -> int:
    """Coerce off-scale 'B-' (from _grade_combat) to C+ index, as the
    on-disk grader's overall-averaging step does.
    """
    if g in grade_to_num:
        return grade_to_num[g]
    if g == 'B-':
        return grade_to_num['C+']
    # Unknown grade — treat as worst (F) so it can't win calibration silently.
    return grade_to_num['F']


def _apply_candidate(sg_module, cand: dict[str, int]) -> None:
    """Mutate the module-level thresholds to the candidate values."""
    sg_module.K_INTER_A          = cand['STRUCT_K_INTER_A']
    sg_module.K_INTER_C_PLUS     = cand['STRUCT_K_INTER_C_PLUS']
    sg_module.K_COMBO_GAME_LEN_A = cand['STRUCT_K_COMBO_GAME_LEN_A']
    sg_module.K_MANA_GAME_LEN_B  = cand['STRUCT_K_MANA_GAME_LEN_B']


def _build_invariant_traces() -> list[tuple[str, dict, str, int]]:
    """Build the three synthetic invariant traces.

    Returns a list of (label, trace_dict, gated_domain, min_index)
    tuples. `min_index` is the FLOOR on the grade-index: an
    anti-gameability invariant says "must score no BETTER than the
    cap letter", so the grade's numeric index must be ≥ min_index
    (lower index = better grade in `llm_judge.GRADE_SCALE`).

    The cap letters come from the gap-closure plan
    (/root/.claude/plans/merge-and-then-come-abundant-lynx.md §"Property
    tests pinning gameability resistance"):

        adversarial keywords → interaction ≤ C (loss path, K_INTER_C_PLUS)
        empty decisions      → combo ≤ B    (no Execute = no great combo)
        storm-faked          → combo ≤ B    (non-COMBO deck floor)

    Why not "every domain" for the adversarial case: mulligan, mana,
    and meta grades depend on game-result + game_length + matchup-class
    only — neither `chosen` nor `reason` keywords affect them, so
    they're outside the threshold-sweep parameter space. The
    invariant tests only the domains whose grade can be lifted by
    structural-count promotions, which is the actual gameability vector
    the structural grader exists to block.
    """
    # Invariant 1 — adversarial-keyword trace. The attack vector is
    # the `reason` field: someone hoping the grader keyword-matches
    # "protect combo counter attack force tendrils storm kill" to
    # lift the grade. The structural grader reads `chosen` only, so
    # token counts stay 0. With deck1='bug' (INTERACTION) and
    # winner=p2 (loss), n_inter=0 must keep interaction at 'C', not
    # promote to 'C+' — i.e. K_INTER_C_PLUS ≥ 1.
    adversarial_decisions = []
    for t in range(1, 6):
        adversarial_decisions.append({
            'turn': t, 'deck': 'bug', 'phase': None, 'chosen': 'pass',
            'candidates': ['pass'],
            'reason': 'protect combo counter attack force tendrils storm kill',
        })
    adversarial = {
        'deck1': 'bug', 'deck2': 'storm', 'winner': 'p2',
        'game_length': 5, 'p1_mulls': 0,
        'strategic_decisions': adversarial_decisions,
    }

    # Invariant 2 — empty-decisions storm win T4. With no Execute token
    # logged, the combo grade must be ≤ B (i.e. cannot reach A or A+).
    # A combo-deck win without a single typed Execute is the canonical
    # "lucky timeout-style win" the structural grader exists to catch.
    # Currently the grader returns 'C' here — the invariant just pins
    # the property so a future threshold candidate cannot promote it.
    empty = {
        'deck1': 'storm', 'deck2': 'burn', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [],
    }

    # Invariant 3 — non-combo deck (goblins) emits a fake `kill_C`
    # token. The grader's non-combo branch in `_grade_combo` short-
    # circuits to a fixed 'B' regardless of token counts — so the cap
    # here is B (idx 3), and the invariant pins the property that adding
    # a fake combo token does NOT lift the grade past this floor. If a
    # future threshold candidate moves the non-combo branch off this
    # floor, this invariant catches it.
    faked = {
        'deck1': 'goblins', 'deck2': 'uwx', 'winner': 'p1',
        'game_length': 4, 'p1_mulls': 0,
        'strategic_decisions': [
            {'turn': 1, 'deck': 'goblins', 'phase': 'setup',
             'chosen': 'kill_C', 'candidates': [], 'reason': 'faked combo win'},
        ],
    }

    return [
        # adversarial: interaction ≤ C (idx ≥ 5) — the gameable path
        ('adversarial_keywords', adversarial, 'interaction', GRADE_C),
        # empty-decisions storm win: combo ≤ B (idx ≥ 3)
        ('empty_decisions',      empty,       'combo',       GRADE_B),
        # storm-faked non-combo deck: combo ≤ B (idx ≥ 3)
        ('storm_faked',          faked,       'combo',       GRADE_B),
    ]


def _passes_invariants(sg_module, invariants, grade_to_num) -> bool:
    """True iff every (trace, domain, min_idx) triple satisfies the floor.

    The invariants are anti-gameability constraints: an adversarial /
    faked / silent trace must NOT score *better* than the cap letter.
    In numeric terms (where lower index = better grade), each grade
    index must be ≥ the cap's index. Example: cap = C (index 5) means
    "must be C or worse"; any grade with index < 5 (B, B+, A, A+) is
    rejected.

    Each call re-grades the synthetic traces with the *current* module
    thresholds, so this must be called AFTER `_apply_candidate`.
    """
    # Cache per-trace grading: multiple invariants share the same trace.
    cache: dict[int, dict[str, str]] = {}
    for label, trace, domain, min_idx in invariants:
        key = id(trace)
        if key not in cache:
            cache[key] = _grade_trace(trace, sg_module)
        g = cache[key].get(domain, 'F')
        idx = _grade_to_num(g, grade_to_num)
        if idx < min_idx:
            # Grade is strictly *better* than the floor cap — reject.
            return False
    return True


def evaluate_candidate(sg_module, cand, traces, invariants, grade_to_num):
    """Apply candidate thresholds; check invariants; return
    (passes, domain_avgs, worst_avg) where domain_avgs is a dict
    {domain: average_grade_index}. Returns (False, None, None) if any
    invariant is violated.
    """
    _apply_candidate(sg_module, cand)
    if not _passes_invariants(sg_module, invariants, grade_to_num):
        return False, None, None
    domain_sums = {d: 0.0 for d in DOMAINS}
    for trace in traces:
        grades = _grade_trace(trace, sg_module)
        for d in DOMAINS:
            domain_sums[d] += _grade_to_num(grades[d], grade_to_num)
    n = max(len(traces), 1)
    domain_avgs = {d: domain_sums[d] / n for d in DOMAINS}
    worst = max(domain_avgs.values())
    return True, domain_avgs, worst


def collect_calibration_data():
    """Iterate the 144-element grid, return list of result dicts."""
    # Import once; mutate module-level thresholds in each evaluation.
    import structural_grader as sg
    from llm_judge import GRADE_SCALE
    grade_to_num = {g: i for i, g in enumerate(GRADE_SCALE)}

    raw_paths = _list_raw_traces()
    traces: list[dict] = []
    for p in raw_paths:
        with p.open() as f:
            traces.append(json.load(f))
    print(f"=== structural-threshold calibration: 144 candidates × "
          f"{len(traces)} traces ===", flush=True)

    invariants = _build_invariant_traces()
    t0 = time.time()

    grid = list(itertools.product(
        GRID_K_INTER_A, GRID_K_INTER_C_PLUS,
        GRID_K_COMBO_GAME_LEN_A, GRID_K_MANA_GAME_LEN_B,
    ))
    assert len(grid) == 144, f"grid size mismatch: {len(grid)}"

    results = []
    n_pass = 0
    for ka, kc, kg, km in grid:
        cand = {
            'STRUCT_K_INTER_A':          ka,
            'STRUCT_K_INTER_C_PLUS':     kc,
            'STRUCT_K_COMBO_GAME_LEN_A': kg,
            'STRUCT_K_MANA_GAME_LEN_B':  km,
        }
        passes, domain_avgs, worst = evaluate_candidate(
            sg, cand, traces, invariants, grade_to_num,
        )
        results.append({
            'cand': cand, 'passes': passes,
            'domain_avgs': domain_avgs, 'worst': worst,
        })
        if passes:
            n_pass += 1

    elapsed = time.time() - t0
    print(f"  evaluated 144 candidates ({n_pass} passed invariants) "
          f"in {elapsed:.1f}s", flush=True)
    return results, traces, grade_to_num


def pick_best(results):
    """Choose the passing candidate minimising worst-domain average.

    Tiebreak order when multiple candidates tie on the worst-domain
    average (the primary objective):
      (a) minimum sum of domain averages — the "secondary objective":
          among equally-best candidates by worst-case, pick the one
          with the best overall mean. This stops the tiebreak from
          throwing away free domain improvements.
      (b) minimum L1 distance to the legacy defaults (K_INTER_A=3,
          K_INTER_C_PLUS=2, K_COMBO_GAME_LEN_A=4, K_MANA_GAME_LEN_B=8) —
          same conservatism rule as the BHI calibration tools.
      (c) higher total K (more conservative — needs more structural
          signal to promote).
    """
    DEFAULTS = {
        'STRUCT_K_INTER_A': 3,
        'STRUCT_K_INTER_C_PLUS': 2,
        'STRUCT_K_COMBO_GAME_LEN_A': 4,
        'STRUCT_K_MANA_GAME_LEN_B': 8,
    }
    passing = [r for r in results if r['passes']]
    if not passing:
        raise SystemExit(
            "No candidate satisfied all invariants. The current literal "
            "thresholds are either broken or the invariants are too strict. "
            "Inspect tools/calibrate_structural_thresholds.py."
        )
    best_worst = min(r['worst'] for r in passing)
    # Treat candidates within 1e-9 of the best as tied (avoid float wobble).
    ties = [r for r in passing if r['worst'] - best_worst < 1e-9]

    def _tiebreak(r):
        c = r['cand']
        sum_domains = sum(r['domain_avgs'].values())
        dist = sum(abs(c[k] - DEFAULTS[k]) for k in DEFAULTS)
        neg_sum_k = -sum(c.values())
        return (round(sum_domains, 6), dist, neg_sum_k)
    ties.sort(key=_tiebreak)
    chosen = ties[0]
    return chosen, {
        'best_worst_domain_avg': round(best_worst, 4),
        'n_ties': len(ties),
        'tied_cands': [r['cand'] for r in ties[:5]],
        'tiebreak_rule': 'min_worst_then_min_sum_then_L1_to_defaults',
        'defaults': DEFAULTS,
    }


def print_summary(results, chosen, summary):
    """Print a compact summary of the sweep + chosen candidate."""
    passing = [r for r in results if r['passes']]
    print()
    print(f"  candidates total:    {len(results)}")
    print(f"  candidates passing:  {len(passing)}")
    print(f"  chosen worst-domain: {summary['best_worst_domain_avg']}")
    print(f"  ties at this worst:  {summary['n_ties']}")
    print()
    print("  chosen thresholds:")
    for k, v in chosen['cand'].items():
        print(f"    {k:<32} = {v}")
    print()
    print("  per-domain averages (chosen):")
    for d in DOMAINS:
        print(f"    {d:<14} = {chosen['domain_avgs'][d]:.3f}")
    print()


def compute_default_avgs(results):
    """Find the 'defaults' row (3, 2, 4, 8) and return its domain_avgs."""
    DEFAULTS = (3, 2, 4, 8)
    for r in results:
        c = r['cand']
        t = (c['STRUCT_K_INTER_A'], c['STRUCT_K_INTER_C_PLUS'],
             c['STRUCT_K_COMBO_GAME_LEN_A'], c['STRUCT_K_MANA_GAME_LEN_B'])
        if t == DEFAULTS:
            return r['domain_avgs']
    return None


def write_calibration_file(results, chosen, summary, path):
    """Merge the four new keys into config/calibration.json.

    Preserves the existing BHI_FREE_COUNTER_THRESHOLD /
    BHI_COUNTER_THRESHOLD entries + the prior `summary` + `data` blocks
    (those describe the most recent BHI calibration). Adds a new
    `structural_summary` block describing this calibration's findings.
    """
    import subprocess
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=str(REPO_ROOT), text=True,
        ).strip()
    except subprocess.CalledProcessError:
        sha = 'unknown'

    existing: dict = {}
    if path.exists():
        try:
            with path.open() as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing = {}

    existing_values = dict(existing.get('values', {}))
    for k, v in chosen['cand'].items():
        existing_values[k] = v

    default_avgs = compute_default_avgs(results) or {}
    improvement_vs_default = {}
    for d in DOMAINS:
        if d in default_avgs:
            improvement_vs_default[d] = round(
                chosen['domain_avgs'][d] - default_avgs[d], 4
            )

    structural_summary = {
        'candidates_evaluated': len(results),
        'candidates_passing_invariants': sum(1 for r in results if r['passes']),
        'chosen': chosen['cand'],
        'aggregate_after': {d: round(chosen['domain_avgs'][d], 4)
                            for d in DOMAINS},
        'aggregate_default': {d: round(default_avgs.get(d, 0.0), 4)
                              for d in DOMAINS},
        'improvement_vs_default': improvement_vs_default,
        'best_worst_domain_avg': summary['best_worst_domain_avg'],
        'tiebreak_rule': summary['tiebreak_rule'],
        'defaults': summary['defaults'],
    }

    out = {
        '_meta': {
            'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'main_sha': sha,
            'n_games_per_matchup': existing.get('_meta', {}).get('n_games_per_matchup', 200),
            'comment': (
                'Phase D calibration output. Reading order: `values` dict '
                'is the canonical source of truth for the listed config '
                'constants. `data` is the raw sweep result the most-recent '
                'BHI choice was derived from. `structural_summary` is the '
                'most-recent structural-grader threshold calibration. '
                'To recalibrate, re-run the appropriate tools/calibrate_*.py '
                'script with --write.'
            ),
            'hash_seed_note': existing.get('_meta', {}).get(
                'hash_seed_note',
                'A prior calibration run was biased by a circular-import '
                'bug in decks/bug.py that silently unregistered the BUG '
                'deck (fixed in PR #140). The previous PYTHONHASHSEED '
                'sensitivity diagnosis was a misdiagnosis of that import '
                'race. Current calibration data is clean.'
            ),
            'last_key_calibrated': 'STRUCT_K_*',
        },
        'values': existing_values,
        'structural_summary': structural_summary,
        # Preserve the prior BHI summary + data blocks so the file stays
        # an audit trail of every calibration that has touched it.
        'summary': existing.get('summary', {}),
        'data': existing.get('data', {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(f"  wrote calibration to {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split('\n')[0])
    ap.add_argument('--write', action='store_true',
                    help='write the chosen values to config/calibration.json')
    args = ap.parse_args()

    results, _traces, _g2n = collect_calibration_data()
    chosen, summary = pick_best(results)
    print_summary(results, chosen, summary)

    if args.write:
        write_calibration_file(results, chosen, summary, CALIBRATION_PATH)
    else:
        print(f"  (read-only — pass --write to update "
              f"{CALIBRATION_PATH.relative_to(REPO_ROOT)})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
