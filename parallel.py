"""
Parallel game execution for meta matrix and sweeps.

Parallelizes at two levels:
- Matrix/field: each matchup pair runs in a separate process
- Sweep: games within a single matchup split across processes
"""

import multiprocessing as mp
import random
from functools import partial


def _run_games_worker(args):
    """Worker: run N games for one matchup pair. Returns (deck1, deck2, wins, losses, kill_turns, lengths)."""
    deck1, deck2, n_games, seed = args
    # Each worker needs its own random state
    if seed is not None:
        random.seed(seed)

    from sim import run_game
    wins = 0
    kill_turns = []
    lengths = []
    for _ in range(n_games):
        r = run_game(deck1, deck2)
        if r.winner == 'p1':
            wins += 1
        if r.kill_turn:
            kill_turns.append(r.kill_turn)
        lengths.append(r.game_length)
    return (deck1, deck2, wins, n_games - wins, kill_turns, lengths)


def parallel_sweep(deck1, deck2, n_games=100, n_workers=None):
    """Run n_games between two decks using multiprocessing.
    Splits games across workers."""
    if n_workers is None:
        n_workers = min(mp.cpu_count(), 8)

    # Split games across workers
    chunk = max(1, n_games // n_workers)
    tasks = []
    remaining = n_games
    for i in range(n_workers):
        n = min(chunk, remaining)
        if n <= 0:
            break
        tasks.append((deck1, deck2, n, random.randint(0, 2**31)))
        remaining -= n

    with mp.Pool(n_workers) as pool:
        results = pool.map(_run_games_worker, tasks)

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
    if n_workers is None:
        n_workers = min(mp.cpu_count(), 8)

    # Build task list: all matchup pairs
    tasks = []
    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            tasks.append((d1, d2, n_games, random.randint(0, 2**31)))

    total = len(tasks)
    print(f"  Running {total} matchups across {n_workers} workers ({n_games} games each)...")

    with mp.Pool(n_workers) as pool:
        results = pool.map(_run_games_worker, tasks)

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
    if n_workers is None:
        n_workers = min(mp.cpu_count(), 8)

    tasks = []
    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            tasks.append((d1, d2, n_matches, random.randint(0, 2**31)))

    total = len(tasks)
    print(f"  Running {total} Bo3 matchups across {n_workers} workers "
          f"({n_matches} matches each)...")

    with mp.Pool(n_workers) as pool:
        results = pool.map(_run_bo3_worker, tasks)

    matrix = {}
    for proto, ant, mw, m_total, gw, g_total in results:
        matrix[(proto, ant)] = {
            'match_wr': mw / m_total if m_total else 0,
            'game_wr':  gw / g_total if g_total else 0,
        }
    return matrix


def parallel_field(deck, opponents, n_games=100, n_workers=None):
    """Run one deck vs all opponents using multiprocessing."""
    if n_workers is None:
        n_workers = min(mp.cpu_count(), 8)

    tasks = [(deck, opp, n_games, random.randint(0, 2**31))
             for opp in opponents if opp != deck]

    with mp.Pool(n_workers) as pool:
        results = pool.map(_run_games_worker, tasks)

    return results
