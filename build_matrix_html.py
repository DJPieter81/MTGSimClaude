#!/usr/bin/env python3
"""
Rebuild meta matrix HTML by swapping the 5 data constants into the
reference template.

PLANNING.md P0 #3 + PLANNING_REFERENCE §10 P1 #5: never rebuild the
matrix HTML from scratch — always template-swap. This script does
exactly that.

Data layers:
  D     — matchup WRs (from meta_fresh.json)
  DA    — deck profiles, speed, plan (from deck_agg.json)
  C     — card-level stats per matchup (placeholder {} — not computed
          in this env; needs extract_cards.py pipeline from §data_pipeline)
  I     — interaction events per matchup (placeholder {})
  ARCH  — deck → archetype label (from deck_agg.json.type)

Usage:
    python3 build_matrix_html.py                             # latest inputs
    python3 build_matrix_html.py --meta meta_fresh.json --agg deck_agg.json
    python3 build_matrix_html.py --out results/meta_matrix_<ts>.html

After build, CLAUDE.md requires grep 'function pills' to verify the
template's JS functions survived. build_matrix_html.py also runs the
same check and exits nonzero if any of the 9 required functions are
missing.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime


REQUIRED_JS_FNS = [
    'pills', 'wc', 'tc', 'muc', 'getCT', 'tierOf', 'tierTag', 'getWR', 'closeDet',
]

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, 'templates', 'reference_meta_matrix.html')


def _load(path):
    with open(path) as f:
        return json.load(f)


def _build_DA(agg, meta):
    """Format deck_agg into the DA shape the template expects.
    DA[deck] = {type, speed, plan, ...} already; just rename fields for safety.
    """
    out = {}
    for d, info in agg.items():
        out[d] = {
            'type': info.get('type', 'other'),
            'speed': 'fast' if info.get('speed', 2) >= 3 else 'medium' if info.get('speed', 2) == 2 else 'slow',
            'plan': info.get('plan', ''),
            'creature_based': info.get('creature_based', False),
            'resilience': info.get('resilience', 2),
        }
    return out


def _build_ARCH(agg):
    return {d: info.get('type', 'other') for d, info in agg.items()}


def rebuild(meta_path, agg_path, out_path):
    meta = _load(meta_path)
    agg = _load(agg_path)

    # D = the matchup data shape already matching template
    D = {'d': meta['d'], 'm': meta['m'], 'a': meta['a'], 'w': meta['w']}
    DA = _build_DA(agg, meta)
    # Interaction / card layers require the extract_cards.py pipeline which
    # isn't present in this env. Stubbed as empty maps; the template renders
    # "no data" gracefully when these are missing.
    I = {}
    C = {}
    ARCH = _build_ARCH(agg)

    with open(TEMPLATE_PATH) as f:
        html = f.read()

    # Replace the 5 const declarations. Each const is one line (the template
    # stores them on single lines). Use a line-mode regex.
    replacements = [
        ('D', D),
        ('DA', DA),
        ('I', I),
        ('C', C),
        ('ARCH', ARCH),
    ]
    for name, value in replacements:
        pattern = re.compile(rf'^const {name}=.*$', re.MULTILINE)
        new_line = f'const {name}={json.dumps(value, separators=(",", ":"))};'
        if not pattern.search(html):
            raise RuntimeError(f"template missing 'const {name}=' line")
        html = pattern.sub(new_line.replace('\\', r'\\'), html, count=1)

    # Provenance line near the bottom — update to today's date + stats
    today = datetime.now().strftime('%B %d %Y')
    n_matchups = len(meta['m'])
    n_decks = len(meta['d'])
    prov_pattern = re.compile(r'MTGSimClaude[^<]*', re.IGNORECASE)
    if prov_pattern.search(html):
        html = prov_pattern.sub(
            f'MTGSimClaude · {n_decks} decks · {n_matchups} matchups · {today}',
            html, count=1)

    with open(out_path, 'w') as f:
        f.write(html)

    # CLAUDE.md mandatory post-build verification
    missing = [fn for fn in REQUIRED_JS_FNS if f'function {fn}' not in html]
    if missing:
        print(f"✗ missing JS fns: {missing}", file=sys.stderr)
        return False
    print(f"✓ wrote {out_path} ({len(html)//1024}KB)")
    print(f"  D:    {n_decks} decks, {n_matchups} matchups")
    print(f"  DA:   {len(DA)} deck profiles")
    print(f"  ARCH: {len(ARCH)} archetype labels")
    print(f"  C:    {len(C)} (stub — extract_cards.py pipeline needed)")
    print(f"  I:    {len(I)} (stub — extract_interactions pipeline needed)")
    print(f"  JS:   all 9 required functions present")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--meta', default=os.path.join(HERE, 'meta_fresh.json'))
    p.add_argument('--agg', default=os.path.join(HERE, 'deck_agg.json'))
    p.add_argument('--out', default=None,
                   help='Output HTML path (default: results/meta_matrix_<ts>.html)')
    args = p.parse_args()

    if args.out:
        out_path = args.out
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(HERE, 'results', f'meta_matrix_{ts}.html')

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    ok = rebuild(args.meta, args.agg, out_path)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
