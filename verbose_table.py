"""
verbose_table.py — Detailed turn-by-turn game table with hand, board, actions, life.

Usage: python3 verbose_table.py [matchup] [seed]
  e.g. python3 verbose_table.py sneak_a 200
"""

import sys, random
sys.path.insert(0, '.')

from cards import DECKS
from game import PlayerState, GameState, london_mulligan, bug_keep, opp_keep
from engine import bug_turn, opp_turn


ABBREV = {
    'Tamiyo, Inquisitive Student': 'Tamiyo',
    'Orcish Bowmasters': 'Bowmasters',
    'Murktide Regent': 'Murktide',
    'Force of Will': 'FoW',
    'Force of Negation': 'FoN',
    'Underground Sea': 'USea',
    'Polluted Delta': 'PDelta',
    'Misty Rainforest': 'MRain',
    'Flooded Strand': 'FStrand',
    'Marsh Flats': 'MFlats',
    'Scalding Tarn': 'STarn',
    'Kaito, Bane of Nightmares': 'Kaito',
    "Dragon's Rage Channeler": 'DRC',
    'Nethergoyf': 'Goyf',
    "Mishra's Bauble": 'Bauble',
    'Lightning Bolt': 'Bolt',
    'Emrakul, the Aeons Torn': 'Emrakul',
    'Atraxa, Grand Unifier': 'Atraxa',
    'Show and Tell': 'SnT',
    'Sneak Attack': 'Sneak',
    'Lotus Petal': 'Petal',
    'Volcanic Island': 'Volc',
    'Ancient Tomb': 'Tomb',
    'Thundering Falls': 'TFalls',
    'Omniscience': 'Omni',
    'Stock Up': 'Stock',
    'Sink into Stupor': 'Sink',
    'Simian Spirit Guide': 'SSG',
    'Cephalid Illusionist': 'Illusionist',
    'Nomads en-Kor': 'Nomads',
    "Thassa's Oracle": 'Oracle',
    'Karn, the Great Creator': 'Karn',
    'The One Ring': 'Ring',
    'Ugin, Eye of the Storms': 'Ugin',
    'Ulamog, the Ceaseless Hunger': 'Ulamog',
    'Patchwork Automaton': 'Automaton',
    'Thought Monitor': 'Monitor',
    'Kappa Cannoneer': 'Cannoneer',
    'Cori-Steel Cutter': 'Cutter',
    'Brazen Borrower': 'Borrower',
    'Undercity Sewers': 'Sewers',
    'Fatal Push': 'Push',
    'Snuff Out': 'Snuff',
    'Wasteland': 'Waste',
    'Crop Rotation': 'Crop',
    'Expedition Map': 'Map',
    'Disruptor Flute': 'Flute',
    'Pithing Needle': 'Needle',
    "Kozilek's Command": 'KozCmd',
    "Urza's Saga": 'Saga',
    "Urza's Tower": 'Tower',
    "Urza's Mine": 'Mine',
    "Urza's Power Plant": 'Plant',
    'Planar Nexus': 'Nexus',
    'Cloudpost': 'CPost',
    'Glimmerpost': 'GPost',
    'Orim\'s Chant': 'Chant',
    'Swords to Plowshares': 'StP',
    'Voice of Victory': 'Voice',
    'Unholy Heat': 'Heat',
    'Dread Return': 'Dread',
    'Narcomoeba': 'Narco',
    'Flusterstorm': 'Fluster',
    'Archon of Cruelty': 'Archon',
    'Mox Opal': 'Opal',
    "Urza's Bauble": 'UBauble',
    'Pinnacle Emissary': 'Emissary',
    'Emry, Lurker of the Loch': 'Emry',
    'Shadowspear': 'Spear',
    'Lavaspur Boots': 'Boots',
    'Krang, Master Mind': 'Krang',
    'Seat of the Synod': 'Seat',
    'Otawara, Soaring City': 'Otawara',
    'Boseiju, Who Endures': 'Boseiju',
    'Bojuka Bog': 'Bog',
}


def ab(name):
    """Abbreviate a card name."""
    return ABBREV.get(name, name)


def fmt_hand(player):
    names = [ab(c.name) for c in player.hand]
    return ', '.join(names) if names else '(empty)'


def fmt_creatures(player):
    parts = []
    for c in player.creatures:
        short = ab(c.card.name)
        if len(short) > 12:
            short = short[:10] + '..'
        sick = '*' if c.summoning_sick else ''
        parts.append(f"{short} {c.power}/{c.toughness}{sick}")
    return ', '.join(parts) if parts else '-'


def fmt_lands(player):
    parts = []
    for l in player.lands:
        short = ab(l.card.name)
        if len(short) > 8:
            short = short[:7] + '.'
        tap = '(T)' if l.tapped else ''
        parts.append(f"{short}{tap}")
    return ', '.join(parts) if parts else '-'


def fmt_actions(lines):
    """Clean up action lines into concise summaries."""
    actions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Abbreviate card names in action text
        for full, short in ABBREV.items():
            line = line.replace(full, short)
        actions.append(line)
    return actions


def print_row(turn, player, life, actions, hand, creatures, lands):
    """Print one turn as a formatted block."""
    act_str = actions[0] if actions else '(pass)'
    print(f"  T{turn:<3} {player:<4} {life:>4}  {act_str}")
    for a in actions[1:]:
        print(f"       {'':<4} {'':>4}  {a}")
    print(f"       {'':<4} {'':>4}  Hand: [{hand}]")
    print(f"       {'':<4} {'':>4}  Board: {creatures}  |  Lands({len(lands.split(',')) if lands != '-' else 0}): {lands}")
    print()


def run_table_game(matchup, seed=None):
    if seed is not None:
        random.seed(seed)

    bug_hand, bug_lib, bug_mulls = london_mulligan(DECKS['bug'], bug_keep)
    opp_hand, opp_lib, opp_mulls = london_mulligan(DECKS[matchup], opp_keep, matchup)

    bug_goes_first = random.random() < 0.5

    bug_player = PlayerState(name='b', hand=list(bug_hand), library=list(bug_lib))
    opp_player = PlayerState(name='o', hand=list(opp_hand), library=list(opp_lib))

    gs = GameState(bug=bug_player, opp=opp_player, bug_goes_first=bug_goes_first)
    gs.matchup = matchup

    meta_name = matchup.replace('_', ' ').title()
    play_draw = 'ON THE PLAY' if bug_goes_first else 'ON THE DRAW'

    print()
    print(f"  ╔{'═' * 78}╗")
    print(f"  ║  BUG Tempo vs {meta_name:<30}  BUG is {play_draw:<20} ║")
    print(f"  ╚{'═' * 78}╝")
    print()
    print(f"  BUG opening ({7 - bug_mulls} cards, mull {bug_mulls}): {fmt_hand(gs.bug)}")
    print(f"  OPP opening ({7 - opp_mulls} cards, mull {opp_mulls}): {fmt_hand(gs.opp)}")
    print()
    print(f"  {'Turn':<5} {'Who':<4} {'Life':>4}  {'Action / State'}")
    print(f"  {'─' * 80}")

    display_turn = 0

    for rnd in range(1, 16):
        if gs.game_over:
            break
        gs.turn = rnd

        def do_one(label):
            nonlocal display_turn
            display_turn += 1

            player = gs.bug if label == 'BUG' else gs.opp

            if label == 'BUG':
                lines = bug_turn(gs, rnd)
            else:
                lines = opp_turn(gs, rnd, matchup)

            actions = fmt_actions(lines)
            hand = fmt_hand(player)
            creatures = fmt_creatures(player)
            lands = fmt_lands(player)

            print_row(display_turn, label, player.life, actions, hand, creatures, lands)

            return gs.game_over

        if bug_goes_first:
            if do_one('BUG'):
                break
            if do_one('OPP'):
                break
        else:
            if do_one('OPP'):
                break
            if do_one('BUG'):
                break

    # Result
    print(f"  {'═' * 80}")
    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    loser = 'OPP' if winner == 'BUG' else 'BUG'
    print(f"  ★ {winner} WINS on T{display_turn} — {gs.win_reason}")
    print(f"  Final life: BUG {gs.bug.life} | OPP {gs.opp.life}")
    print(f"  BUG board: {fmt_creatures(gs.bug)}  |  OPP board: {fmt_creatures(gs.opp)}")
    print(f"  {'═' * 80}")
    print()


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_table_game(matchup, seed)
