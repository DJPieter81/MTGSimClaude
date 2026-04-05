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


def format_hand(player):
    """Summarize hand by card names."""
    names = [c.name for c in player.hand]
    if not names:
        return "(empty)"
    # Abbreviate long names
    abbrev = {
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
        'Dragon\'s Rage Channeler': 'DRC',
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
        "Nomads en-Kor": 'Nomads',
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
    }
    short = [abbrev.get(n, n) for n in names]
    return ', '.join(short)


def format_board(player):
    """Summarize board: creatures + lands."""
    creatures = []
    for c in player.creatures:
        p = c.power
        t = c.toughness
        name = c.card.name
        # Abbreviate
        short = name.split(',')[0]
        if len(short) > 12:
            short = short[:10] + '..'
        sick = '(sick)' if c.summoning_sick else ''
        creatures.append(f"{short} {p}/{t}{sick}")

    lands = []
    for l in player.lands:
        name = l.card.name
        short = {
            'Underground Sea': 'USea', 'Polluted Delta': 'PDelta',
            'Volcanic Island': 'Volc', 'Ancient Tomb': 'Tomb',
            'Misty Rainforest': 'MRain', 'Flooded Strand': 'FStrand',
            'Scalding Tarn': 'STarn', 'Marsh Flats': 'MFlats',
            'Island': 'Island', 'Swamp': 'Swamp', 'Mountain': 'Mtn',
            'Undercity Sewers': 'Sewers', 'Thundering Falls': 'TFalls',
            'Wasteland': 'Waste',
        }.get(name, name[:8])
        tap = '(T)' if l.tapped else ''
        lands.append(f"{short}{tap}")

    parts = []
    if creatures:
        parts.append('Creatures: ' + ', '.join(creatures))
    if lands:
        parts.append('Lands: ' + ', '.join(lands))
    return ' | '.join(parts) if parts else '(empty)'


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

    first_label = 'BUG' if bug_goes_first else 'OPP'
    second_label = 'OPP' if bug_goes_first else 'BUG'

    # Header
    meta_name = matchup.replace('_', ' ').title()
    print(f"{'=' * 100}")
    print(f"  BUG Tempo vs {meta_name}  |  BUG is {'ON THE PLAY' if bug_goes_first else 'ON THE DRAW'}")
    print(f"  BUG mulligans: {bug_mulls}  |  OPP mulligans: {opp_mulls}")
    print(f"{'=' * 100}")
    print()

    # Opening hands
    print(f"  BUG opening hand ({7 - bug_mulls} cards): {format_hand(gs.bug)}")
    print(f"  OPP opening hand ({7 - opp_mulls} cards): {format_hand(gs.opp)}")
    print()

    # Column header
    sep = '-' * 100
    print(f"{'Turn':<8} {'Player':<6} {'Life':>4}  {'Actions':<50} ")
    print(sep)

    display_turn = 0

    for turn in range(1, 16):
        if gs.game_over:
            break
        gs.turn = turn

        def do_turn(label, turn_fn, *args):
            nonlocal display_turn
            display_turn += 1

            player = gs.bug if label == 'BUG' else gs.opp
            life_before = player.life

            # Run the turn
            if label == 'BUG':
                lines = bug_turn(gs, turn)
            else:
                lines = opp_turn(gs, turn, matchup)

            life_after = player.life
            opp_ref = gs.opp if label == 'BUG' else gs.bug

            # Print turn header with board state
            print(f"\n  T{display_turn:<5} {label:<6} {life_after:>3}   ", end='')

            # Filter and print key actions
            key_actions = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                key_actions.append(line)

            if key_actions:
                print(key_actions[0])
                for a in key_actions[1:]:
                    print(f"{'':>17} {a}")
            else:
                print("(pass)")

            # Print board state summary
            print(f"{'':>17} Hand: [{format_hand(player)}]")
            board = format_board(player)
            if 'Creatures' in board:
                print(f"{'':>17} Board: {board}")

            return gs.game_over

        if bug_goes_first:
            if do_turn('BUG', bug_turn, gs, turn):
                break
            if do_turn('OPP', opp_turn, gs, turn, matchup):
                break
        else:
            if do_turn('OPP', opp_turn, gs, turn, matchup):
                break
            if do_turn('BUG', bug_turn, gs, turn):
                break

    # Result
    print()
    print(sep)
    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    print(f"  RESULT: {winner} WINS — {gs.win_reason}")
    print(f"  Final life: BUG {gs.bug.life} | OPP {gs.opp.life}")
    print(f"  Game length: T{display_turn}")
    print(sep)


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_table_game(matchup, seed)
