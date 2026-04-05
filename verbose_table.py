"""
verbose_table.py — Turn-by-turn game replay with AI reasoning.

Usage: python3 verbose_table.py [matchup] [seed]
"""

import sys, random
sys.path.insert(0, '.')

from cards import DECKS
from game import PlayerState, GameState, london_mulligan, bug_keep, opp_keep
from engine import bug_turn, opp_turn


ABBREV = {
    'Tamiyo, Inquisitive Student': 'Tamiyo', 'Orcish Bowmasters': 'Bowmasters',
    'Murktide Regent': 'Murktide', 'Force of Will': 'FoW', 'Force of Negation': 'FoN',
    'Underground Sea': 'USea', 'Polluted Delta': 'PDelta', 'Misty Rainforest': 'MRain',
    'Flooded Strand': 'FStrand', 'Marsh Flats': 'MFlats', 'Scalding Tarn': 'STarn',
    'Kaito, Bane of Nightmares': 'Kaito', "Dragon's Rage Channeler": 'DRC',
    'Nethergoyf': 'Goyf', "Mishra's Bauble": 'Bauble', 'Lightning Bolt': 'Bolt',
    'Emrakul, the Aeons Torn': 'Emrakul', 'Atraxa, Grand Unifier': 'Atraxa',
    'Show and Tell': 'SnT', 'Sneak Attack': 'Sneak', 'Lotus Petal': 'Petal',
    'Volcanic Island': 'Volc', 'Ancient Tomb': 'Tomb', 'Thundering Falls': 'TFalls',
    'Omniscience': 'Omni', 'Stock Up': 'Stock', 'Sink into Stupor': 'Sink',
    'Simian Spirit Guide': 'SSG', 'Cephalid Illusionist': 'Illusionist',
    'Nomads en-Kor': 'Nomads', "Thassa's Oracle": 'Oracle',
    'Karn, the Great Creator': 'Karn', 'The One Ring': 'Ring',
    'Ugin, Eye of the Storms': 'Ugin', 'Ulamog, the Ceaseless Hunger': 'Ulamog',
    'Patchwork Automaton': 'Automaton', 'Thought Monitor': 'Monitor',
    'Kappa Cannoneer': 'Cannoneer', 'Cori-Steel Cutter': 'Cutter',
    'Brazen Borrower': 'Borrower', 'Undercity Sewers': 'Sewers',
    'Fatal Push': 'Push', 'Snuff Out': 'Snuff', 'Wasteland': 'Waste',
    'Crop Rotation': 'Crop', 'Expedition Map': 'Map', 'Disruptor Flute': 'Flute',
    'Pithing Needle': 'Needle', "Kozilek's Command": 'KozCmd',
    "Urza's Saga": 'Saga', "Urza's Tower": 'Tower', "Urza's Mine": 'Mine',
    "Urza's Power Plant": 'Plant', 'Planar Nexus': 'Nexus',
    'Cloudpost': 'CPost', 'Glimmerpost': 'GPost', 'Orim\'s Chant': 'Chant',
    'Swords to Plowshares': 'StP', 'Voice of Victory': 'Voice',
    'Unholy Heat': 'Heat', 'Dread Return': 'Dread', 'Narcomoeba': 'Narco',
    'Flusterstorm': 'Fluster', 'Archon of Cruelty': 'Archon',
    'Mox Opal': 'Opal', "Urza's Bauble": 'UBauble',
    'Pinnacle Emissary': 'Emissary', 'Emry, Lurker of the Loch': 'Emry',
    'Shadowspear': 'Spear', 'Lavaspur Boots': 'Boots',
    'Krang, Master Mind': 'Krang', 'Seat of the Synod': 'Seat',
    'Otawara, Soaring City': 'Otawara', 'Boseiju, Who Endures': 'Boseiju',
    'Bojuka Bog': 'Bog', 'City of Traitors': 'City',
}


def ab(name):
    return ABBREV.get(name, name)


def ab_line(line):
    for full, short in ABBREV.items():
        line = line.replace(full, short)
    return line


def fmt_hand(player):
    names = [ab(c.name) for c in player.hand]
    return ', '.join(names) if names else '(empty)'


def fmt_creatures(player):
    parts = []
    for c in player.creatures:
        short = ab(c.card.name)
        if len(short) > 14:
            short = short[:12] + '..'
        sick = ' (sick)' if c.summoning_sick else ''
        parts.append(f"{short} {c.power}/{c.toughness}{sick}")
    return ', '.join(parts) if parts else 'none'


def fmt_lands_short(player):
    parts = []
    for l in player.lands:
        short = ab(l.card.name)
        if len(short) > 8:
            short = short[:8]
        parts.append(short)
    return ', '.join(parts) if parts else 'none'


def reason(line):
    """One-line strategic reasoning for a game action."""
    lo = line.lower()
    if 'play+crack' in lo and '→' in lo:
        return "fix mana + shuffle"
    if lo.startswith('play') and 'waste' in lo:
        return "threaten mana denial"
    if lo.startswith('land:') or (lo.startswith('play ') and '→' not in lo):
        return "develop mana"
    if 'wasteland' in lo and 'destroys' in lo:
        return "deny opponent mana"
    if 'thoughtseize' in lo and 'strips' in lo:
        return "rip their best card"
    if 'thoughtseize' in lo and 'life' in lo:
        return "pay 2 life to see hand + take best card"
    if 'brainstorm' in lo and ('draw' in lo or '3 draws' in lo):
        return "dig 3 deep, put back 2 worst"
    if 'ponder' in lo and ('draw' in lo or 'keeps' in lo):
        return "look at top 3, keep the best"
    if 'stock' in lo and 'draw' in lo:
        return "instant-speed draw 2"
    if 'puts back' in lo:
        return "hide bad cards on top (fetch shuffles later)"
    if 'cast tamiyo' in lo:
        return "0/3 blocker that flips to planeswalker"
    if 'tamiyo flips' in lo:
        return "FLIP! Now a card-advantage engine"
    if 'flash bowmasters' in lo:
        return "punishes every draw: 1 ping + grows Orc Army"
    if 'goyf' in lo and 'cast' in lo:
        return "cheap threat, grows with graveyard types"
    if 'murktide' in lo and 'delve' in lo:
        return "5/5 flyer for ~2 mana via delve"
    if 'cast kaito' in lo:
        return "hexproof threat + card advantage"
    if 'push' in lo and ('kills' in lo or '→ kills' in lo):
        return "1-mana removal"
    if 'snuff out' in lo:
        return "free removal (pay 4 life)"
    if 'bolt' in lo and ('→' in lo or 'damage' in lo):
        return "3 damage, flexible removal or burn"
    if 'fow counters' in lo or 'force of will counters' in lo:
        return "FREE counter (exile blue card)"
    if 'fon counters' in lo:
        return "free counter on opp's turn"
    if 'daze counters' in lo:
        return "free counter (bounce own land)"
    if 'countered' in lo:
        return "COUNTERED!"
    if 'show and tell' in lo and '->' in lo:
        return "COMBO! Cheat huge threat into play"
    if 'sneak attack' in lo and '->' in lo:
        return "COMBO! Sneak creature in with haste"
    if 'emrakul attacks' in lo:
        return "15 damage + annihilator = GG"
    if 'omniscience' in lo and 'free' in lo:
        return "COMBO! Cast everything for free = game over"
    if 'atraxa etb' in lo:
        return "draw ~4 cards off ETB"
    if 'petal' in lo and ('+1 mana' in lo or 'mana=' in lo):
        return "sacrifice for fast mana"
    if 'bowmasters t' in lo and 'orc army' in lo:
        return "PING! Draw trigger fires"
    if 'attack:' in lo:
        if 'unblocked' in lo:
            return "swing for damage"
        if 'blocked' in lo:
            return "attack (got blocked)"
        return "combat"
    if 'cephalid' in lo and 'combo' in lo:
        return "COMBO! Mill library → Oracle wins"
    if 'karn' in lo and 'lattice' in lo:
        return "LOCK! Opponent's lands shut off"
    if 'crop rotation' in lo and 'sac' in lo:
        return "sac land → tutor Cloudpost to play"
    if 'ugin' in lo and 'exile' in lo:
        return "board wipe all colored creatures"
    if lo.startswith('draw:'):
        return "draw for turn"
    if 'bauble' in lo and ('sac' in lo or 'draw' in lo or 'artifact' in lo):
        return "free artifact, draws next turn"
    return ""


def run_table_game(matchup, seed=None):
    if seed is not None:
        random.seed(seed)

    bug_hand, bug_lib, bug_mulls = london_mulligan(DECKS['bug'], bug_keep)
    opp_hand, opp_lib, opp_mulls = london_mulligan(DECKS[matchup], opp_keep, matchup)
    bug_goes_first = random.random() < 0.5

    gs = GameState(
        bug=PlayerState(name='b', hand=list(bug_hand), library=list(bug_lib)),
        opp=PlayerState(name='o', hand=list(opp_hand), library=list(opp_lib)),
        bug_goes_first=bug_goes_first)
    gs.matchup = matchup

    meta_name = matchup.replace('_', ' ').title()

    # ── Header ──
    print()
    print(f"  ╔══════════════════════════════════════════════════════════════════╗")
    print(f"  ║  BUG Tempo  vs  {meta_name:<46} ║")
    print(f"  ║  BUG is {'ON THE PLAY' if bug_goes_first else 'ON THE DRAW':<54} ║")
    print(f"  ╠══════════════════════════════════════════════════════════════════╣")
    print(f"  ║  BUG hand (mull {bug_mulls}): {fmt_hand(gs.bug):<42} ║")
    print(f"  ║  OPP hand (mull {opp_mulls}): {fmt_hand(gs.opp):<42} ║")
    print(f"  ╚══════════════════════════════════════════════════════════════════╝")
    print()

    display_turn = 0

    for rnd in range(1, 16):
        if gs.game_over:
            break
        gs.turn = rnd

        def do_one(label):
            nonlocal display_turn
            display_turn += 1

            player = gs.bug if label == 'BUG' else gs.opp
            opponent = gs.opp if label == 'BUG' else gs.bug
            life_before = player.life

            # Snapshot hand before turn
            hand_before = fmt_hand(player)

            # Execute turn
            if label == 'BUG':
                raw_lines = bug_turn(gs, rnd)
            else:
                raw_lines = opp_turn(gs, rnd, matchup)

            life_after = player.life
            life_delta = life_after - life_before
            life_str = f"{life_after}" if life_delta == 0 else f"{life_after} ({life_delta:+d})"
            opp_life = opponent.life

            # ── Turn header line ──
            print(f"  T{display_turn:<2}  {label:<3}  Life: {life_str:<10}  (Opp life: {opp_life})")

            # ── Hand before ──
            print(f"       Hand:  {hand_before}")

            # ── Plays with reasoning ──
            step = 0
            for raw_line in raw_lines:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                display = ab_line(raw_line)
                r = reason(raw_line)
                step += 1
                if r:
                    print(f"        {step}. {display:<55} ← {r}")
                else:
                    print(f"        {step}. {display}")

            if step == 0:
                print(f"        (no plays)")

            # ── Board after ──
            creatures = fmt_creatures(player)
            lands = fmt_lands_short(player)
            if creatures != 'none':
                print(f"       Board: {creatures}")
            print(f"       Lands: {lands}")
            print()

            return gs.game_over

        if bug_goes_first:
            if do_one('BUG'): break
            if do_one('OPP'): break
        else:
            if do_one('OPP'): break
            if do_one('BUG'): break

    # ── Result ──
    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    print(f"  ══════════════════════════════════════════════════════════════════")
    print(f"  ★ {winner} WINS  │  {gs.win_reason}")
    print(f"    Life: BUG {gs.bug.life}  OPP {gs.opp.life}  │  Game length: T{display_turn}")
    print(f"    BUG board: {fmt_creatures(gs.bug)}")
    print(f"    OPP board: {fmt_creatures(gs.opp)}")
    print(f"  ══════════════════════════════════════════════════════════════════")
    print()


def run_game_data(matchup, seed=None):
    """Run a game and return structured data for markdown/html rendering."""
    if seed is not None:
        random.seed(seed)

    bug_hand, bug_lib, bug_mulls = london_mulligan(DECKS['bug'], bug_keep)
    opp_hand, opp_lib, opp_mulls = london_mulligan(DECKS[matchup], opp_keep, matchup)
    bug_goes_first = random.random() < 0.5

    gs = GameState(
        bug=PlayerState(name='b', hand=list(bug_hand), library=list(bug_lib)),
        opp=PlayerState(name='o', hand=list(opp_hand), library=list(opp_lib)),
        bug_goes_first=bug_goes_first)
    gs.matchup = matchup

    meta_name = matchup.replace('_', ' ').title()
    bug_open = fmt_hand(gs.bug)
    opp_open = fmt_hand(gs.opp)

    turns = []
    display_turn = 0

    for rnd in range(1, 16):
        if gs.game_over:
            break
        gs.turn = rnd

        def do_one(label):
            nonlocal display_turn
            display_turn += 1
            player = gs.bug if label == 'BUG' else gs.opp
            opponent = gs.opp if label == 'BUG' else gs.bug
            hand_before = fmt_hand(player)
            life_before = player.life

            if label == 'BUG':
                raw_lines = bug_turn(gs, rnd)
            else:
                raw_lines = opp_turn(gs, rnd, matchup)

            plays = []
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                plays.append({'text': ab_line(line), 'reason': reason(line),
                              'raw': line})

            turns.append({
                'num': display_turn, 'label': label,
                'life': player.life, 'life_before': life_before,
                'opp_life': opponent.life,
                'hand_before': hand_before,
                'creatures': fmt_creatures(player),
                'lands': fmt_lands_short(player),
                'plays': plays,
            })
            return gs.game_over

        if bug_goes_first:
            if do_one('BUG'): break
            if do_one('OPP'): break
        else:
            if do_one('OPP'): break
            if do_one('BUG'): break

    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    return {
        'matchup': matchup, 'meta_name': meta_name, 'seed': seed,
        'bug_goes_first': bug_goes_first,
        'bug_mulls': bug_mulls, 'opp_mulls': opp_mulls,
        'bug_open': bug_open, 'opp_open': opp_open,
        'turns': turns, 'display_turn': display_turn,
        'winner': winner, 'win_reason': gs.win_reason or '',
        'bug_life': gs.bug.life, 'opp_life': gs.opp.life,
        'bug_board': fmt_creatures(gs.bug),
        'opp_board': fmt_creatures(gs.opp),
    }


def markdown_game(game, game_num=None, series_score=None):
    """Render a single game as detailed markdown tables."""
    g = game
    lines = []

    # Game header
    header = f"### GAME {game_num}" if game_num else f"### {g['meta_name']}"
    if series_score:
        header += f" — {series_score}"
    lines.append(header)
    lines.append("")
    play_draw = "BUG on the play" if g['bug_goes_first'] else "BUG on the draw"
    lines.append(f"*{play_draw}, seed {g['seed']}*")
    lines.append("")

    # Opening hands
    lines.append(f"| | BUG | OPP ({g['meta_name']}) |")
    lines.append(f"|---|---|---|")
    lines.append(f"| **Opening Hand** | {g['bug_open']} | {g['opp_open']} |")
    lines.append("")

    # Turn table
    lines.append(f"| Turn | Who | Life | Key Plays | Reasoning |")
    lines.append(f"|------|-----|------|-----------|-----------|")

    for t in g['turns']:
        delta = t['life'] - t['life_before']
        life_str = str(t['life'])
        if delta != 0:
            life_str += f" ({delta:+d})"

        # Collect key plays and reasons
        key_plays = []
        reasons = []
        for p in t['plays']:
            text = p['text']
            r = p['reason']
            # Skip mundane draw-for-turn unless it's a notable topdeck
            if r == 'draw for turn' and not any(k in text.lower() for k in
                    ('emrakul', 'snt', 'sneak', 'fow', 'omni', 'atraxa')):
                continue
            # Bold key plays
            is_key = any(k in text.lower() for k in
                         ('strips', 'destroys', 'flash bowm', 'fow counters',
                          'daze counters', 'snt ->', 'sneak attack ->',
                          'emrakul attacks', 'omniscience', 'combo', 'attack:',
                          'countered!', 'tamiyo flips', 'murktide', 'cast kaito',
                          'cast goyf'))
            display = f"**{text}**" if is_key else text
            key_plays.append(display)
            if r and r != 'COUNTERED!':
                reasons.append(f"*{r}*")

        if not key_plays:
            key_plays = ["(develop)"]

        plays_str = ', '.join(key_plays[:3])  # limit to 3 most important
        if len(key_plays) > 3:
            plays_str += f" +{len(key_plays)-3} more"
        reason_str = ' / '.join(reasons[:2]) if reasons else ''

        lines.append(f"| T{t['num']} | {t['label']} | {life_str} | {plays_str} | {reason_str} |")

    lines.append("")

    # Board + result
    lines.append(f"**Board:** BUG: {g['bug_board']} | OPP: {g['opp_board']}")
    wcls = "**" if g['winner'] == 'BUG' else "**"
    lines.append(f"**Result:** {g['winner']} wins T{g['display_turn']} — {g['win_reason']}")
    lines.append("")

    return '\n'.join(lines)


def markdown_bo3(matchup, seeds):
    """Generate a full Bo3 markdown report with detailed tables.

    Usage:
        from verbose_table import markdown_bo3
        print(markdown_bo3('sneak_a', [51, 56, 55]))
    """
    games = [run_game_data(matchup, s) for s in seeds]
    meta_name = games[0]['meta_name']

    bug_score = 0
    opp_score = 0
    lines = []

    lines.append(f"## Best of 3: BUG Tempo vs {meta_name}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, g in enumerate(games):
        if i == 0:
            score_str = "0-0"
        else:
            score_str = f"BUG {bug_score} - {opp_score} OPP"

        gnum = i + 1
        game_md = markdown_game(g, game_num=gnum, series_score=score_str)
        lines.append(game_md)
        lines.append("---")
        lines.append("")

        if g['winner'] == 'BUG':
            bug_score += 1
        else:
            opp_score += 1

    # Series summary
    series_winner = 'BUG' if bug_score > opp_score else 'OPP'
    lines.append(f"## Series Summary")
    lines.append("")
    lines.append(f"| Game | Winner | How | Key Moment |")
    lines.append(f"|------|--------|-----|------------|")
    for i, g in enumerate(games):
        # Find the key moment
        key = ''
        for t in g['turns']:
            for p in t['plays']:
                if any(k in p['text'].lower() for k in ('snt ->', 'emrakul attacks',
                       'omniscience', 'combo', 'strips', 'fow counters')):
                    key = p['text']
        if not key:
            key = g['win_reason']
        lines.append(f"| {i+1} | **{g['winner']}** | T{g['display_turn']} {g['win_reason'][:30]} | {key[:50]} |")

    lines.append("")
    lines.append(f"**{series_winner} wins the series {bug_score}-{opp_score}**")
    lines.append("")

    return '\n'.join(lines)


def find_bo3_seeds(matchup, start=1, end=1000):
    """Find 3 seeds for a good Bo3: no mulligans, mix of BUG/OPP wins.

    Picks games to form a 2-1 series with variety (different game lengths,
    both players winning at least once).

    Usage:
        from verbose_table import find_bo3_seeds
        seeds = find_bo3_seeds('sneak_a')  # e.g. [51, 56, 55]
    """
    bug_wins = []
    opp_wins = []

    for seed in range(start, end):
        random.seed(seed)
        _, _, bm = london_mulligan(DECKS['bug'], bug_keep)
        _, _, om = london_mulligan(DECKS[matchup], opp_keep, matchup)
        if bm != 0 or om != 0:
            continue

        # Run the game
        random.seed(seed)
        bh, bl, _ = london_mulligan(DECKS['bug'], bug_keep)
        oh, ol, _ = london_mulligan(DECKS[matchup], opp_keep, matchup)
        bf = random.random() < 0.5
        gs = GameState(
            bug=PlayerState(name='b', hand=list(bh), library=list(bl)),
            opp=PlayerState(name='o', hand=list(oh), library=list(ol)),
            bug_goes_first=bf)
        gs.matchup = matchup
        try:
            for t in range(1, 16):
                if gs.game_over:
                    break
                gs.turn = t
                if bf:
                    bug_turn(gs, t)
                    if gs.game_over:
                        break
                    opp_turn(gs, t, matchup)
                else:
                    opp_turn(gs, t, matchup)
                    if gs.game_over:
                        break
                    bug_turn(gs, t)
        except Exception:
            continue

        w = 'BUG' if gs.winner == 'bug' else 'OPP'
        entry = (seed, gs.turn, gs.win_reason or '')
        if w == 'BUG':
            bug_wins.append(entry)
        else:
            opp_wins.append(entry)

        # Once we have enough of each, build a 2-1 series
        if len(bug_wins) >= 2 and len(opp_wins) >= 2:
            break

    # Prefer 2-1 series with the underdog taking game 1 for drama
    if len(opp_wins) >= 2 and len(bug_wins) >= 1:
        # OPP wins 2-1: OPP, BUG, OPP
        return [opp_wins[0][0], bug_wins[0][0], opp_wins[1][0]]
    elif len(bug_wins) >= 2 and len(opp_wins) >= 1:
        # BUG wins 2-1: BUG, OPP, BUG
        return [bug_wins[0][0], opp_wins[0][0], bug_wins[1][0]]
    elif len(bug_wins) >= 2:
        return [bug_wins[0][0], bug_wins[1][0], bug_wins[0][0]]
    elif len(opp_wins) >= 2:
        return [opp_wins[0][0], opp_wins[1][0], opp_wins[0][0]]
    else:
        # Fallback: just use whatever we found
        all_seeds = [s for s, _, _ in bug_wins + opp_wins]
        while len(all_seeds) < 3:
            all_seeds.append(all_seeds[-1] + 1)
        return all_seeds[:3]


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'

    if '--bo3' in sys.argv:
        idx = sys.argv.index('--bo3')
        remaining = sys.argv[idx+1:]
        # If seeds provided, use them; otherwise auto-pick
        seeds = [int(s) for s in remaining if s.isdigit()]
        if len(seeds) < 3:
            print(f"Finding best Bo3 seeds for {matchup}...", flush=True)
            seeds = find_bo3_seeds(matchup)
            print(f"Using seeds: {seeds}")
            print()
        print(markdown_bo3(matchup, seeds))
    elif '--md' in sys.argv:
        idx = sys.argv.index('--md')
        remaining = sys.argv[idx+1:]
        seed = int(remaining[0]) if remaining and remaining[0].isdigit() else None
        g = run_game_data(matchup, seed)
        print(markdown_game(g))
    else:
        seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
        run_table_game(matchup, seed)
