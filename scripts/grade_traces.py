#!/usr/bin/env python3
"""
grade_traces.py — Grade MTGSimClaude traces via Anthropic API (§9 #7).

Usage:
    # LLM grading (requires valid Anthropic API key)
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 scripts/grade_traces.py results/traces/*.json

    # Heuristic grading (no API key needed — rule-based analysis)
    python3 scripts/grade_traces.py results/traces/*.json --local

    # Report from existing graded files
    python3 scripts/grade_traces.py --report
    python3 scripts/grade_traces.py --report --threshold B-   # exit 1 if avg < threshold
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Allow importing llm_judge from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_judge import RUBRIC_DOMAINS, GRADE_SCALE, bundle

TRACE_DIR = Path(__file__).resolve().parent.parent / 'results' / 'traces'

# Numeric mapping for grade averaging
GRADE_TO_NUM = {g: i for i, g in enumerate(GRADE_SCALE)}
NUM_TO_GRADE = {i: g for g, i in GRADE_TO_NUM.items()}

# Decks known to be combo-centric
COMBO_DECKS = {'storm', 'doomsday', 'oops', 'belcher', 'cephalid', 'reanimator',
               'sneak_a', 'sneak_b', 'show', 'show_fix', 'tes', 'depths', 'elves'}
# Decks known to be interaction-heavy
INTERACTION_DECKS = {'bug', 'dimir', 'dimir_b', 'dimir_c', 'dimir_d', 'dimir_flash',
                     'ur_delver', 'ur_tempo', 'uwx', 'dnt', 'mardu'}
# Aggro decks
AGGRO_DECKS = {'burn', 'goblins', 'eldrazi', 'affinity', 'ur_aggro', 'boros'}


def parse_grades(raw_response: str) -> dict:
    """Parse LLM response into {domain: grade, ..., overall: grade, justifications: {...}}.

    Tolerant regex: matches lines like  'mulligan: B+ — kept a good hand'
    Returns 'UNGRADED' for any domain not found.
    """
    pattern = re.compile(r'^(\w+)\s*:\s*([A-F][+-]?)\s*[—\-–]\s*(.+)$', re.MULTILINE)
    grades = {}
    justifications = {}
    for m in pattern.finditer(raw_response):
        domain = m.group(1).lower().strip()
        grade = m.group(2).strip()
        justification = m.group(3).strip()
        if domain in RUBRIC_DOMAINS or domain == 'overall':
            grades[domain] = grade
            justifications[domain] = justification

    # Fill missing domains
    for d in RUBRIC_DOMAINS:
        if d not in grades:
            grades[d] = 'UNGRADED'
            justifications[d] = '(no response for this domain)'

    if 'overall' not in grades:
        grades['overall'] = 'UNGRADED'
        justifications['overall'] = ''

    return {'grades': grades, 'justifications': justifications}


def _heuristic_grade(trace: dict) -> dict:
    """Rule-based grading from trace data. Returns {grades: {...}, justifications: {...}}."""
    deck1 = trace.get('deck1', '')
    deck2 = trace.get('deck2', '')
    decisions = trace.get('strategic_decisions', [])
    n_dec = len(decisions)
    game_length = trace.get('game_length', 10)
    winner = trace.get('winner', '')
    p1_won = winner == 'p1'
    p1_mulls = trace.get('p1_mulls', 0)
    win_reason = trace.get('win_reason', '')
    log = trace.get('full_log', [])
    log_text = '\n'.join(log[:60])

    grades = {}
    justifications = {}

    # --- mulligan ---
    if p1_mulls == 0:
        grades['mulligan'] = 'B+' if p1_won else 'B'
        justifications['mulligan'] = f"Kept 7; {'won' if p1_won else 'lost'} — opening hand was {'adequate' if p1_won else 'possibly too greedy'}"
    elif p1_mulls == 1:
        grades['mulligan'] = 'B' if p1_won else 'C+'
        justifications['mulligan'] = f"Mulled to 6; {'still won' if p1_won else 'card disadvantage contributed to loss'}"
    else:
        grades['mulligan'] = 'C' if p1_won else 'D'
        justifications['mulligan'] = f"Mulled to {7 - p1_mulls}; aggressive mulligan strategy {'paid off' if p1_won else 'backfired'}"

    # --- mana ---
    mana_keywords = ['tap', 'mana', 'land', 'ritual', 'petal', 'LED', 'lotus']
    mana_decisions = [d for d in decisions if any(k.lower() in (d.get('chosen', '') + d.get('reason', '')).lower() for k in mana_keywords)]
    mana_ratio = len(mana_decisions) / max(n_dec, 1)
    if deck1 in COMBO_DECKS:
        # Combo decks: mana sequencing is critical
        if p1_won and game_length <= 4:
            grades['mana'] = 'A'
            justifications['mana'] = f"Fast kill (T{game_length}) implies efficient mana sequencing"
        elif p1_won:
            grades['mana'] = 'B+'
            justifications['mana'] = f"Won but took {game_length} turns — mana was adequate"
        else:
            grades['mana'] = 'C+' if game_length <= 6 else 'C'
            justifications['mana'] = f"Lost in {game_length} turns — possible mana sequencing issues"
    else:
        if p1_won:
            grades['mana'] = 'B+' if game_length <= 8 else 'B'
            justifications['mana'] = f"Resource deployment supported a T{game_length} win"
        else:
            grades['mana'] = 'B' if game_length >= 8 else 'C+'
            justifications['mana'] = f"{'Adequate' if game_length >= 8 else 'Suboptimal'} mana utilization over {game_length} turns"

    # --- combat ---
    combat_keywords = ['attack', 'block', 'damage', 'combat', 'swing']
    combat_decisions = [d for d in decisions if any(k.lower() in (d.get('chosen', '') + d.get('reason', '')).lower() for k in combat_keywords)]
    if deck1 in COMBO_DECKS:
        grades['combat'] = 'B'
        justifications['combat'] = f"Combo deck — combat decisions {'minimal' if len(combat_decisions) == 0 else 'present but secondary'}"
    elif deck1 in AGGRO_DECKS:
        if p1_won:
            grades['combat'] = 'A' if game_length <= 5 else 'B+'
            justifications['combat'] = f"Aggro plan executed in {game_length} turns — {'excellent' if game_length <= 5 else 'solid'} pressure"
        else:
            grades['combat'] = 'C+' if game_length <= 8 else 'C'
            justifications['combat'] = f"Aggro plan {'stalled' if game_length > 8 else 'fell short'} — opponent stabilized"
    else:
        if p1_won:
            grades['combat'] = 'B+' if combat_decisions else 'B'
            justifications['combat'] = f"{'Active combat decisions contributed to win' if combat_decisions else 'Won through non-combat means'}"
        else:
            grades['combat'] = 'C+' if combat_decisions else 'C'
            _msg = "Combat trades did not generate enough advantage" if combat_decisions else "Limited combat engagement"
            justifications['combat'] = _msg

    # --- combo ---
    combo_keywords = ['combo', 'kill', 'win', 'storm', 'tendrils', 'reanimate', 'sneak', 'show', 'doomsday']
    combo_decisions = [d for d in decisions if d.get('phase') == 'combo' or any(k.lower() in (d.get('chosen', '') + d.get('reason', '')).lower() for k in combo_keywords)]
    if deck1 in COMBO_DECKS:
        if p1_won and game_length <= 4:
            grades['combo'] = 'A+'
            justifications['combo'] = f"Clean combo kill on T{game_length} — optimal assembly"
        elif p1_won:
            grades['combo'] = 'B+' if game_length <= 6 else 'B'
            justifications['combo'] = f"Combo executed on T{game_length} — {'efficient' if game_length <= 6 else 'delayed but successful'}"
        else:
            grades['combo'] = 'D' if game_length <= 5 else 'C'
            _cmsg = "disrupted early" if game_length <= 5 else "could not find pieces"
            justifications['combo'] = f"Failed to assemble combo — {_cmsg}"
    else:
        grades['combo'] = 'B'
        justifications['combo'] = f"Non-combo deck — domain not primary axis"

    # --- interaction ---
    inter_keywords = ['counter', 'remove', 'discard', 'thoughtseize', 'force', 'bolt', 'swords', 'wasteland', 'interact']
    inter_decisions = [d for d in decisions if any(k.lower() in (d.get('chosen', '') + d.get('reason', '')).lower() for k in inter_keywords)]
    if deck1 in INTERACTION_DECKS:
        if p1_won:
            grades['interaction'] = 'A' if len(inter_decisions) >= 3 else 'B+'
            justifications['interaction'] = f"{'Heavy disruption ({0} decisions) enabled win'.format(len(inter_decisions)) if len(inter_decisions) >= 3 else 'Interaction-backed win with measured disruption'}"
        else:
            grades['interaction'] = 'C+' if len(inter_decisions) >= 2 else 'C'
            _imsg = "was not enough to prevent opponent plan" if len(inter_decisions) >= 2 else "was insufficient — key threats went unanswered"
            justifications['interaction'] = f"Disruption {_imsg}"
    elif deck1 in COMBO_DECKS:
        # Combo decks have limited interaction (maybe protection)
        protection_found = any('protect' in d.get('reason', '').lower() or 'force' in d.get('chosen', '').lower() for d in decisions)
        if p1_won:
            grades['interaction'] = 'B+' if protection_found else 'B'
            justifications['interaction'] = f"{'Protected combo with countermagic' if protection_found else 'Combo resolved without needing protection'}"
        else:
            grades['interaction'] = 'C' if not protection_found else 'C+'
            justifications['interaction'] = f"{'No protection deployed against disruption' if not protection_found else 'Protection was insufficient'}"
    else:
        grades['interaction'] = 'B' if p1_won else 'C+'
        justifications['interaction'] = f"{'Adequate interaction for game plan' if p1_won else 'Interaction fell short of needs'}"

    # --- meta ---
    # Matchup awareness: did deck1 play to its expected role?
    is_favored = deck1 in COMBO_DECKS and deck2 in AGGRO_DECKS  # combo usually beats aggro on speed
    is_unfavored = deck1 in COMBO_DECKS and deck2 in INTERACTION_DECKS  # combo struggles vs disruption
    if p1_won and is_unfavored:
        grades['meta'] = 'A'
        justifications['meta'] = f"Won an unfavored matchup ({deck1} vs {deck2}) — strong matchup awareness"
    elif p1_won:
        grades['meta'] = 'B+' if game_length <= 6 else 'B'
        justifications['meta'] = f"{'Efficiently closed' if game_length <= 6 else 'Eventually closed'} {'a favored' if is_favored else 'the'} matchup"
    elif not p1_won and is_favored:
        grades['meta'] = 'C'
        justifications['meta'] = f"Lost a matchup that should be favored ({deck1} vs {deck2}) — possible role confusion"
    else:
        grades['meta'] = 'C+' if n_dec >= 5 else 'C'
        _mmsg = "played actively but could not overcome matchup" if n_dec >= 5 else "limited decision points suggest structural disadvantage"
        justifications['meta'] = f"Lost — {_mmsg}"

    # --- overall ---
    all_nums = [GRADE_TO_NUM.get(g, 3) for g in grades.values()]
    avg = sum(all_nums) / len(all_nums)
    nearest = min(NUM_TO_GRADE.keys(), key=lambda k: abs(k - avg))
    grades['overall'] = NUM_TO_GRADE[nearest]
    justifications['overall'] = f"Average across 6 domains — {'won' if p1_won else 'lost'} in {game_length} turns"

    return {'grades': grades, 'justifications': justifications}


def grade_one_local(trace_path: Path) -> Path | None:
    """Heuristic-grade a single trace. Returns path to _graded.json."""
    with open(trace_path) as f:
        trace_data = json.load(f)

    parsed = _heuristic_grade(trace_data)

    # Build raw_response text that matches the LLM output format
    raw_lines = []
    for d in list(RUBRIC_DOMAINS) + ['overall']:
        raw_lines.append(f"{d}: {parsed['grades'][d]} — {parsed['justifications'][d]}")
    raw = '\n'.join(raw_lines)

    graded = {
        'trace_file': trace_path.name,
        'matchup': trace_data.get('matchup', ''),
        'seed': trace_data.get('seed', ''),
        'winner': trace_data.get('winner', ''),
        'win_reason': trace_data.get('win_reason', ''),
        'kill_turn': trace_data.get('kill_turn', ''),
        'game_length': trace_data.get('game_length', ''),
        'deck1': trace_data.get('deck1', ''),
        'deck2': trace_data.get('deck2', ''),
        'grades': parsed['grades'],
        'justifications': parsed['justifications'],
        'raw_response': raw,
        'model': 'heuristic-v1',
        'graded_at': datetime.utcnow().isoformat() + 'Z',
    }

    out_path = trace_path.with_name(trace_path.stem + '_graded.json')
    with open(out_path, 'w') as f:
        json.dump(graded, f, indent=2)

    grade_str = ' '.join(f"{d}={parsed['grades'][d]}" for d in RUBRIC_DOMAINS)
    print(f"  ✓ {trace_path.name} → {grade_str}")
    return out_path


def grade_one_api(trace_path: Path, client, model: str = 'claude-sonnet-4-5-20250514',
                  dry_run: bool = False) -> Path | None:
    """Grade a single trace via Anthropic API. Returns path to _graded.json or None."""
    prompt_paths = bundle([str(trace_path)])
    if not prompt_paths:
        print(f"  ✗ failed to build prompt for {trace_path.name}")
        return None

    prompt_text = prompt_paths[0].read_text()

    if dry_run:
        print(f"  [dry-run] {trace_path.name} — prompt {len(prompt_text)} chars")
        return None

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt_text}],
        )
        raw = resp.content[0].text
    except Exception as e:
        print(f"  ✗ API error for {trace_path.name}: {e}")
        return None

    parsed = parse_grades(raw)

    with open(trace_path) as f:
        trace_data = json.load(f)

    graded = {
        'trace_file': trace_path.name,
        'matchup': trace_data.get('matchup', ''),
        'seed': trace_data.get('seed', ''),
        'winner': trace_data.get('winner', ''),
        'win_reason': trace_data.get('win_reason', ''),
        'kill_turn': trace_data.get('kill_turn', ''),
        'game_length': trace_data.get('game_length', ''),
        'deck1': trace_data.get('deck1', ''),
        'deck2': trace_data.get('deck2', ''),
        'grades': parsed['grades'],
        'justifications': parsed['justifications'],
        'raw_response': raw,
        'model': model,
        'graded_at': datetime.utcnow().isoformat() + 'Z',
    }

    out_path = trace_path.with_name(trace_path.stem + '_graded.json')
    with open(out_path, 'w') as f:
        json.dump(graded, f, indent=2)

    grade_str = ' '.join(f"{d}={parsed['grades'][d]}" for d in RUBRIC_DOMAINS)
    print(f"  ✓ {trace_path.name} → {grade_str}")
    return out_path


def grade_avg_numeric(grades_list: list[str]) -> tuple[float, str]:
    """Compute average grade from list of grade strings. Ignores UNGRADED."""
    nums = [GRADE_TO_NUM[g] for g in grades_list if g in GRADE_TO_NUM]
    if not nums:
        return 999, 'UNGRADED'
    avg = sum(nums) / len(nums)
    nearest = min(NUM_TO_GRADE.keys(), key=lambda k: abs(k - avg))
    return avg, NUM_TO_GRADE[nearest]


def build_report(threshold: str | None = None) -> str:
    """Read all *_graded.json, produce markdown report."""
    graded_files = sorted(TRACE_DIR.glob('*_graded.json'))
    if not graded_files:
        return "# No graded traces found\n\nRun `python3 scripts/grade_traces.py results/traces/*.json` first.\n"

    all_graded = []
    for f in graded_files:
        with open(f) as fh:
            all_graded.append(json.load(fh))

    n = len(all_graded)
    models_used = sorted(set(g.get('model', 'unknown') for g in all_graded))

    # Domain averages
    domain_grades = {d: [] for d in RUBRIC_DOMAINS}
    for g in all_graded:
        for d in RUBRIC_DOMAINS:
            gr = g['grades'].get(d, 'UNGRADED')
            if gr != 'UNGRADED':
                domain_grades[d].append((gr, g['trace_file']))

    lines = [
        f"# MTGSimClaude LLM Audit — {datetime.utcnow().strftime('%Y-%m-%d')}",
        "",
        f"**N={n} traces graded** | Model(s): {', '.join(models_used)}",
        "",
        "## Domain averages",
        "",
        "| Domain | Avg Grade | Worst Trace | Best Trace |",
        "|--------|-----------|-------------|------------|",
    ]

    domain_avgs = {}
    for d in RUBRIC_DOMAINS:
        grades = [g for g, _ in domain_grades[d]]
        if not grades:
            lines.append(f"| {d} | UNGRADED | — | — |")
            continue
        avg_num, avg_grade = grade_avg_numeric(grades)
        domain_avgs[d] = avg_num
        worst = max(domain_grades[d], key=lambda x: GRADE_TO_NUM.get(x[0], 999))
        best = min(domain_grades[d], key=lambda x: GRADE_TO_NUM.get(x[0], 999))
        lines.append(
            f"| {d} | {avg_grade} | {worst[1].replace('.json','')} ({worst[0]}) | {best[1].replace('.json','')} ({best[0]}) |"
        )

    # Per-trace summary
    lines += ["", "## Per-trace summary", ""]
    for g in all_graded:
        trace_id = g['trace_file'].replace('.json', '')
        header = f"### {trace_id} — {g['winner']} won on turn {g.get('kill_turn', '?')}"
        lines.append(header)
        for d in RUBRIC_DOMAINS:
            gr = g['grades'].get(d, 'UNGRADED')
            just = g.get('justifications', {}).get(d, '')
            lines.append(f"- **{d}**: {gr} — {just}")
        if g['grades'].get('overall', 'UNGRADED') != 'UNGRADED':
            lines.append(f"- **overall**: {g['grades']['overall']} — {g.get('justifications', {}).get('overall', '')}")
        lines.append("")

    # Flagged weaknesses
    lines += ["## Flagged weaknesses (repeat C/D/F grades)", ""]
    weakness_found = False
    deck_domain_grades = defaultdict(list)
    for g in all_graded:
        for d in RUBRIC_DOMAINS:
            gr = g['grades'].get(d, 'UNGRADED')
            if gr in ('C+', 'C', 'D', 'F'):
                deck_domain_grades[(g.get('deck1', '?'), d)].append((gr, g['trace_file']))

    for (deck, domain), entries in sorted(deck_domain_grades.items()):
        if len(entries) >= 2:
            weakness_found = True
            traces = ', '.join(f"{t.replace('.json','')} ({g})" for g, t in entries)
            lines.append(f"- **{deck}.{domain}** ({len(entries)}/{n} traces C or below): {traces}")

    if not weakness_found:
        lines.append("- None detected (all domains average B or above)")

    # Threshold check
    if threshold:
        lines += ["", f"## Threshold check (minimum: {threshold})", ""]
        threshold_num = GRADE_TO_NUM.get(threshold, 3)
        failures = []
        for d, avg in domain_avgs.items():
            if avg > threshold_num:
                _, avg_grade = grade_avg_numeric([g for g, _ in domain_grades[d]])
                failures.append(f"{d} ({avg_grade})")
        if failures:
            lines.append(f"**FAIL** — domains below {threshold}: {', '.join(failures)}")
        else:
            lines.append(f"**PASS** — all domains at or above {threshold}")

    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('paths', nargs='*', help='Trace JSON files to grade')
    p.add_argument('--report', action='store_true', help='Generate audit report from graded files')
    p.add_argument('--threshold', default=None, help='Minimum grade for CI check (e.g. B-); exit 1 if below')
    p.add_argument('--dry-run', action='store_true', help='Build prompts but skip API calls')
    p.add_argument('--local', action='store_true', help='Use heuristic grading (no API key needed)')
    p.add_argument('--force', action='store_true', help='Re-grade even if _graded.json exists')
    p.add_argument('--model', default='claude-sonnet-4-5-20250514', help='Model for API grading')

    args = p.parse_args()

    if args.report:
        report = build_report(args.threshold)
        report_path = TRACE_DIR.parent / 'llm_audit_report.md'
        report_path.write_text(report)
        print(f"Report written to {report_path}")
        print(report)
        if args.threshold and '**FAIL**' in report:
            sys.exit(1)
        return

    if not args.paths:
        p.error("Provide trace JSON paths, or use --report")

    # Filter to only raw trace JSON files
    trace_paths = []
    for tp in args.paths:
        pp = Path(tp)
        if '_graded.json' in pp.name or '_prompt.txt' in pp.name:
            continue
        if not pp.exists():
            print(f"  ⚠ skipping {tp} (not found)")
            continue
        trace_paths.append(pp)

    if not trace_paths:
        print("No trace files to grade.")
        return

    if args.local:
        print(f"Grading {len(trace_paths)} traces with heuristic-v1...")
        graded = 0
        for tp in trace_paths:
            graded_path = tp.with_name(tp.stem + '_graded.json')
            if graded_path.exists() and not args.force:
                print(f"  ⊘ {tp.name} already graded, skipping (use --force to re-grade)")
                continue
            result = grade_one_local(tp)
            if result:
                graded += 1
        print(f"\nGraded {graded}/{len(trace_paths)} traces.")
    else:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key and not args.dry_run:
            print("ERROR: Set ANTHROPIC_API_KEY environment variable (or use --local)")
            sys.exit(1)

        import anthropic
        client = None
        if not args.dry_run:
            import httpx as _httpx
            http_client = _httpx.Client(verify=False)
            client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

        print(f"Grading {len(trace_paths)} traces with {args.model}...")
        graded = 0
        for tp in trace_paths:
            graded_path = tp.with_name(tp.stem + '_graded.json')
            if graded_path.exists() and not args.force:
                print(f"  ⊘ {tp.name} already graded, skipping (use --force to re-grade)")
                continue
            result = grade_one_api(tp, client, model=args.model, dry_run=args.dry_run)
            if result:
                graded += 1
                time.sleep(0.5)
        print(f"\nGraded {graded}/{len(trace_paths)} traces.")

    if not args.dry_run:
        print(f"Next: python3 scripts/grade_traces.py --report")


if __name__ == '__main__':
    main()
