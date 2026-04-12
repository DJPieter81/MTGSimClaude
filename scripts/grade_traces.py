#!/usr/bin/env python3
"""
grade_traces.py — LLM grading loop for MTGSimClaude AI-judged sim traces.

Posts each trace's prompt bundle to the Anthropic API (Claude), parses
6-domain grades, and writes graded JSON + a markdown audit report.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...

    # Grade specific trace files
    python3 scripts/grade_traces.py results/traces/storm_vs_dnt_s42.json

    # Grade all traces in the directory
    python3 scripts/grade_traces.py results/traces/*.json

    # Generate report from already-graded files
    python3 scripts/grade_traces.py --report

    # Report + CI threshold check (exits 1 if any domain avg < threshold)
    python3 scripts/grade_traces.py --report --threshold B-

Requires ANTHROPIC_API_KEY env var. Never committed to the repo.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# Allow importing llm_judge from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from llm_judge import build_prompt, RUBRIC_DOMAINS, GRADE_SCALE

# Ordered high-to-low for numeric comparison
GRADE_TO_NUM = {g: (len(GRADE_SCALE) - i) for i, g in enumerate(GRADE_SCALE)}
# B- isn't on the canonical scale but used as a threshold alias → treat as between C+ and B
GRADE_TO_NUM['B-'] = GRADE_TO_NUM['C+'] + 0.5

TRACE_DIR = Path(__file__).resolve().parent.parent / 'results' / 'traces'
REPORT_PATH = Path(__file__).resolve().parent.parent / 'results' / 'llm_audit_report.md'


# ---------------------------------------------------------------------------
# Grade parser
# ---------------------------------------------------------------------------

# Matches lines like:  mulligan: B+ — Kept a keepable 7
GRADE_LINE_RE = re.compile(
    r'^(\w+):\s*([A-F][+-]?)\s*[—\-]\s*(.+)$', re.MULTILINE
)


def parse_grades(raw_response: str) -> dict:
    """
    Parse LLM response into {domain: {grade, justification}}.
    Returns 'UNGRADED' for domains not found / malformed.
    """
    grades = {}
    for match in GRADE_LINE_RE.finditer(raw_response):
        domain = match.group(1).lower()
        grade = match.group(2).upper()
        justification = match.group(3).strip()
        if domain in RUBRIC_DOMAINS or domain == 'overall':
            grades[domain] = {'grade': grade, 'justification': justification}

    # Fill missing domains
    for d in RUBRIC_DOMAINS:
        if d not in grades:
            grades[d] = {'grade': 'UNGRADED', 'justification': 'Domain not found in LLM response'}

    return grades


# ---------------------------------------------------------------------------
# Anthropic API call
# ---------------------------------------------------------------------------

def grade_trace(trace: dict, client: anthropic.Anthropic, model: str = 'claude-sonnet-4-5-20250514') -> dict:
    """Call the Anthropic API to grade a single trace. Returns graded dict."""
    prompt = build_prompt(trace)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw_text = response.content[0].text
    grades = parse_grades(raw_text)

    return {
        'matchup': trace['matchup'],
        'seed': trace['seed'],
        'winner': trace['winner'],
        'kill_turn': trace.get('kill_turn'),
        'game_length': trace['game_length'],
        'deck1': trace['deck1'],
        'deck2': trace['deck2'],
        'grades': {d: g['grade'] for d, g in grades.items()},
        'justifications': {d: g['justification'] for d, g in grades.items()},
        'raw_response': raw_text,
        'model': model,
        'graded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def grade_avg(grade_list: list) -> str:
    """Compute average grade from a list of grade strings. Ignores UNGRADED."""
    nums = [GRADE_TO_NUM[g] for g in grade_list if g in GRADE_TO_NUM]
    if not nums:
        return 'UNGRADED'
    avg = sum(nums) / len(nums)
    # Map back to nearest grade
    best = min(GRADE_SCALE, key=lambda g: abs(GRADE_TO_NUM[g] - avg))
    return best


def load_graded_files() -> list:
    """Load all *_graded.json files from the trace directory."""
    files = sorted(TRACE_DIR.glob('*_graded.json'))
    results = []
    for f in files:
        with open(f) as fh:
            results.append(json.load(fh))
    return results


def generate_report(graded: list) -> str:
    """Build the markdown audit report from a list of graded dicts."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    n = len(graded)

    # Domain averages
    domain_grades = {d: [] for d in RUBRIC_DOMAINS}
    for g in graded:
        for d in RUBRIC_DOMAINS:
            grade = g['grades'].get(d, 'UNGRADED')
            if grade != 'UNGRADED':
                domain_grades[d].append((grade, f"{g['matchup']}_s{g['seed']}"))

    lines = [
        f'# MTGSimClaude LLM Audit — {now}',
        '',
        f'## Domain averages across N={n} traces',
        '',
        '| Domain | Avg Grade | Worst Trace | Best Trace |',
        '|--------|-----------|-------------|------------|',
    ]

    domain_avgs = {}
    for d in RUBRIC_DOMAINS:
        entries = domain_grades[d]
        if not entries:
            lines.append(f'| {d} | UNGRADED | — | — |')
            domain_avgs[d] = 'UNGRADED'
            continue
        avg = grade_avg([e[0] for e in entries])
        domain_avgs[d] = avg
        worst = min(entries, key=lambda e: GRADE_TO_NUM.get(e[0], 0))
        best = max(entries, key=lambda e: GRADE_TO_NUM.get(e[0], 0))
        lines.append(f'| {d} | {avg} | {worst[1]} ({worst[0]}) | {best[1]} ({best[0]}) |')

    # Per-trace summary
    lines.extend(['', '## Per-trace summary', ''])
    for g in graded:
        label = f"{g['matchup']}_s{g['seed']}"
        header = f"### {label} — {g['winner']} won on turn {g.get('game_length', '?')}"
        lines.append(header)
        for d in RUBRIC_DOMAINS:
            grade = g['grades'].get(d, 'UNGRADED')
            just = g.get('justifications', {}).get(d, '')
            lines.append(f'- {d}: {grade} — {just}')
        if 'overall' in g['grades']:
            lines.append(f'- **overall: {g["grades"]["overall"]}** — {g.get("justifications", {}).get("overall", "")}')
        lines.append('')

    # Flagged weaknesses (C or below appearing in 2+ traces for same domain)
    lines.extend(['## Flagged weaknesses (repeat C/D/F grades)', ''])
    weak_threshold = GRADE_TO_NUM['C']  # C and below
    for d in RUBRIC_DOMAINS:
        weak = [(e[0], e[1]) for e in domain_grades[d] if GRADE_TO_NUM.get(e[0], 0) <= weak_threshold]
        if len(weak) >= 2:
            traces_str = ', '.join(f'{t} ({g})' for g, t in weak)
            lines.append(f'- **{d}** ({len(weak)}/{len(domain_grades[d])} traces C or below): {traces_str}')
    if not any(
        len([(e[0], e[1]) for e in domain_grades[d] if GRADE_TO_NUM.get(e[0], 0) <= weak_threshold]) >= 2
        for d in RUBRIC_DOMAINS
    ):
        lines.append('(No domains flagged — all averages above C)')

    lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Threshold check
# ---------------------------------------------------------------------------

def check_threshold(graded: list, threshold: str) -> tuple:
    """
    Returns (passed: bool, failures: list[str]).
    Fails if any domain average is below the threshold.
    """
    if threshold not in GRADE_TO_NUM:
        raise ValueError(f"Unknown threshold grade: {threshold}")
    threshold_num = GRADE_TO_NUM[threshold]

    domain_grades = {d: [] for d in RUBRIC_DOMAINS}
    for g in graded:
        for d in RUBRIC_DOMAINS:
            grade = g['grades'].get(d, 'UNGRADED')
            if grade != 'UNGRADED':
                domain_grades[d].append(grade)

    failures = []
    for d in RUBRIC_DOMAINS:
        if not domain_grades[d]:
            continue
        avg = grade_avg(domain_grades[d])
        if GRADE_TO_NUM.get(avg, 0) < threshold_num:
            failures.append(f'{d}: avg={avg} (below {threshold})')

    return (len(failures) == 0, failures)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('traces', nargs='*', help='Trace JSON files to grade')
    parser.add_argument('--report', action='store_true', help='Generate report from existing graded files')
    parser.add_argument('--threshold', default=None, help='Min acceptable grade (e.g. B-). Exit 1 if below.')
    parser.add_argument('--model', default='claude-sonnet-4-5-20250514', help='Anthropic model to use')
    parser.add_argument('--dry-run', action='store_true', help='Build prompts but skip API calls')
    args = parser.parse_args()

    if not args.report and not args.traces:
        parser.error('Provide trace files to grade, or use --report')

    # --- Grade traces ---
    if args.traces:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key and not args.dry_run:
            print('ERROR: ANTHROPIC_API_KEY not set', file=sys.stderr)
            sys.exit(1)

        client = anthropic.Anthropic(api_key=api_key) if not args.dry_run else None

        for path_str in args.traces:
            path = Path(path_str)
            if not path.exists():
                print(f'SKIP: {path} not found', file=sys.stderr)
                continue
            if '_graded' in path.stem or '_prompt' in path.stem:
                continue  # skip already-graded or prompt files

            with open(path) as f:
                trace = json.load(f)

            print(f'Grading {path.name} ...', end=' ', flush=True)

            if args.dry_run:
                prompt = build_prompt(trace)
                prompt_path = path.with_name(path.stem + '_prompt.txt')
                with open(prompt_path, 'w') as f:
                    f.write(prompt)
                print(f'dry-run → {prompt_path.name} ({len(prompt)} chars)')
                continue

            result = grade_trace(trace, client, model=args.model)
            out_path = path.with_name(path.stem + '_graded.json')
            with open(out_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f'→ {out_path.name}  grades: {result["grades"]}')

    # --- Report ---
    if args.report or (args.traces and not args.dry_run):
        graded = load_graded_files()
        if not graded:
            print('No graded files found in results/traces/', file=sys.stderr)
            sys.exit(1)

        report = generate_report(graded)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, 'w') as f:
            f.write(report)
        print(f'\nReport: {REPORT_PATH}')

        # --- Threshold check ---
        if args.threshold:
            passed, failures = check_threshold(graded, args.threshold)
            if not passed:
                print(f'\nTHRESHOLD FAIL ({args.threshold}):')
                for fail in failures:
                    print(f'  ✗ {fail}')
                sys.exit(1)
            else:
                print(f'\nThreshold check passed (all domains >= {args.threshold})')


if __name__ == '__main__':
    main()
