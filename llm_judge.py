#!/usr/bin/env python3
"""
llm_judge.py — Collect simulation traces for LLM-graded AI audit (§9 #7).

PLANNING_REFERENCE.md §9 #7 specifies a "6-expert panel" that grades
strategic decisions across domains (mulligan, mana, combat, combo,
interaction, meta). This script builds the trace-collection scaffold
so graded data is ready the moment an LLM endpoint is available.

No LLM calls here. Output is a JSON file + human-readable summary;
the actual LLM prompt/response loop is left to a downstream consumer
(e.g. `scripts/grade_traces.py` calling `anthropic.messages.create`).

Usage:
    # Collect traces for storm-vs-dnt (the flagship P0 matchup)
    python3 llm_judge.py collect storm dnt --seeds 42 99 7 2026

    # Show existing trace files + their summary stats
    python3 llm_judge.py list

    # Produce the prompt bundle ready for LLM grading
    python3 llm_judge.py bundle results/traces/storm_vs_dnt_*.json

Output schema (results/traces/<d1>_vs_<d2>_s<seed>.json):
    {
      "matchup": "storm_vs_dnt",
      "seed": 42,
      "winner": "p2",
      "win_reason": "...",
      "kill_turn": 15,
      "game_length": 16,
      "p1_mulls": 0, "p2_mulls": 0,
      "opening_hands": {"p1": [...], "p2": [...]},
      "strategic_decisions": [
        {"turn": 1, "deck": "storm", "phase": "setup", "chosen": "pass",
         "candidates": [...], "reason": "..."},
        ...
      ],
      "full_log": [...]
    }

Rubric (from PLANNING_REFERENCE §9 #7):
    mulligan       — keep/mull defensibility
    mana           — resource efficiency, tap sequencing
    combat         — attack/block decisions
    combo          — assembly-and-execution quality
    interaction    — counter/removal timing
    meta           — matchup-aware adjustments

Grade scale: A+ / A / B+ / B / C+ / C / D / F per domain.
"""
import argparse
import glob
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim import run_game


HERE = Path(__file__).resolve().parent
TRACE_DIR = HERE / 'results' / 'traces'
TRACE_DIR.mkdir(parents=True, exist_ok=True)


RUBRIC_DOMAINS = ('mulligan', 'mana', 'combat', 'combo', 'interaction', 'meta')
GRADE_SCALE = ('A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F')

GRADING_PROMPT_TEMPLATE = """You are a Legacy MTG grandmaster grading an AI's play in a simulated game.

Matchup: {matchup}
Seed: {seed}
Result: {winner} ({win_reason}) on turn {kill_turn} of {game_length}

Opening hands:
  P1 ({deck1}): {p1_hand}
  P2 ({deck2}): {p2_hand}

Strategic decision trace ({n_decisions} entries):
{decisions_block}

Full log (first 40 lines):
{log_excerpt}

Grade the **{deck1}** player on each domain. For each domain, output a
single line of the form:
    <domain>: <grade> — <one-sentence justification>

Domains: mulligan, mana, combat, combo, interaction, meta
Grade scale: A+, A, B+, B, C+, C, D, F

Also output a final "overall: <grade> — <summary>" line.
"""


def build_prompt(trace: dict) -> str:
    """Build the LLM grading prompt from a trace dict.

    Importable helper so downstream consumers (e.g. scripts/grade_traces.py)
    don't duplicate the templating logic.
    """
    decisions_block = '\n'.join(
        f"  T{x['turn']} [{x['deck']}]"
        + (f" [phase:{x['phase']}]" if x.get('phase') else '')
        + f" chose {x['chosen']} from {x['candidates']} — {x['reason']}"
        for x in trace['strategic_decisions']
    ) or '  (no decisions logged)'
    log_excerpt = '\n'.join(trace['full_log'][:40])

    return GRADING_PROMPT_TEMPLATE.format(
        matchup=trace['matchup'],
        seed=trace['seed'],
        winner=trace['winner'],
        win_reason=trace['win_reason'],
        kill_turn=trace.get('kill_turn') or 'N/A',
        game_length=trace['game_length'],
        deck1=trace['deck1'],
        deck2=trace['deck2'],
        p1_hand=', '.join(trace['opening_hands']['p1']),
        p2_hand=', '.join(trace['opening_hands']['p2']),
        n_decisions=len(trace['strategic_decisions']),
        decisions_block=decisions_block,
        log_excerpt=log_excerpt,
    )


def collect(deck1, deck2, seeds):
    """Run one game per seed, dump trace to JSON. Returns list of paths written."""
    out_paths = []
    for seed in seeds:
        random.seed(seed)
        r = run_game(deck1, deck2, trace=True)

        decisions = []
        for line in r.log_lines:
            if ' chose ' not in line or '[' not in line:
                continue
            # "T3 [storm] [phase:combo] chose kill_C from [...] — reason"
            try:
                parts = line.split(' chose ', 1)
                header, rest = parts
                action, reason = rest.split(' — ', 1) if ' — ' in rest else (rest, '')
                chosen = action.split(' from ', 1)[0].strip()
                cands_raw = action.split('[', 1)[1].rstrip(']').strip() if '[' in action else ''
                candidates = [c.strip() for c in cands_raw.split(',')] if cands_raw else []
                turn = int(header.split()[0].lstrip('T'))
                deck = header.split('[', 1)[1].split(']')[0]
                phase = None
                if '[phase:' in header:
                    phase = header.split('[phase:', 1)[1].split(']')[0]
                decisions.append({
                    'turn': turn, 'deck': deck, 'phase': phase,
                    'chosen': chosen, 'candidates': candidates,
                    'reason': reason.strip(),
                })
            except (IndexError, ValueError):
                continue

        out = {
            'matchup': f"{deck1}_vs_{deck2}",
            'deck1': deck1,
            'deck2': deck2,
            'seed': seed,
            'winner': r.winner,
            'win_reason': r.win_reason,
            'kill_turn': r.kill_turn,
            'game_length': r.game_length,
            'p1_mulls': r.p1_mulls,
            'p2_mulls': r.p2_mulls,
            'opening_hands': {
                'p1': r.p1_opening_hand,
                'p2': r.p2_opening_hand,
            },
            'strategic_decisions': decisions,
            'full_log': r.log_lines,
        }
        fname = TRACE_DIR / f"{deck1}_vs_{deck2}_s{seed}.json"
        with open(fname, 'w') as f:
            json.dump(out, f, indent=2)
        out_paths.append(fname)
        print(f"  ✓ {fname.name}  (winner={r.winner}, {len(decisions)} decisions, {r.game_length}t)")
    return out_paths


def list_traces():
    files = sorted(TRACE_DIR.glob('*.json'))
    if not files:
        print("(no traces in results/traces)")
        return
    print(f"{len(files)} traces in {TRACE_DIR}:")
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        print(f"  {f.name}  {d['matchup']:<25} s{d['seed']:<5} "
              f"winner={d['winner']}  "
              f"decisions={len(d['strategic_decisions']):<3}  "
              f"T={d['game_length']}")


def bundle(paths):
    """Write one LLM-ready prompt per trace to results/traces/<name>_prompt.txt."""
    written = []
    for path in paths:
        with open(path) as f:
            d = json.load(f)
        prompt = build_prompt(d)
        out_path = Path(path).with_name(Path(path).stem + '_prompt.txt')
        with open(out_path, 'w') as f:
            f.write(prompt)
        written.append(out_path)
        print(f"  wrote {out_path.name}  ({len(prompt)} chars)")
    return written


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    pc = sub.add_parser('collect', help='Run a matchup at N seeds, dump traces')
    pc.add_argument('deck1')
    pc.add_argument('deck2')
    pc.add_argument('--seeds', type=int, nargs='+', default=[42])

    sub.add_parser('list', help='List existing trace files')

    pb = sub.add_parser('bundle', help='Build LLM-ready prompts from traces')
    pb.add_argument('paths', nargs='+')

    args = p.parse_args()
    if args.cmd == 'collect':
        paths = collect(args.deck1, args.deck2, args.seeds)
        print(f"\nNext step: python3 llm_judge.py bundle {' '.join(str(p) for p in paths)}")
    elif args.cmd == 'list':
        list_traces()
    elif args.cmd == 'bundle':
        written = bundle(args.paths)
        print(f"\nFeed each *_prompt.txt to the LLM of choice; capture the "
              f"per-domain grade lines for the report.")


if __name__ == '__main__':
    main()
