"""
Meta results persistence — save and load simulation results as JSON.

Usage:
    # Save a matrix run
    from meta_results import save_matrix, load_matrix
    matrix = run_meta_matrix(top_tier=10, n_games=100)
    save_matrix(matrix, tag='top10')

    # Load in another session
    data = load_matrix()  # loads latest
    data = load_matrix('top10')  # loads specific tag

    # Save a field run
    from meta_results import save_field, load_field
    save_field('ur_delver', rows, tag='delver_field')

Results saved to results/ directory as timestamped JSON files.
"""

import json
import os
import glob
from datetime import datetime

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')


def _ensure_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def save_matrix(matrix, decks=None, n_games=None, tag='matrix'):
    """Save a meta matrix to JSON.
    matrix: dict of {(d1, d2): win_rate}
    """
    _ensure_dir()
    if decks is None:
        decks = sorted(set(d for pair in matrix for d in pair))

    # Compute meta-weighted EV (T1+T2 only: meta_share >= 0.04)
    from deck_registry import get_meta_share
    t1t2 = {d for d in decks if get_meta_share(d) >= 0.04}
    evs = {}
    for d in decks:
        opps = [(d2, get_meta_share(d2)) for d2 in t1t2 if d2 != d and (d, d2) in matrix]
        if not opps:
            evs[d] = 0
            continue
        total_share = sum(s for _, s in opps)
        evs[d] = sum(matrix[(d, d2)] * s for d2, s in opps) / total_share

    data = {
        'type': 'matrix',
        'tag': tag,
        'timestamp': datetime.now().isoformat(),
        'n_games': n_games,
        'decks': decks,
        'matchups': {f"{d1}_vs_{d2}": wr for (d1, d2), wr in matrix.items()},
        'meta_ev': evs,
        'rankings': [d for d, _ in sorted(evs.items(), key=lambda x: -x[1])],
    }

    filename = f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {filepath}")
    return filepath


def load_matrix(tag='matrix'):
    """Load the latest matrix result with the given tag.
    Returns dict with keys: decks, matchups, meta_ev, rankings, etc.
    """
    pattern = os.path.join(RESULTS_DIR, f"{tag}_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        # Try loading any matrix file
        pattern = os.path.join(RESULTS_DIR, "*matrix*.json")
        files = sorted(glob.glob(pattern))
    if not files:
        print(f"No matrix results found (looked for {tag}_*.json)")
        return None

    filepath = files[-1]  # latest
    with open(filepath) as f:
        data = json.load(f)
    print(f"Loaded: {filepath} ({data.get('timestamp', '?')})")
    return data


def save_sweep(deck1, deck2, stats, tag='sweep'):
    """Save a sweep result to JSON."""
    _ensure_dir()
    data = {
        'type': 'sweep',
        'tag': tag,
        'timestamp': datetime.now().isoformat(),
        'deck1': deck1, 'deck2': deck2,
        **stats,
    }
    filename = f"{tag}_{deck1}_vs_{deck2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {filepath}")
    return filepath


def save_field(deck, rows, n_games=None, tag='field'):
    """Save a field result (one deck vs all opponents) to JSON."""
    _ensure_dir()
    data = {
        'type': 'field',
        'tag': tag,
        'timestamp': datetime.now().isoformat(),
        'deck': deck,
        'n_games_per_matchup': n_games,
        'matchups': [
            {'opponent': opp, 'wins': w, 'losses': l, 'wr': wr, 'avg_length': avg}
            for opp, w, l, wr, avg in rows
        ],
        'overall_wr': sum(r[3] for r in rows) / len(rows) if rows else 0,
    }
    filename = f"{tag}_{deck}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {filepath}")
    return filepath


def list_results():
    """List all saved result files."""
    pattern = os.path.join(RESULTS_DIR, "*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No saved results found.")
        return []
    print(f"\nSaved results ({len(files)}):")
    for f in files:
        name = os.path.basename(f)
        size = os.path.getsize(f)
        print(f"  {name} ({size/1024:.1f}KB)")
    return files


def print_matrix(data):
    """Pretty-print a loaded matrix result."""
    if data is None:
        return
    decks = data['decks']
    matchups = data['matchups']

    def s(d):
        return d[:8] if len(d) > 8 else d

    hdr = f"{'':13s}" + ''.join(f'{s(d):>9s}' for d in decks)
    print(hdr)
    print('-' * len(hdr))

    for d1 in decks:
        row = f'{s(d1):13s}'
        for d2 in decks:
            if d1 == d2:
                row += f"{'---':>9s}"
            else:
                key = f"{d1}_vs_{d2}"
                wr = matchups.get(key, 0)
                row += f'{wr:>8.0%} '
        print(row)

    print('\nMeta-Weighted WR (T1+T2):')
    rankings = data.get('rankings', [])
    evs = data.get('meta_ev', {})
    from deck_registry import get_meta_share
    for i, d in enumerate(rankings):
        ev = evs.get(d, 0)
        tier = 'T1' if get_meta_share(d) >= 0.05 else 'T2' if get_meta_share(d) >= 0.04 else '  '
        bar = '#' * int(ev * 40)
        print(f'  {i+1:2d}. {d:15s} {ev:5.1%}  {tier}  {bar}')
