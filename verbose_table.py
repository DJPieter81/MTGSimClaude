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


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_table_game(matchup, seed)
