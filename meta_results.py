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


def save_matrix_bo3(matrix, decks=None, n_matches=None, tag='matrix_bo3'):
    """Save a Bo3 meta matrix to JSON.

    matrix: dict of {(d1, d2): {'match_wr': float, 'game_wr': float}}

    Stores both match_wr (primary) and game_wr (Bo1 baseline) so the HTML
    can render either. Meta-weighted EV is computed from match_wr, which
    is the tournament-relevant figure.
    """
    _ensure_dir()
    if decks is None:
        decks = sorted(set(d for pair in matrix for d in pair))

    from deck_registry import get_meta_share
    t1t2 = {d for d in decks if get_meta_share(d) >= 0.04}
    evs_match, evs_game = {}, {}
    for d in decks:
        opps = [(d2, get_meta_share(d2)) for d2 in t1t2
                if d2 != d and (d, d2) in matrix]
        if not opps:
            evs_match[d] = 0; evs_game[d] = 0
            continue
        total_share = sum(s for _, s in opps)
        evs_match[d] = sum(matrix[(d, d2)]['match_wr'] * s for d2, s in opps) / total_share
        evs_game[d]  = sum(matrix[(d, d2)]['game_wr']  * s for d2, s in opps) / total_share

    data = {
        'type': 'matrix_bo3',
        'tag': tag,
        'timestamp': datetime.now().isoformat(),
        'n_matches': n_matches,
        'decks': decks,
        # Matchups store [match_wr, game_wr] pairs — template M[k] indexable
        'matchups': {
            f"{d1}_vs_{d2}": [v['match_wr'], v['game_wr']]
            for (d1, d2), v in matrix.items()
        },
        'meta_ev_match': evs_match,
        'meta_ev_game':  evs_game,
        'rankings_match': [d for d, _ in sorted(evs_match.items(), key=lambda x: -x[1])],
        'rankings_game':  [d for d, _ in sorted(evs_game.items(), key=lambda x: -x[1])],
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
    """Pretty-print a loaded matrix result (Bo1 or Bo3)."""
    if data is None:
        return
    decks = data['decks']
    matchups = data['matchups']
    is_bo3 = data.get('type') == 'matrix_bo3'

    def s(d):
        return d[:8] if len(d) > 8 else d

    def _wr(key):
        v = matchups.get(key, 0)
        if isinstance(v, list):
            return v[0]  # match_wr for Bo3
        return v

    hdr = f"{'':13s}" + ''.join(f'{s(d):>9s}' for d in decks)
    print(hdr)
    print('-' * len(hdr))

    for d1 in decks:
        row = f'{s(d1):13s}'
        for d2 in decks:
            if d1 == d2:
                row += f"{'---':>9s}"
            else:
                wr = _wr(f"{d1}_vs_{d2}")
                row += f'{wr:>8.0%} '
        print(row)

    from deck_registry import get_meta_share
    if is_bo3:
        print('\nMeta-Weighted Match WR (T1+T2, Bo3):')
        rankings = data.get('rankings_match', [])
        m_evs = data.get('meta_ev_match', {})
        g_evs = data.get('meta_ev_game',  {})
        for i, d in enumerate(rankings):
            m = m_evs.get(d, 0); g = g_evs.get(d, 0)
            tier = 'T1' if get_meta_share(d) >= 0.05 else 'T2' if get_meta_share(d) >= 0.04 else '  '
            bar = '#' * int(m * 40)
            print(f'  {i+1:2d}. {d:15s} match {m:5.1%}  game {g:5.1%}  '
                  f'Δ {g-m:+5.1%}  {tier}  {bar}')
    else:
        print('\nMeta-Weighted WR (T1+T2):')
        rankings = data.get('rankings', [])
        evs = data.get('meta_ev', {})
        for i, d in enumerate(rankings):
            ev = evs.get(d, 0)
            tier = 'T1' if get_meta_share(d) >= 0.05 else 'T2' if get_meta_share(d) >= 0.04 else '  '
            bar = '#' * int(ev * 40)
            print(f'  {i+1:2d}. {d:15s} {ev:5.1%}  {tier}  {bar}')


# ── Symmetry averaging (PLANNING_REFERENCE §9 #3) ────────────────────────────

def symmetrise_matrix(data, asymmetry_threshold=0.10):
    """Average each matchup across both orderings to eliminate p1/p2 asymmetry.

    For every pair (d1, d2) where both 'd1_vs_d2' and 'd2_vs_d1' exist, replace
    each value with ((wr_as_p1) + (1 - wr_as_p2)) / 2. Keeps the `d1+d2 ≈ 1`
    invariant exactly. Flags any pair whose pre-symmetrisation asymmetry
    exceeds `asymmetry_threshold` in a 'symmetry_warnings' list.

    Args:
        data: matrix dict as returned by load_matrix() (must contain 'matchups').
        asymmetry_threshold: flag pairs where |wr_p1 + wr_p2 - 1| > threshold.

    Returns:
        dict with keys:
            'matchups'           — the averaged matchup map
            'symmetry_warnings'  — list of (d1, d2, wr_p1, wr_p2, asymmetry)
            'unpaired'           — list of matchup keys missing their reverse
        Plus all other keys from the input data.
    """
    mu = data['matchups']
    averaged = {}
    warnings = []
    unpaired = []
    seen = set()
    for key, wr in mu.items():
        if '_vs_' not in key:
            averaged[key] = wr
            continue
        d1, d2 = key.split('_vs_', 1)
        reverse_key = f"{d2}_vs_{d1}"
        reverse_wr = mu.get(reverse_key)
        if reverse_wr is None:
            averaged[key] = wr
            unpaired.append(key)
            continue
        pair_id = tuple(sorted((d1, d2)))
        if pair_id not in seen:
            asymmetry = abs(wr + reverse_wr - 1.0)
            if asymmetry > asymmetry_threshold:
                warnings.append((d1, d2, wr, reverse_wr, asymmetry))
            seen.add(pair_id)
        # Symmetric average: this side's "win rate as p1" averaged with
        # "1 - opponent's win rate as p1" (i.e. my win rate as p2)
        averaged[key] = (wr + (1 - reverse_wr)) / 2
    out = dict(data)
    out['matchups'] = averaged
    out['symmetry_warnings'] = warnings
    out['unpaired'] = unpaired
    return out


def save_symmetrised(data, path=None):
    """Write a symmetrised matrix alongside the original.

    If path is None, derives '<original>_sym.json' from the timestamp.
    """
    _ensure_dir()
    if path is None:
        ts = data.get('timestamp', datetime.now().isoformat()).replace(':', '').replace('-', '').split('.')[0]
        path = os.path.join(RESULTS_DIR, f"matrix_{ts}_sym.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved symmetrised matrix: {path}")
    return path
