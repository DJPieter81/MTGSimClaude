#!/usr/bin/env python3
"""
Build meta_fresh.json + deck_agg.json from a results/matrix_*.json.

gen_guides.py expects these two files at /home/claude/... in the original
environment. This script derives them from whatever matrix JSON the
current repo has, so gen_guides can run locally.

Usage:
    python3 build_meta_inputs.py                      # use latest matrix
    python3 build_meta_inputs.py results/matrix_<ts>.json
    python3 build_meta_inputs.py --out-dir /tmp       # write elsewhere

Schema produced:
    meta_fresh.json
        d: [deck_keys]            — ordered list
        a: {d: flat_wr_percent}   — avg WR across all matchups as P1
        w: {d: weighted_wr_pct}   — meta-weighted WR (from matrix.meta_ev)
        m: {"d1|d2": [wr_pct]}    — matchup WR as percentage inside a 1-list

    deck_agg.json
        {d: {type, plan, speed, resilience, creature_based, soft_to_wasteland}}
"""
import json
import os
import sys
import argparse
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deck_registry import get_meta


def pct(wr):
    """Coerce 0-1 or 0-100 to percent. Handles both float and list [wr, ...] formats."""
    if isinstance(wr, (list, tuple)):
        wr = wr[0]
    return wr * 100 if wr <= 1.0 else wr


def build_meta(matrix_data):
    decks = matrix_data['decks']
    mu = matrix_data['matchups']
    evs = matrix_data.get('meta_ev', {})

    # flat WR: average over all opponents (excluding self)
    a = {}
    for d in decks:
        ws = [pct(mu[f"{d}_vs_{o}"]) for o in decks if o != d and f"{d}_vs_{o}" in mu]
        a[d] = round(sum(ws) / len(ws), 1) if ws else 50.0

    # weighted WR: from matrix's own meta_ev (fraction → percent)
    w = {d: round(pct(evs.get(d, a.get(d, 50) / 100)), 1) for d in decks}

    # matchups: "d1|d2": [wr_pct]
    m = {}
    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            k = f"{d1}_vs_{d2}"
            if k in mu:
                m[f"{d1}|{d2}"] = [round(pct(mu[k]), 1)]

    return {'d': decks, 'a': a, 'w': w, 'm': m}


# Mapping from deck category set to single 'type' label used by gen_guides.py.
# Order matters — first match wins.
_TYPE_ORDER = [
    ('fast_combo',    'combo'),
    ('gy_combo',      'combo'),
    ('combo',         'combo'),
    ('prison',        'prison'),
    ('control',       'control'),
    ('aggro',         'aggro'),
    ('tempo_mirror',  'tempo'),
    ('tempo',         'tempo'),
    ('midrange',      'midrange'),
]


def classify_deck(meta):
    """Reduce a set of DECK_META categories to a single archetype label."""
    cats = set(meta.get('categories', ()))
    for cat, label in _TYPE_ORDER:
        if cat in cats:
            return label
    return 'other'


# Minimal per-deck plan summaries. Real deck_agg.json has richer plan text
# generated from sim data; this is a best-effort starting point keyed off
# DECK_META. Override entries as we learn more about each deck.
_PLAN_TEMPLATES = {
    'combo':    "Protect the combo, dig with cantrips, go off when safe.",
    'aggro':    "Deploy threats, trade efficiently, close out with reach.",
    'control':  "Stabilise with counters and removal, win with card advantage.",
    'tempo':    "Curve threats into disruption; win on tempo margins.",
    'prison':   "Land lock pieces early, deny opponent's actions, win slowly.",
    'midrange': "Interact, resolve value creatures, grind out advantage.",
    'other':    "Play to the deck's strengths.",
}


def build_agg(decks):
    out = {}
    for d in decks:
        meta = get_meta(d)
        if meta is None:
            meta = {}
        dtype = classify_deck(meta)
        interaction = meta.get('interaction', {}) or {}
        out[d] = {
            'type': dtype,
            'plan': _PLAN_TEMPLATES.get(dtype, _PLAN_TEMPLATES['other']),
            'speed': interaction.get('speed', 2),
            'resilience': interaction.get('resilience', 2),
            'creature_based': interaction.get('creature_based', False),
            'soft_to_wasteland': interaction.get('soft_to_wasteland', False),
            'uses_graveyard': interaction.get('uses_graveyard', False),
            'uses_veil': interaction.get('uses_veil', False),
        }
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('matrix_path', nargs='?',
                   help='Path to matrix JSON (default: results/matrix_*.json latest)')
    p.add_argument('--out-dir', default='.',
                   help='Where to write meta_fresh.json + deck_agg.json')
    args = p.parse_args()

    if args.matrix_path:
        mpath = args.matrix_path
    else:
        files = sorted(glob.glob('results/matrix_*.json'))
        if not files:
            print('No results/matrix_*.json found.', file=sys.stderr)
            sys.exit(1)
        # Prefer latest by modification time (alphabetical picks bo3 over G1)
        mpath = max(files, key=os.path.getmtime)

    print(f"Using matrix: {mpath}")
    with open(mpath) as f:
        matrix_data = json.load(f)

    meta = build_meta(matrix_data)
    agg = build_agg(matrix_data['decks'])

    os.makedirs(args.out_dir, exist_ok=True)
    meta_out = os.path.join(args.out_dir, 'meta_fresh.json')
    agg_out = os.path.join(args.out_dir, 'deck_agg.json')
    with open(meta_out, 'w') as f:
        json.dump(meta, f, indent=2)
    with open(agg_out, 'w') as f:
        json.dump(agg, f, indent=2)
    print(f"Wrote: {meta_out} ({len(meta['m'])} matchups)")
    print(f"Wrote: {agg_out} ({len(agg)} deck profiles)")


if __name__ == '__main__':
    main()
