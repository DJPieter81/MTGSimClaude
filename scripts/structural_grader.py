#!/usr/bin/env python3
"""
structural_grader.py — Prototype structural grader for MTGSimClaude traces.

PROTOTYPE — does NOT replace `scripts/grade_traces.py`. The point is to show
that we can derive meaningful per-domain grades from the *typed* `chosen`
field that strategies now emit (post-Phase-6 + PR #138):

    'defer', 'hold_<tag>', 'kill_<X>', 'cast_<combo>', 'entomb_<tag>',
    'combo:<path_tag>', 'attack with N <creatures>'

…instead of pattern-matching English keywords in the `reason` field (which
is gameable: a strategy could emit "protect" anywhere in `reason` and lift
its interaction grade).

Output shape matches `grade_one_local()` in `scripts/grade_traces.py`. The
graded file is written next to the trace as `<trace>_structural_graded.json`
so the two graders' outputs can coexist for comparison.

Usage:
    # Grade traces
    python3 scripts/structural_grader.py results/traces/*.json

    # Compare structural vs heuristic agreement (reads both _graded.json
    # and _structural_graded.json next to each trace)
    python3 scripts/structural_grader.py --report
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Allow importing llm_judge from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_judge import RUBRIC_DOMAINS, GRADE_SCALE  # noqa: E402
from config import _load_calibrated  # noqa: E402

TRACE_DIR = Path(__file__).resolve().parent.parent / 'results' / 'traces'

# Promotion thresholds — calibrated via tools/calibrate_structural_thresholds.py.
# Each gates the grade promotion in one binding-constraint domain. The literal
# fallback values are the legacy hand-picked numbers; the calibrated values
# live in config/calibration.json under the `values` dict. See
# `_load_calibrated` in config.py for the resolution order.
#
# K_INTER_A          — promotes interaction grade B+ → A on wins for
#                      interaction decks when n_inter ≥ K_INTER_A.
# K_INTER_C_PLUS     — promotes interaction grade C → C+ on losses for
#                      interaction decks when n_inter ≥ K_INTER_C_PLUS.
# K_COMBO_GAME_LEN_A — game_length cap below which a winning combo deck
#                      grades A (vs B+) — i.e. "fast enough kill is A".
# K_MANA_GAME_LEN_B  — game_length cap below which a winning non-combo deck
#                      grades B+ (vs B) on mana.
K_INTER_A          = _load_calibrated('STRUCT_K_INTER_A', 3)
K_INTER_C_PLUS     = _load_calibrated('STRUCT_K_INTER_C_PLUS', 2)
K_COMBO_GAME_LEN_A = _load_calibrated('STRUCT_K_COMBO_GAME_LEN_A', 4)
K_MANA_GAME_LEN_B  = _load_calibrated('STRUCT_K_MANA_GAME_LEN_B', 8)

GRADE_TO_NUM = {g: i for i, g in enumerate(GRADE_SCALE)}
NUM_TO_GRADE = {i: g for g, i in GRADE_TO_NUM.items()}

# Deck-class buckets (kept parallel to grade_traces.py so the comparison
# stays apples-to-apples).
COMBO_DECKS = {
    'storm', 'doomsday', 'oops', 'belcher', 'cephalid', 'reanimator',
    'sneak_a', 'sneak_b', 'show', 'show_fix', 'tes', 'depths', 'elves',
}
INTERACTION_DECKS = {
    'bug', 'dimir', 'dimir_b', 'dimir_c', 'dimir_d', 'dimir_flash',
    'ur_delver', 'ur_tempo', 'uwx', 'dnt', 'mardu',
}
AGGRO_DECKS = {
    'burn', 'goblins', 'eldrazi', 'affinity', 'ur_aggro', 'boros',
}

# Structured-token prefixes / values the strategies emit. Each token is a
# *de-facto API contract* between the strategy layer and any grader: it has
# a fixed meaning that does not depend on prose elsewhere in the entry.
EXECUTE_PREFIXES = ('combo:', 'kill_', 'cast_doomsday', 'cast_spy',
                    'entomb_', 'oracle_win', 't1_kill', 't2_kill')
HOLD_PREFIXES = ('hold_',)
DEFER_TOKENS = {'defer'}
COUNTER_PREFIXES = ('counter_',)   # interaction decks log counter_<spell>_with_<ctr>
DISCARD_PREFIXES = ('discard_',)   # interaction decks log discard_<spell>_with_<ts>
REMOVAL_PREFIXES = ('remove_',)    # removal spells log remove_<target>_with_<spell>
TRIED_COMBO_PREFIXES = ('tried_combo:',)  # combo decks log when a piece was
                                          # played but the full kill did not fire
ATTACK_PREFIX = 'attack'  # 'attack with N goblins'
COMBAT_PHASE = 'combat'


# ─── token-level structural counts ────────────────────────────────────────

def _is_execute(chosen: str) -> bool:
    """Decision indicates the strategy *fired* its combo plan."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in EXECUTE_PREFIXES)


def _is_hold(chosen: str) -> bool:
    """Decision indicates the strategy *withheld* a card (protection / disruption)."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in HOLD_PREFIXES)


def _is_defer(chosen: str) -> bool:
    """Decision indicates the strategy *passed* on firing this turn."""
    return chosen in DEFER_TOKENS


def _is_counter(chosen: str) -> bool:
    """Decision indicates the strategy *countered* an opposing spell."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in COUNTER_PREFIXES)


def _is_discard(chosen: str) -> bool:
    """Decision indicates the strategy *forced opp to discard* a card."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in DISCARD_PREFIXES)


def _is_removal(chosen: str) -> bool:
    """Decision indicates the strategy *removed* an opposing permanent
    (creature, planeswalker, artifact, enchantment) via a spot-removal
    spell (Push, STP, Snuff, Dismember, AD, Bolt-as-removal, Solitude,
    Skyclave Apparition, Fury, Deluge, Pyro/Hydroblast, Force of Vigor)."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in REMOVAL_PREFIXES)


def _is_tried_combo(chosen: str) -> bool:
    """Decision indicates a combo piece was played but the kill did not fire.
    Partial-credit signal for combo decks whose plan was disrupted."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in TRIED_COMBO_PREFIXES)


def _is_combat_decision(decision: dict) -> bool:
    """Combat-axis decision: either tagged with combat phase or attack action."""
    if decision.get('phase') == COMBAT_PHASE:
        return True
    chosen = decision.get('chosen', '') or ''
    return chosen.startswith(ATTACK_PREFIX)


def _count_structural(decisions: list[dict], deck1: str | None = None) -> dict:
    """Bucket decisions by structural token. Returns counts only — no keyword
    pattern matching on `reason`.

    When `deck1` is provided, only decisions emitted by that deck count toward
    the structural buckets. Without this filter, an opponent's typed decision
    (e.g. storm casting TS that hits bug's FoW) would be credited to deck1's
    score — the wrong attribution. The grader's per-domain rules judge
    deck1's play, so its counts must only see deck1's decisions.
    """
    if deck1 is not None:
        decisions = [d for d in decisions if d.get('deck') == deck1]
    counts = {
        'execute': 0, 'hold': 0, 'defer': 0, 'counter': 0, 'discard': 0,
        'removal': 0, 'tried_combo': 0,
        'combat': 0, 'combo_phase': 0, 'protect_phase': 0,
        'total': len(decisions),
    }
    for d in decisions:
        chosen = d.get('chosen', '') or ''
        phase = d.get('phase')
        if _is_execute(chosen):
            counts['execute'] += 1
        if _is_hold(chosen):
            counts['hold'] += 1
        if _is_defer(chosen):
            counts['defer'] += 1
        if _is_counter(chosen):
            counts['counter'] += 1
        if _is_discard(chosen):
            counts['discard'] += 1
        if _is_removal(chosen):
            counts['removal'] += 1
        if _is_tried_combo(chosen):
            counts['tried_combo'] += 1
        if _is_combat_decision(d):
            counts['combat'] += 1
        if phase == 'combo':
            counts['combo_phase'] += 1
        if phase == 'protect' or phase == 'disruption':
            counts['protect_phase'] += 1
    return counts


# ─── per-domain grading from structural counts ────────────────────────────

def _grade_mulligan(trace: dict) -> tuple[str, str]:
    p1_won = trace.get('winner') == 'p1'
    p1_mulls = trace.get('p1_mulls', 0)
    if p1_mulls == 0:
        g = 'B+' if p1_won else 'B'
        j = f"Kept 7; {'won' if p1_won else 'lost'} — opening hand was {'adequate' if p1_won else 'possibly too greedy'}"
    elif p1_mulls == 1:
        g = 'B' if p1_won else 'C+'
        j = f"Mulled to 6; {'still won' if p1_won else 'card disadvantage contributed to loss'}"
    else:
        g = 'C' if p1_won else 'D'
        j = f"Mulled to {7 - p1_mulls}; aggressive mulligan strategy {'paid off' if p1_won else 'backfired'}"
    return g, j


def _grade_mana(trace: dict) -> tuple[str, str]:
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)
    if deck1 in COMBO_DECKS:
        if p1_won and game_length <= 4:
            return 'A', f"Fast kill (T{game_length}) implies efficient mana sequencing"
        if p1_won:
            return 'B+', f"Won but took {game_length} turns — mana was adequate"
        return ('C+' if game_length <= 6 else 'C',
                f"Lost in {game_length} turns — possible mana sequencing issues")
    if p1_won:
        return ('B+' if game_length <= K_MANA_GAME_LEN_B else 'B',
                f"Resource deployment supported a T{game_length} win")
    return ('B' if game_length >= K_MANA_GAME_LEN_B else 'C+',
            f"{'Adequate' if game_length >= K_MANA_GAME_LEN_B else 'Suboptimal'} mana utilization over {game_length} turns")


def _grade_combat(trace: dict, counts: dict) -> tuple[str, str]:
    """Combat grading from structural combat-phase / attack tokens, no English keywords.

    For aggro decks that won, spot-removal tokens (`remove_*`) count toward
    the combat tally too: a bolt or push that killed an opposing blocker
    *enabled* the swing that closed the game. Without crediting removal
    here, an aggro deck that cleared a Bowmasters/Goyf with a Bolt before
    attacking would look like it skipped combat decisioning.
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    n_combat = counts['combat']
    n_removal = counts.get('removal', 0)

    if deck1 in COMBO_DECKS:
        # Combo decks: combat is secondary; absence is neutral.
        return ('B',
                f"Combo deck — {n_combat} combat decision(s); combat is not the primary axis")
    if deck1 in AGGRO_DECKS:
        # Aggro decks: roll spot-removal into the combat tally on wins —
        # a bolt that cleared a blocker is a combat-enabling decision.
        n_combat_aggro = n_combat + (n_removal if p1_won else 0)
        if p1_won and n_combat_aggro >= 1:
            return 'A', (f"Aggro plan with {n_combat} combat + {n_removal} remove "
                         f"decision(s) — pressure converted to win")
        if p1_won:
            return 'B+', "Aggro plan won without surfaced combat decisions (lethal via burn / direct damage)"
        if n_combat >= 1:
            return 'B-', f"Aggro plan logged {n_combat} combat decision(s) but lost — opponent stabilized"
        return 'C', "Aggro deck without combat decisions — combat axis was inactive"
    # Mid-range / interaction / other
    if p1_won:
        return ('B+' if n_combat >= 1 else 'B',
                f"{n_combat} combat decision(s); {'combat contributed to win' if n_combat else 'won via non-combat means'}")
    return ('C+' if n_combat >= 1 else 'C',
            f"{n_combat} combat decision(s); combat axis {'engaged but insufficient' if n_combat else 'inactive'}")


def _grade_combo(trace: dict, counts: dict) -> tuple[str, str]:
    """Combo grading from Execute-token counts, no English keywords.

    Combo-deck losses are promoted one grade (D→C+, C→C+ kept at C+, C+→
    well the rule below preserves the existing C+ for length>5 and only
    lifts the length≤5 D→C+ case) when at least one `tried_combo:<tag>`
    partial-credit token was logged. Encodes "played pieces but kill was
    disrupted" as distinct from "did nothing".
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)
    n_exec = counts['execute']
    n_tried = counts.get('tried_combo', 0)

    if deck1 not in COMBO_DECKS:
        return 'B', "Non-combo deck — domain not primary axis"

    if n_exec == 0:
        # The deck's typed combo plan never fired. If at least one combo
        # piece was played (tried_combo token), promote from baseline C to C+.
        if n_tried >= 1:
            return ('C+',
                    f"No Execute token, but {n_tried} tried_combo token(s) — "
                    f"pieces deployed, kill disrupted")
        return 'C', "No combo Execute decision logged — deck did not fire its plan"
    if p1_won and game_length <= 6:
        return ('A+' if game_length <= K_COMBO_GAME_LEN_A else 'A',
                f"{n_exec} Execute decision(s); combo resolved on T{game_length}")
    if p1_won:
        return 'B+', f"{n_exec} Execute decision(s); combo resolved late on T{game_length}"
    if game_length <= 5:
        # One-grade promotion: D → C+ when at least one tried_combo was emitted.
        if n_tried >= 1:
            return ('C+',
                    f"{n_exec} Execute + {n_tried} tried_combo; "
                    f"lost on T{game_length} — disrupted early but pieces deployed")
        return 'D', f"{n_exec} Execute decision(s) but lost on T{game_length} — disrupted early"
    # game_length > 5
    if n_tried >= 1:
        return ('C',
                f"{n_exec} Execute + {n_tried} tried_combo; "
                f"lost on T{game_length} — combo could not close but pieces deployed")
    return 'C+', f"{n_exec} Execute decision(s) but lost on T{game_length} — combo could not close"


def _grade_interaction(trace: dict, counts: dict) -> tuple[str, str]:
    """Interaction grading from Hold/Defer/Counter-token counts, no English keywords.

    For interaction decks (bug, dimir, ur_delver, …), the relevant
    structural signal is `counter_<spell>_with_<ctr>` tokens emitted by
    `engine._try_counter_any` whenever the deck actually fires a
    counter spell. Hold/Defer tokens (a combo-deck signal) also count.

    For combo decks, Hold/Defer remains the primary signal.
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    n_hold = counts['hold']
    n_defer = counts['defer']
    n_counter = counts.get('counter', 0)
    n_discard = counts.get('discard', 0)
    n_removal = counts.get('removal', 0)
    # Interaction decks earn primary credit from counter_*, discard_*, and
    # remove_* tokens. A spot-removal spell that kills a threat is just as
    # much "interaction" as a counter or a discard — it's how tempo/midrange
    # decks (bug, dimir, ur_delver, …) interact with creature plans.
    n_inter = n_hold + n_defer + n_counter + n_discard + n_removal

    if deck1 in INTERACTION_DECKS:
        if p1_won:
            return ('A' if n_inter >= K_INTER_A else 'B+',
                    f"{n_counter} counter + {n_discard} discard + {n_removal} remove + "
                    f"{n_hold} hold + {n_defer} defer decisions; "
                    f"{'heavy structured disruption' if n_inter >= K_INTER_A else 'measured disruption'} backed the win")
        return ('C+' if n_inter >= K_INTER_C_PLUS else 'C',
                f"{n_counter} counter + {n_discard} discard + {n_removal} remove + "
                f"{n_hold} hold + {n_defer} defer decisions; "
                f"{'logged but insufficient' if n_inter >= K_INTER_C_PLUS else 'not enough disruption surfaced'}")

    if deck1 in COMBO_DECKS:
        # For combo decks, Hold/Defer surfaces *protection*-grade play.
        if p1_won:
            return ('B+' if n_hold >= 1 else 'B',
                    f"{n_hold} hold + {n_defer} defer; {'protected combo via typed hold' if n_hold else 'combo resolved without holding protection'}")
        return ('C+' if n_hold >= 1 else 'C',
                f"{n_hold} hold + {n_defer} defer; {'protection deployed but insufficient' if n_hold else 'no protection token surfaced'}")

    return ('B' if p1_won else 'C+',
            f"{n_hold} hold + {n_defer} defer; interaction tokens {'sufficed' if p1_won else 'fell short'}")


def _grade_meta(trace: dict, counts: dict) -> tuple[str, str]:
    deck1 = trace.get('deck1', '')
    deck2 = trace.get('deck2', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)

    is_favored = deck1 in COMBO_DECKS and deck2 in AGGRO_DECKS
    is_unfavored = deck1 in COMBO_DECKS and deck2 in INTERACTION_DECKS

    if p1_won and is_unfavored:
        return 'A', f"Won an unfavored matchup ({deck1} vs {deck2}) — strong matchup awareness"
    if p1_won:
        return ('B+' if game_length <= 6 else 'B',
                f"{'Efficiently closed' if game_length <= 6 else 'Eventually closed'} {'a favored' if is_favored else 'the'} matchup")
    if not p1_won and is_favored:
        return 'C', f"Lost a matchup that should be favored ({deck1} vs {deck2}) — possible role confusion"
    return ('C+' if counts['total'] >= 5 else 'C',
            f"Lost — {'played actively but could not overcome matchup' if counts['total'] >= 5 else 'limited decision points suggest structural disadvantage'}")


def grade_one_structural(trace_path: Path) -> Path | None:
    """Structural-grade a single trace. Returns path to _structural_graded.json."""
    with open(trace_path) as f:
        trace = json.load(f)

    decisions = trace.get('strategic_decisions', []) or []
    counts = _count_structural(decisions, deck1=trace.get('deck1'))

    grades = {}
    justs = {}
    grades['mulligan'], justs['mulligan'] = _grade_mulligan(trace)
    grades['mana'], justs['mana'] = _grade_mana(trace)
    grades['combat'], justs['combat'] = _grade_combat(trace, counts)
    grades['combo'], justs['combo'] = _grade_combo(trace, counts)
    grades['interaction'], justs['interaction'] = _grade_interaction(trace, counts)
    grades['meta'], justs['meta'] = _grade_meta(trace, counts)

    # Coerce off-scale "B-" → "B" for the averaging step (GRADE_SCALE has no B-).
    overall_nums = []
    for g in grades.values():
        if g in GRADE_TO_NUM:
            overall_nums.append(GRADE_TO_NUM[g])
        elif g == 'B-':
            overall_nums.append(GRADE_TO_NUM['C+'])
    if overall_nums:
        avg = sum(overall_nums) / len(overall_nums)
        nearest = min(NUM_TO_GRADE.keys(), key=lambda k: abs(k - avg))
        grades['overall'] = NUM_TO_GRADE[nearest]
    else:
        grades['overall'] = 'UNGRADED'
    p1_won = trace.get('winner') == 'p1'
    justs['overall'] = (f"Average across 6 domains — {'won' if p1_won else 'lost'} "
                        f"in {trace.get('game_length','?')} turns; "
                        f"structural counts: exec={counts['execute']} "
                        f"hold={counts['hold']} defer={counts['defer']} "
                        f"remove={counts.get('removal', 0)} "
                        f"combat={counts['combat']}")

    raw_lines = []
    for d in list(RUBRIC_DOMAINS) + ['overall']:
        raw_lines.append(f"{d}: {grades[d]} — {justs[d]}")
    raw = '\n'.join(raw_lines)

    graded = {
        'trace_file': trace_path.name,
        'matchup': trace.get('matchup', ''),
        'seed': trace.get('seed', ''),
        'winner': trace.get('winner', ''),
        'win_reason': trace.get('win_reason', ''),
        'kill_turn': trace.get('kill_turn', ''),
        'game_length': trace.get('game_length', ''),
        'deck1': trace.get('deck1', ''),
        'deck2': trace.get('deck2', ''),
        'grades': grades,
        'justifications': justs,
        'structural_counts': counts,
        'raw_response': raw,
        'model': 'structural-v1',
        'graded_at': datetime.utcnow().isoformat() + 'Z',
    }

    out_path = trace_path.with_name(trace_path.stem + '_structural_graded.json')
    with open(out_path, 'w') as f:
        json.dump(graded, f, indent=2)

    grade_str = ' '.join(f"{d}={grades[d]}" for d in RUBRIC_DOMAINS)
    print(f"  + {trace_path.name} -> {grade_str}")
    return out_path


# ─── comparison report ────────────────────────────────────────────────────

def build_report() -> str:
    """Compare structural grades vs heuristic grades per domain.

    Reads `<trace>_graded.json` (heuristic) and `<trace>_structural_graded.json`
    (this script). For each trace where both exist, count per-domain
    agreement. Does not fail on disagreement — the comparison is the point.
    """
    structural_files = sorted(TRACE_DIR.glob('*_structural_graded.json'))
    if not structural_files:
        return ("# No structural-graded traces found\n\n"
                "Run `python3 scripts/structural_grader.py results/traces/*.json` first.\n")

    # Pair each with its heuristic counterpart, if any.
    pairs = []
    for sp in structural_files:
        base = sp.name.replace('_structural_graded.json', '')
        hp = sp.with_name(base + '_graded.json')
        if hp.exists():
            with open(sp) as f:
                s = json.load(f)
            with open(hp) as f:
                h = json.load(f)
            pairs.append((base, h, s))

    if not pairs:
        return "# No paired heuristic + structural graded traces found.\n"

    # Per-domain agreement count
    agree = defaultdict(int)
    disagree_examples = defaultdict(list)
    for base, h, s in pairs:
        for d in RUBRIC_DOMAINS:
            hg = h['grades'].get(d, 'UNGRADED')
            sg = s['grades'].get(d, 'UNGRADED')
            if hg == sg:
                agree[d] += 1
            else:
                disagree_examples[d].append((base, hg, sg,
                                             s.get('justifications', {}).get(d, '')))

    n = len(pairs)
    lines = [
        f"# Structural vs heuristic grader comparison",
        "",
        f"**N={n} paired traces** (heuristic-v1 vs structural-v1)",
        "",
        "## Per-domain agreement",
        "",
        "| Domain | Agreement | Heuristic example | Structural example |",
        "|--------|-----------|-------------------|--------------------|",
    ]
    for d in RUBRIC_DOMAINS:
        pct = 100.0 * agree[d] / max(n, 1)
        if disagree_examples[d]:
            base, hg, sg, _just = disagree_examples[d][0]
            lines.append(f"| {d} | {agree[d]}/{n} = {pct:.0f}% | "
                         f"{base}: {hg} | {base}: {sg} |")
        else:
            lines.append(f"| {d} | {agree[d]}/{n} = {pct:.0f}% | "
                         f"(all match) | (all match) |")

    # Per-trace side-by-side
    lines += ["", "## Per-trace grades (heuristic | structural)", ""]
    header = "| trace | " + " | ".join(
        f"{d} (H/S)" for d in RUBRIC_DOMAINS
    ) + " |"
    sep = "|" + "|".join(["---"] * (len(RUBRIC_DOMAINS) + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for base, h, s in pairs:
        cells = [base]
        for d in RUBRIC_DOMAINS:
            hg = h['grades'].get(d, '?')
            sg = s['grades'].get(d, '?')
            marker = '' if hg == sg else ' *'
            cells.append(f"{hg}/{sg}{marker}")
        lines.append("| " + " | ".join(cells) + " |")

    # Show a representative disagreement
    lines += ["", "## First disagreement per domain", ""]
    for d in RUBRIC_DOMAINS:
        if disagree_examples[d]:
            base, hg, sg, just = disagree_examples[d][0]
            lines.append(f"### {d}: {base}")
            lines.append(f"- heuristic = **{hg}**, structural = **{sg}**")
            lines.append(f"- structural rationale: {just}")
            lines.append("")

    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('paths', nargs='*', help='Trace JSON files to grade')
    p.add_argument('--report', action='store_true',
                   help='Compare structural vs heuristic grades (reads existing graded files)')
    p.add_argument('--force', action='store_true',
                   help='Re-grade even if _structural_graded.json exists')

    args = p.parse_args()

    if args.report:
        report = build_report()
        report_path = TRACE_DIR.parent / 'structural_vs_heuristic_report.md'
        report_path.write_text(report)
        print(f"Report written to {report_path}")
        print(report)
        return

    if not args.paths:
        p.error("Provide trace JSON paths, or use --report")

    trace_paths = []
    for tp in args.paths:
        pp = Path(tp)
        if '_graded.json' in pp.name or '_prompt.txt' in pp.name:
            continue
        if not pp.exists():
            print(f"  ! skipping {tp} (not found)")
            continue
        trace_paths.append(pp)

    if not trace_paths:
        print("No trace files to grade.")
        return

    print(f"Grading {len(trace_paths)} traces with structural-v1...")
    graded = 0
    for tp in trace_paths:
        out_path = tp.with_name(tp.stem + '_structural_graded.json')
        if out_path.exists() and not args.force:
            print(f"  - {tp.name} already graded, skipping (use --force to re-grade)")
            continue
        if grade_one_structural(tp):
            graded += 1
    print(f"\nGraded {graded}/{len(trace_paths)} traces with structural-v1.")
    print(f"Next: python3 scripts/structural_grader.py --report")


if __name__ == '__main__':
    main()
