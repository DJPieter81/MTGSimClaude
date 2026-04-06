#!/usr/bin/env python3
"""
MTGSimClaude — Meta Analysis CLI

Usage:
  python3 run_meta.py --list                          All decks with meta share
  python3 run_meta.py --deck storm                    Decklist, strategy, card tags
  python3 run_meta.py --matchup storm burn -n 100     Win rate, avg turn, turn distribution
  python3 run_meta.py --field ur_delver -n 50         One deck vs all others
  python3 run_meta.py --matrix --decks 8 -n 30        Top-8 meta matrix with rankings
  python3 run_meta.py --matrix -n 50 bug storm dimir  Custom deck list matrix
  python3 run_meta.py --verbose storm burn -s 42      Game log (actions only)
  python3 run_meta.py --trace storm burn -s 42        Full log with hand state
  python3 run_meta.py --results                       List saved result files
  python3 run_meta.py --load                          Display latest saved matrix
  python3 run_meta.py --load custom_matrix            Display specific saved result

HTML replay (separate script):
  python3 game_replay.py storm 42                     Single game replay
  python3 game_replay.py dimir --bo3 1 3 5            Bo3 replay
  python3 game_replay.py dimir 42 --pro ur_delver     Any deck as protagonist

Import a new deck:
  echo "4 Delver of Secrets ..." | python3 import_deck.py "My Deck" aggro,tempo_mirror
  python3 import_deck.py --scan                       Batch import from decks/imports/*.txt
"""

import argparse
import random
import sys


def cmd_list():
    """List all available decks with meta share."""
    from cards import DECKS, MATCHUP_META

    print(f"\n{'Deck':<20s} {'Meta Share':>10s}   {'Has Strategy':>12s}")
    print('-' * 46)

    def _get_share(k):
        meta = MATCHUP_META.get(k, {})
        if isinstance(meta, dict) and 'share' in meta:
            return meta['share']
        return 0.0

    from deck_registry import get_strategy
    from sim import STRATEGIES

    ranked = sorted(DECKS.keys(), key=lambda k: -_get_share(k))
    for k in ranked:
        share = _get_share(k)
        has_strat = bool(get_strategy(k) or STRATEGIES.get(k))
        print(f"  {k:<18s} {share:>8.0%}      {'yes' if has_strat else 'NO ':>5s}")
    print(f"\n  {len(ranked)} decks available")


def cmd_deck(deck_key):
    """Show deck details: card list, strategy, tags."""
    from cards import DECKS, MATCHUP_META
    from deck_registry import get_strategy
    from sim import STRATEGIES

    if deck_key not in DECKS:
        print(f"Unknown deck: {deck_key}")
        print(f"Available: {sorted(DECKS.keys())}")
        return

    deck_fn = DECKS[deck_key]
    cards = deck_fn()

    meta = MATCHUP_META.get(deck_key, {})
    name = meta.get('name', deck_key) if isinstance(meta, dict) else deck_key
    share = meta.get('share', 0) if isinstance(meta, dict) else 0

    print(f"\n{'=' * 60}")
    print(f"  {name}  ({deck_key})")
    print(f"  Meta share: {share:.0%}  |  Cards: {len(cards)}")
    print(f"{'=' * 60}")

    # Group by type
    creatures = [c for c in cards if c.is_creature()]
    lands = [c for c in cards if c.is_land()]
    spells = [c for c in cards if not c.is_creature() and not c.is_land()]

    for label, group in [('Creatures', creatures), ('Spells', spells), ('Lands', lands)]:
        if not group:
            continue
        print(f"\n  {label} ({len(group)}):")
        # Count duplicates
        counts = {}
        for c in group:
            key = c.name
            counts[key] = counts.get(key, 0) + 1
        for name, count in sorted(counts.items()):
            card = next(c for c in group if c.name == name)
            tags = f" [{card.tag}]" if card.tag else ""
            cmc = f" CMC{card.cmc}" if not card.is_land() else ""
            print(f"    {count}x {name}{cmc}{tags}")

    # Strategy source
    has_strat = bool(get_strategy(deck_key) or STRATEGIES.get(deck_key))
    strat_fn = get_strategy(deck_key) or STRATEGIES.get(deck_key)
    if strat_fn:
        strat_name = strat_fn.__name__ if hasattr(strat_fn, '__name__') else str(strat_fn)
        strat_loc = f"{strat_fn.__module__}" if hasattr(strat_fn, '__module__') else '?'
        print(f"\n  Strategy: {strat_name} (in {strat_loc})")
    else:
        print(f"\n  Strategy: MISSING")

    # Archetype categories
    from config import MatchupCategory as MC
    categories = []
    for cat_name in ['COMBO', 'FAST_COMBO', 'AGGRO', 'PRISON', 'MIRROR', 'TEMPO_MIRROR',
                     'GY_COMBO', 'LAND_COMBO', 'VIAL_DECKS', 'TRIBAL', 'BOWM_DECKS']:
        cat_set = getattr(MC, cat_name, set())
        if deck_key in cat_set:
            categories.append(cat_name.lower())
    if categories:
        print(f"  Archetype: {', '.join(categories)}")
    else:
        print(f"  Archetype: fair/unclassified")

    # Interaction profile
    from interaction_model import get_or_infer_interaction
    profile = get_or_infer_interaction(deck_key)
    if profile:
        print(f"\n  Interaction profile:")
        print(f"    Speed:       {profile.get('speed', '?')}/5 (1=fastest)")
        print(f"    Resilience:  {profile.get('resilience', '?')}/5 (1=fragile)")
        flags = []
        if profile.get('uses_graveyard'): flags.append('graveyard-dependent')
        if profile.get('uses_veil'): flags.append('Veil of Summer')
        if profile.get('soft_to_wasteland'): flags.append('soft to Wasteland')
        if profile.get('creature_based'): flags.append('creature-based')
        if flags:
            print(f"    Traits:      {', '.join(flags)}")

    # Key card stats
    print(f"\n  Key stats:")
    n_cantrips = sum(1 for c in cards if c.is_cantrip)
    n_creatures = sum(1 for c in cards if c.is_creature())
    n_counters = sum(1 for c in cards if c.tag in ('fow', 'fon', 'daze', 'fluster', 'counter', 'pierce'))
    n_removal = sum(1 for c in cards if c.tag in ('push', 'stp', 'bolt', 'snuffout', 'dismember'))
    n_rituals = sum(1 for c in cards if getattr(c, 'mana_ritual', False) or c.tag in ('darkrit', 'cabalrit'))
    n_combo = sum(1 for c in cards if c.win_condition or c.is_combo_piece)
    avg_cmc = sum(c.cmc for c in cards if not c.is_land()) / max(1, sum(1 for c in cards if not c.is_land()))
    stats = []
    if n_cantrips: stats.append(f"{n_cantrips} cantrips")
    if n_creatures: stats.append(f"{n_creatures} creatures")
    if n_counters: stats.append(f"{n_counters} counters")
    if n_removal: stats.append(f"{n_removal} removal")
    if n_rituals: stats.append(f"{n_rituals} rituals")
    if n_combo: stats.append(f"{n_combo} combo pieces")
    print(f"    {', '.join(stats)}")
    print(f"    Avg CMC (nonland): {avg_cmc:.2f}")


def cmd_matchup(deck1, deck2, n_games, seed=None):
    """Run N games between two decks, show stats."""
    from sim import run_game
    if seed is not None:
        random.seed(seed)

    print(f"\n{'=' * 60}")
    print(f"  {deck1.upper()} vs {deck2.upper()} — {n_games} games")
    print(f"{'=' * 60}")

    results = [run_game(deck1, deck2) for _ in range(n_games)]
    p1_wins = sum(1 for r in results if r.winner == 'p1')
    p2_wins = n_games - p1_wins

    kill_turns = [r.kill_turn for r in results if r.kill_turn]
    lengths = [r.game_length for r in results]

    p1_first_games = [r for r in results if r.p1_went_first]
    p1_first_wr = (sum(1 for r in p1_first_games if r.winner == 'p1') /
                   max(1, len(p1_first_games)))
    p1_second_wr = (sum(1 for r in results if r.winner == 'p1' and not r.p1_went_first) /
                    max(1, sum(1 for r in results if not r.p1_went_first)))

    print(f"\n  {deck1.upper():>15s}: {p1_wins:3d} wins ({p1_wins/n_games:.1%})")
    print(f"  {deck2.upper():>15s}: {p2_wins:3d} wins ({p2_wins/n_games:.1%})")
    print(f"\n  Avg game length:  {sum(lengths)/len(lengths):.1f} turns")
    if kill_turns:
        print(f"  Avg kill turn:    {sum(kill_turns)/len(kill_turns):.1f}")
    print(f"\n  {deck1} on play:   {p1_first_wr:.1%}")
    print(f"  {deck1} on draw:   {p1_second_wr:.1%}")

    # Turn distribution
    turn_hist = {}
    for r in results:
        t = r.game_length
        turn_hist[t] = turn_hist.get(t, 0) + 1
    print(f"\n  Turn distribution:")
    for t in sorted(turn_hist.keys()):
        bar = '#' * (turn_hist[t] * 40 // n_games)
        print(f"    T{t:2d}: {turn_hist[t]:3d} ({turn_hist[t]/n_games:4.0%}) {bar}")

    # Win reasons
    reasons = {}
    for r in results:
        key = r.win_reason.split(' on ')[0].split(' after ')[0][:40]
        reasons[key] = reasons.get(key, 0) + 1
    print(f"\n  Win reasons:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1])[:8]:
        print(f"    {count:3d}  {reason}")


def cmd_field(deck, n_games, seed=None):
    """Run one deck vs all others (parallelized at matchup level)."""
    from cards import DECKS
    if seed is not None:
        random.seed(seed)

    opponents = sorted(k for k in DECKS.keys() if k != deck)

    print(f"\n{'=' * 60}")
    print(f"  {deck.upper()} vs THE FIELD — {n_games} games each")
    print(f"{'=' * 60}\n")

    from parallel import parallel_field
    raw = parallel_field(deck, opponents, n_games)

    total_wins = 0
    total_games = 0
    rows = []

    for d1, opp, wins, losses, kill_turns, lengths in raw:
        n = wins + losses
        wr = wins / n if n > 0 else 0
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        rows.append((opp, wins, losses, wr, avg_len))
        total_wins += wins
        total_games += n

    rows.sort(key=lambda x: -x[3])
    print(f"  {'Opponent':<20s} {'W-L':>7s} {'WR':>6s} {'AvgT':>5s}")
    print(f"  {'-'*40}")
    for opp, w, l, wr, avg_len in rows:
        print(f"  {opp:<20s} {w:2d}-{l:<2d}   {wr:5.0%}  {avg_len:4.1f}")

    overall = total_wins / total_games
    print(f"\n  Overall: {total_wins}/{total_games} ({overall:.1%})")


def cmd_matrix(decks, n_games, top_tier, seed=None, decks_arg=None):
    """Run NxN meta matrix (parallelized at matchup level)."""
    from cards import DECKS, MATCHUP_META
    if seed is not None:
        random.seed(seed)

    # Resolve deck list (same logic as run_meta_matrix)
    if not decks:
        if top_tier > 0:
            def _get_share(k):
                meta = MATCHUP_META.get(k, {})
                if isinstance(meta, dict) and 'share' in meta:
                    return meta['share']
                return 0.0
            ranked = sorted(
                ((k, _get_share(k)) for k in DECKS if _get_share(k) > 0),
                key=lambda x: -x[1])
            pool = [k for k, _ in ranked[:max(top_tier * 2, 10)]]
            if 'bug' not in pool: pool.append('bug')
            chosen = ['bug'] if 'bug' in pool else []
            others = [k for k in pool if k not in chosen]
            random.shuffle(others)
            chosen += others[:top_tier - len(chosen)]
            decks = sorted(chosen)
            print(f"Top-tier selection ({top_tier}): {', '.join(decks)}")
        else:
            decks = sorted(DECKS.keys())

    from parallel import parallel_meta_matrix
    matrix = parallel_meta_matrix(decks, n_games)

    print()
    all_decks = sorted(set(d for pair in matrix for d in pair))

    # Abbreviate long names
    def s(d):
        if len(d) > 8:
            return d[:8]
        return d

    hdr = f"{'':13s}" + ''.join(f'{s(d):>9s}' for d in all_decks)
    print(hdr)
    print('-' * len(hdr))

    for d1 in all_decks:
        row = f'{s(d1):13s}'
        for d2 in all_decks:
            if d1 == d2:
                row += f"{'---':>9s}"
            else:
                wr = matrix.get((d1, d2), 0)
                row += f'{wr:>8.0%} '
        print(row)

    # Meta-weighted WR (T1+T2 only: meta_share >= 0.04)
    from deck_registry import get_meta_share
    t1t2 = {d for d in all_decks if get_meta_share(d) >= 0.04}
    print(f'\nMeta-Weighted WR (T1+T2: {len(t1t2)} decks):')
    evs = []
    for d in all_decks:
        opps = [(d2, get_meta_share(d2)) for d2 in t1t2 if d2 != d and (d, d2) in matrix]
        if not opps:
            evs.append((0.0, d))
            continue
        total_share = sum(s for _, s in opps)
        weighted = sum(matrix[(d, d2)] * s for d2, s in opps) / total_share
        evs.append((weighted, d))
    evs.sort(reverse=True)
    for i, (avg, d) in enumerate(evs):
        tier = 'T1' if get_meta_share(d) >= 0.05 else 'T2' if get_meta_share(d) >= 0.04 else '  '
        bar = '#' * int(avg * 40)
        print(f'  {i+1:2d}. {d:15s} {avg:5.1%}  {tier}  {bar}')

    # Auto-save results
    from meta_results import save_matrix
    tag = 'matrix' if not decks_arg else 'custom_matrix'
    save_matrix(matrix, decks=all_decks, n_games=n_games, tag=tag)


def cmd_verbose(deck1, deck2, seed=None):
    """Run one game with full log output."""
    from sim import run_game
    if seed is not None:
        random.seed(seed)

    r = run_game(deck1, deck2)

    print(f"\n{'=' * 60}")
    print(f"  {deck1.upper()} vs {deck2.upper()}")
    print(f"  Winner: {r.winner.upper()} — {r.win_reason}")
    print(f"  {deck1} {'FIRST' if r.p1_went_first else 'SECOND'} | "
          f"Life: {r.final_p1_life}-{r.final_p2_life} | T{r.game_length}")
    print(f"  P1 hand: {r.p1_opening_hand}")
    print(f"  P2 hand: {r.p2_opening_hand}")
    print(f"{'=' * 60}")

    for line in r.log_lines:
        print(line)


def cmd_trace(deck1, deck2, seed=None):
    """Run one game with full log + hand state each turn."""
    from sim import run_game
    if seed is not None:
        random.seed(seed)

    # For trace, we need to run the game ourselves to access gs mid-game
    # For now, just run verbose with extra header info
    cmd_verbose(deck1, deck2, seed)
    print("\n  (--trace currently shows same output as --verbose)")
    print("  Full AI reasoning trace requires engine instrumentation — future work)")


def main():
    parser = argparse.ArgumentParser(
        description='MTGSimClaude — Meta Analysis CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_meta.py --list
  python3 run_meta.py --deck storm
  python3 run_meta.py --matchup ur_delver dimir -n 200
  python3 run_meta.py --field bug -n 50
  python3 run_meta.py --matrix --decks 10 -n 100
  python3 run_meta.py --matrix -n 50 bug storm ur_delver dimir
  python3 run_meta.py --verbose storm burn -s 42

HTML replay (separate script):
  python3 game_replay.py storm 42
  python3 game_replay.py dimir --bo3 1 3 5
  python3 game_replay.py dimir 42 --pro ur_delver

Import a new deck:
  echo "4 Delver ..." | python3 import_deck.py "My Deck" aggro
  python3 import_deck.py --scan
        """)

    parser.add_argument('--list', action='store_true',
                        help='List all decks with meta share')
    parser.add_argument('--deck', metavar='NAME',
                        help='Show deck details (cards, strategy, tags)')
    parser.add_argument('--matchup', nargs=2, metavar=('D1', 'D2'),
                        help='Run D1 vs D2 sweep')
    parser.add_argument('--field', metavar='DECK',
                        help='Run one deck vs all others')
    parser.add_argument('--matrix', action='store_true',
                        help='Run NxN meta matrix')
    parser.add_argument('--verbose', nargs=2, metavar=('D1', 'D2'),
                        help='Single game with full log')
    parser.add_argument('--trace', nargs=2, metavar=('D1', 'D2'),
                        help='Single game with AI reasoning trace')

    parser.add_argument('-n', type=int, default=100,
                        help='Number of games (default: 100)')
    parser.add_argument('-s', '--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    parser.add_argument('--decks', type=int, default=0,
                        help='For --matrix: pick N top-tier decks (default: use positional args)')
    parser.add_argument('--load', metavar='TAG', nargs='?', const='matrix',
                        help='Load and display saved results (default tag: matrix)')
    parser.add_argument('--results', action='store_true',
                        help='List all saved result files')
    parser.add_argument('deck_list', nargs='*',
                        help='For --matrix: explicit deck list')

    args = parser.parse_args()

    if args.results:
        from meta_results import list_results
        list_results()
    elif args.load:
        from meta_results import load_matrix, print_matrix
        data = load_matrix(args.load)
        if data:
            print_matrix(data)
    elif args.list:
        cmd_list()
    elif args.deck:
        cmd_deck(args.deck)
    elif args.matchup:
        cmd_matchup(args.matchup[0], args.matchup[1], args.n, args.seed)
    elif args.field:
        cmd_field(args.field, args.n, args.seed)
    elif args.matrix:
        decks = args.deck_list if args.deck_list else None
        cmd_matrix(decks, args.n, args.decks or 8, args.seed, decks_arg=decks)
    elif args.verbose:
        cmd_verbose(args.verbose[0], args.verbose[1], args.seed)
    elif args.trace:
        cmd_trace(args.trace[0], args.trace[1], args.seed)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
