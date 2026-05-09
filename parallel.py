"""
Parallel game execution for meta matrix and sweeps.

Parallelizes at two levels:
- Matrix/field: each matchup pair runs in a separate process
- Sweep: games within a single matchup split across processes

Worker count resolution (highest precedence wins):
  1. Explicit `n_workers=` argument
  2. `MTGSIM_WORKERS` environment variable
  3. `min(cpu_count(), 16)` default cap (raised from 8)

Progress: every parallel function consumes results via
`pool.imap_unordered` and prints `[done/total]` status as workers finish.
For determinism, results are sorted by `(deck1, deck2)` (or equivalent
key) before assembling the output dict so the resulting JSON is
byte-identical to the previous `pool.map` ordering under fixed seed.
"""

import multiprocessing as mp
import os
import random
from functools import partial


def _resolve_workers(n_workers=None):
    """Worker count: explicit arg > MTGSIM_WORKERS env var > min(cpu_count(), 16)."""
    if n_workers is not None:
        return n_workers
    env = os.environ.get('MTGSIM_WORKERS')
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return min(mp.cpu_count(), 16)


def _run_games_worker(args):
    """Worker: run N games for one matchup pair. Returns (deck1, deck2, wins, losses, kill_turns, lengths).

    Task tuple shape:
        (deck1, deck2, n_games, seed)                  — legacy 4-tuple, no neural flags
        (deck1, deck2, n_games, seed, neural_flags)    — 5-tuple where neural_flags is a
                                                         dict of bool kwargs forwarded to
                                                         run_game (use_neural_gates, etc.)
    """
    if len(args) == 5:
        deck1, deck2, n_games, seed, neural_flags = args
    else:
        deck1, deck2, n_games, seed = args
        neural_flags = {}
    # Each worker needs its own random state
    if seed is not None:
        random.seed(seed)

    from sim import run_game
    wins = 0
    kill_turns = []
    lengths = []
    for _ in range(n_games):
        r = run_game(deck1, deck2, **neural_flags)
        if r.winner == 'p1':
            wins += 1
        if r.kill_turn:
            kill_turns.append(r.kill_turn)
        lengths.append(r.game_length)
    return (deck1, deck2, wins, n_games - wins, kill_turns, lengths)


def parallel_sweep(deck1, deck2, n_games=100, n_workers=None, neural_flags=None):
    """Run n_games between two decks using multiprocessing.
    Splits games across workers.

    neural_flags: optional dict of run_game kwargs (use_neural_gates, etc.)
                  to forward to each worker.
    """
    n_workers = _resolve_workers(n_workers)
    neural_flags = neural_flags or {}

    # Split games across workers
    chunk = max(1, n_games // n_workers)
    tasks = []
    remaining = n_games
    for i in range(n_workers):
        n = min(chunk, remaining)
        if n <= 0:
            break
        tasks.append((deck1, deck2, n, random.randint(0, 2**31), neural_flags))
        remaining -= n

    total = len(tasks)
    # Small pool (one chunk per worker), so we report every K=10.
    K = 10
    results = []
    with mp.Pool(n_workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_run_games_worker, tasks), 1):
            results.append(r)
            if i % K == 0 or i == total:
                print(f"  [{i}/{total}] sweep chunks complete", flush=True)

    # Determinism: sort by (deck1, deck2) so aggregate order matches pool.map.
    # For sweep all chunks share the same (deck1, deck2); sort is a no-op but
    # kept for symmetry with the other functions.
    results.sort(key=lambda r: (r[0], r[1]))

    # Aggregate
    total_wins = sum(r[2] for r in results)
    total_losses = sum(r[3] for r in results)
    all_kills = [t for r in results for t in r[4]]
    all_lengths = [t for r in results for t in r[5]]
    total = total_wins + total_losses

    return {
        'deck1': deck1, 'deck2': deck2,
        'p1_wins': total_wins, 'p2_wins': total_losses,
        'p1_wr': total_wins / total if total > 0 else 0,
        'n_games': total,
        'avg_length': sum(all_lengths) / len(all_lengths) if all_lengths else 0,
        'avg_kill': sum(all_kills) / len(all_kills) if all_kills else 0,
    }


def parallel_meta_matrix(decks, n_games=100, n_workers=None):
    """Run NxN meta matrix using multiprocessing.
    Each matchup pair is an independent task."""
    n_workers = _resolve_workers(n_workers)

    # Build task list: all matchup pairs
    tasks = []
    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            tasks.append((d1, d2, n_games, random.randint(0, 2**31)))

    total = len(tasks)
    print(f"  Running {total} matchups across {n_workers} workers ({n_games} games each)...",
          flush=True)

    K = 30  # matrix has hundreds of tasks
    results = []
    with mp.Pool(n_workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_run_games_worker, tasks), 1):
            results.append(r)
            if i % K == 0 or i == total:
                print(f"  [{i}/{total}] matchups complete", flush=True)

    # Determinism: imap_unordered returns results in completion order, but the
    # output dict must be deterministic across runs (matters for symmetrise +
    # JSON byte-equality). Sort by (deck1, deck2) before assembling.
    results.sort(key=lambda r: (r[0], r[1]))

    # Build matrix
    matrix = {}
    for d1, d2, wins, losses, kill_turns, lengths in results:
        matrix[(d1, d2)] = wins / (wins + losses) if (wins + losses) > 0 else 0

    return matrix


def _run_bo3_worker(args):
    """Worker: run N Bo3 matches for one protagonist/antagonist pair.
    Returns (proto, ant, match_wins, total_matches, game_wins, total_games)."""
    proto, ant, n_matches, seed = args
    if seed is not None:
        random.seed(seed)

    from sim import run_any_match
    match_wins = 0
    game_wins = 0
    total_games = 0
    for _ in range(n_matches):
        pw, aw, gp, grs = run_any_match(proto, ant)
        if pw > aw:
            match_wins += 1
        total_games += len(grs)
        game_wins += sum(1 for r in grs if r.winner == 'p1')
    return (proto, ant, match_wins, n_matches, game_wins, total_games)


def parallel_meta_matrix_bo3(decks, n_matches=100, n_workers=None):
    """Run NxN Bo3 meta matrix using multiprocessing.
    Each matchup pair is an independent task; returns dict of
        {(d1, d2): {'match_wr': float, 'game_wr': float}}.
    """
    n_workers = _resolve_workers(n_workers)

    tasks = []
    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            tasks.append((d1, d2, n_matches, random.randint(0, 2**31)))

    total = len(tasks)
    print(f"  Running {total} Bo3 matchups across {n_workers} workers "
          f"({n_matches} matches each)...", flush=True)

    K = 30
    results = []
    with mp.Pool(n_workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_run_bo3_worker, tasks), 1):
            results.append(r)
            if i % K == 0 or i == total:
                print(f"  [{i}/{total}] Bo3 matchups complete", flush=True)

    # Determinism: sort by (proto, ant) before building dict.
    results.sort(key=lambda r: (r[0], r[1]))

    matrix = {}
    for proto, ant, mw, m_total, gw, g_total in results:
        matrix[(proto, ant)] = {
            'match_wr': mw / m_total if m_total else 0,
            'game_wr':  gw / g_total if g_total else 0,
        }
    return matrix


def parallel_field(deck, opponents, n_games=100, n_workers=None):
    """Run one deck vs all opponents using multiprocessing."""
    n_workers = _resolve_workers(n_workers)

    tasks = [(deck, opp, n_games, random.randint(0, 2**31))
             for opp in opponents if opp != deck]

    total = len(tasks)
    K = 10  # field is at most ~36 tasks
    results = []
    with mp.Pool(n_workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_run_games_worker, tasks), 1):
            results.append(r)
            if i % K == 0 or i == total:
                print(f"  [{i}/{total}] field opponents complete", flush=True)

    # Determinism: sort by (deck, opp) so the returned list order is stable.
    results.sort(key=lambda r: (r[0], r[1]))
    return results


# ---------------------------------------------------------------------------
# gen_guides.py data-collection worker
# ---------------------------------------------------------------------------
# `gen_guides.py` builds per-deck stats (kill-turn distribution, hand-archetype
# WR, win/loss exemplars) by playing N=2000 games per deck against random
# opponents drawn from the meta deck list. Each deck is independent so the
# whole 36-deck loop is embarrassingly parallel. The worker below does
# exactly what `gen_guides.py` did inline; the parent stitches per-deck
# dicts back into `all_data`.

# Land-name fragments used to count lands in an opening hand. Mirrors the
# inline list `gen_guides.py` used before this worker existed; defined as a
# module-level constant so the worker is self-contained and picklable.
_GEN_GUIDES_LAND_FRAGMENTS = (
    'mountain', 'island', 'forest', 'swamp', 'plains', 'sea', 'tarn',
    'strand', 'delta', 'mesa', 'foothills', 'mire', 'heath', 'catacombs',
    'tomb', 'city', 'cavern', 'temple', 'port', 'waste', 'vantage',
    'islet', 'ring', 'saga', 'depths', 'stage', 'bayou', 'volcanic',
    'tropical', 'underground', 'tundra', 'savannah', 'scrubland',
    'badlands', 'plateau', 'taiga', 'field', 'post', 'tower', 'mine',
    'karakas', 'boseiju', 'otawara', 'seat', 'vault', 'foundry', 'den',
    'arbor', 'nexus', 'mishra', 'urza',
)


def _gen_guides_worker(args):
    """Collect gen_guides per-deck stats for one deck.

    Mirrors the body of gen_guides.py's old 36-deck loop. Returns
    (deck_key, all_data_entry) where all_data_entry has the same keys
    the inline loop produced: kt_dist, archetypes, baseline, win_ex,
    loss_ex, avg_kill.

    `opp_pool` is the list of opponent keys to sample from (gen_guides
    uses meta_fresh.json's deck list, which can differ from cards.DECKS).
    """
    from collections import Counter, defaultdict
    deck_key, n_games, seed, opp_pool = args
    if seed is not None:
        random.seed(seed)

    from sim import run_game

    games = []
    opps = [x for x in opp_pool if x != deck_key]
    for _ in range(n_games):
        opp = random.choice(opps)
        try:
            r = run_game(deck_key, opp)
            hand_cards = list(r.p1_opening_hand) if r.p1_opening_hand else []
            games.append({
                'won': r.winner == 'p1',
                'kill_turn': r.kill_turn or r.game_length,
                'hand': hand_cards,
                'opp': opp,
                'logs': r.log_lines[:12] if r.log_lines else [],
                'length': r.game_length,
                'mulls': r.p1_mulls or 0,
            })
        except Exception:
            # Same per-game guard as the original inline loop: a single bad
            # game shouldn't poison the whole deck (let alone the pool).
            pass

    wins = [g for g in games if g['won']]
    kt_counts = Counter(min(g['kill_turn'], 10) for g in wins)
    total_wins = max(len(wins), 1)
    kt_dist = {t: round(kt_counts.get(t, 0) / total_wins * 100, 1)
               for t in range(1, 11)}

    hand_groups = defaultdict(lambda: {'wins': 0, 'total': 0})
    for g in games:
        if not g['hand']:
            continue
        lands = sum(1 for c in g['hand']
                    if any(x in c.lower() for x in _GEN_GUIDES_LAND_FRAGMENTS))
        lands = min(lands, 7)
        key = str(lands) + 'L-' + str(len(g['hand']) - lands) + 'S'
        hand_groups[key]['total'] += 1
        if g['won']:
            hand_groups[key]['wins'] += 1

    archetypes = [(k, round(d['wins'] / d['total'] * 100, 1), d['total'])
                  for k, d in hand_groups.items() if d['total'] >= 10]
    archetypes.sort(key=lambda x: -x[1])
    baseline = round(len(wins) / max(len(games), 1) * 100, 1)

    entry = {
        'kt_dist': kt_dist,
        'archetypes': archetypes[:6],
        'baseline': baseline,
        'win_ex': sorted(
            [g for g in wins if g['hand'] and g['kill_turn'] <= 8],
            key=lambda g: g['kill_turn'])[:2],
        'loss_ex': [g for g in games if not g['won'] and g['hand']][:1],
        'avg_kill': (round(sum(g['kill_turn'] for g in wins) / total_wins, 1)
                     if wins else 0),
        'n_games': len(games),
        'n_wins': len(wins),
    }
    return (deck_key, entry)


def parallel_gen_guides(decks_list, opp_pool=None, n_games=2000,
                        n_workers=None, seed=None):
    """Parallelise gen_guides.py's per-deck data collection.

    Each deck in `decks_list` runs `n_games` games against random
    opponents drawn from `opp_pool` (defaults to `decks_list` itself)
    in its own worker process. Returns `{deck_key: all_data_entry}`
    matching the structure the previous serial loop produced.
    """
    n_workers = _resolve_workers(n_workers)
    if seed is not None:
        random.seed(seed)

    decks_list = list(decks_list)
    opp_pool = list(opp_pool) if opp_pool is not None else decks_list
    tasks = [(dk, n_games, random.randint(0, 2**31), opp_pool)
             for dk in sorted(decks_list)]
    total = len(tasks)

    print(f"  Running gen_guides data collection: {total} decks "
          f"x {n_games} games across {n_workers} workers...", flush=True)

    out = {}
    done = 0
    with mp.Pool(n_workers) as pool:
        for deck_key, entry in pool.imap_unordered(_gen_guides_worker, tasks):
            out[deck_key] = entry
            done += 1
            print(f"  [{done}/{total}] {deck_key}: {entry['n_games']} games, "
                  f"{entry['n_wins']} wins, avg T{entry['avg_kill']}",
                  flush=True)

    return out
