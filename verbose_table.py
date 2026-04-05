"""
verbose_table.py — Detailed turn-by-turn game table with hand, board, actions,
life totals, and AI reasoning per play.

Usage: python3 verbose_table.py [matchup] [seed]
  e.g. python3 verbose_table.py sneak_a 2
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


# ── AI Reasoning Engine ─────────────────────────────────────────────────────

def reason_action(line, label, player, opponent, gs, display_turn):
    """Generate strategic reasoning for a game action."""
    lo = line.lower()

    # ── Land plays ──
    if 'play+crack' in lo and 'fetch' in lo or ('play+crack' in lo and '→' in lo):
        return "Fetch → dual: fix colors + thin deck. Shuffle away bad Brainstorm locks."
    if lo.startswith('play') and 'wasteland' in lo.lower():
        return "Deploy Wasteland: threatens to cut opponent off mana next turn."
    if lo.startswith('land:') or lo.startswith('play '):
        return "Develop mana."

    # ── Wasteland activation ──
    if 'wasteland' in lo and 'destroys' in lo:
        return "Wasteland: deny opponent mana — slow their combo/threat deployment."

    # ── Discard ──
    if 'thoughtseize' in lo and 'strips' in lo:
        target = line.split('strips ')[-1] if 'strips ' in line else '?'
        return f"Surgical strike: take their best card ({target}) before they can use it."
    if 'thoughtseize' in lo and 'life' in lo:
        return "Pay 2 life to see their hand and strip the most dangerous card."

    # ── Cantrips ──
    if 'brainstorm' in lo and 'draw' in lo:
        return "Brainstorm: see 3 deep, put back 2 worst. Best cantrip with fetchlands."
    if 'ponder' in lo and 'draw' in lo:
        return "Ponder: look at top 3, pick the best one. Smooth draws."
    if 'stock up' in lo and 'draw' in lo:
        return "Stock Up: instant-speed draw 2 — refuel hand at end of opponent's turn."
    if 'puts back' in lo:
        return "Put back least useful cards — fetch will shuffle if needed."

    # ── Creatures ──
    if 'cast tamiyo' in lo:
        return "T1 Tamiyo: 0/3 blocker that flips into a planeswalker after drawing 3+ cards."
    if 'tamiyo flips' in lo:
        return "Tamiyo transforms! Now a planeswalker — card advantage engine online."
    if 'flash bowmasters' in lo:
        return "Flash in Bowmasters: punishes every card opponent draws — 1 dmg + grows Army."
    if 'cast goyf' in lo or 'nethergoyf' in lo.split('cast ')[-1:][0] if 'cast ' in lo else False:
        return "Deploy Nethergoyf: cheap threat that grows as graveyards fill up."
    if 'murktide' in lo and ('delve' in lo or 'cast' in lo):
        return "Murktide Regent: delve away graveyard → huge 5/5+ flyer for just 2 mana."
    if 'cast kaito' in lo:
        return "Kaito: hexproof 3/4 that surveils + draws — hard to remove card advantage."

    # ── Removal ──
    if 'fatal push' in lo or 'push' in lo and ('kills' in lo or '→' in lo):
        return "Fatal Push: efficient 1-mana removal — kills their key creature."
    if 'snuff out' in lo:
        return "Snuff Out: free removal (pay 4 life) — tempo positive, no mana needed."
    if 'bolt' in lo and ('→' in lo or 'damage' in lo):
        return "Lightning Bolt: 3 damage removal or face burn — flexible and efficient."
    if 'unholy heat' in lo:
        return "Unholy Heat: with delirium (4+ card types in GY) deals 6 damage for 1 mana."

    # ── Countermagic ──
    if 'fow counters' in lo or 'force of will counters' in lo:
        return "Force of Will: free counter (exile blue card) — protect at all costs."
    if 'fon counters' in lo or 'force of negation' in lo:
        return "Force of Negation: free counter on opponent's turn — don't let their spell resolve."
    if 'daze counters' in lo:
        return "Daze: free counter (bounce a land) — punish opponent for tapping out."
    if 'countered' in lo and 'opp' not in lo:
        return "Spell was countered by opponent's interaction."

    # ── Show and Tell / Sneak combo ──
    if 'show and tell' in lo and '->' in lo:
        target = line.split('->')[-1].strip() if '->' in line else '?'
        return f"COMBO: Show and Tell resolves! Both players put a permanent in play — cheating {target} into play."
    if 'sneak attack' in lo and '->' in lo:
        return "COMBO: Activate Sneak Attack for {R} — put creature in with haste, attacks immediately!"
    if 'emrakul attacks' in lo:
        return "Emrakul swings for 15 + annihilator 6 — virtually always lethal."
    if 'omniscience' in lo and 'free' in lo:
        return "COMBO: Omniscience in play — cast anything for free. Game is effectively over."
    if 'atraxa etb' in lo:
        return "Atraxa ETB: reveal top cards, draw one of each type — massive card advantage."
    if 'lotus petal' in lo or 'petal' in lo and '+1 mana' in lo:
        return "Crack Lotus Petal: sacrifice for 1 mana — fast mana to enable early combo."

    # ── Bowmasters triggers ──
    if 'bowmasters t' in lo and 'orc army' in lo:
        return "Bowmasters trigger: opponent drew a card → 1 ping + Orc Army grows."

    # ── Combat ──
    if 'attack:' in lo:
        attackers = line.split('Attack: ')[-1].split(' — ')[0] if 'Attack: ' in line else '?'
        if 'unblocked' in lo:
            dmg = line.split('→')[-1].strip() if '→' in line else ''
            return f"Alpha strike: swing with everything — apply maximum pressure."
        if 'blocked' in lo:
            return "Attack into blockers: trade or force opponent to make tough choices."
        return "Turn creatures sideways — clock the opponent."

    # ── Combo decks ──
    if 'cephalid' in lo and 'combo' in lo:
        return "COMBO: Illusionist + Nomads/Shuko → mill entire library → Oracle wins!"
    if 'karn' in lo and 'lattice' in lo:
        return "COMBO: Karn + Mycosynth Lattice lock — opponent's lands are shut off."
    if 'crop rotation' in lo and 'sac' in lo:
        return "Crop Rotation: sacrifice a land to tutor Cloudpost directly into play — huge mana jump."
    if 'ugin' in lo and 'exile' in lo:
        return "Ugin board wipe: exile all colored permanents — resets opponent's board."

    # ── Draw step ──
    if lo.startswith('draw:'):
        card = line.split('Draw: ')[-1].strip() if 'Draw: ' in line else '?'
        for full, short in ABBREV.items():
            card = card.replace(full, short)
        return f"Draw step: topdeck {card}."

    # ── Bauble ──
    if 'bauble' in lo and ('sac' in lo or 'draw' in lo):
        return "Bauble: free artifact, sac to draw next upkeep — fuels delirium + graveyard."

    # ── Default ──
    return ""


def ab(name):
    return ABBREV.get(name, name)


def fmt_hand(player):
    names = [ab(c.name) for c in player.hand]
    return ', '.join(names) if names else '(empty)'


def fmt_creatures(player):
    parts = []
    for c in player.creatures:
        short = ab(c.card.name)
        if len(short) > 14:
            short = short[:12] + '..'
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
    actions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for full, short in ABBREV.items():
            line = line.replace(full, short)
        actions.append(line)
    return actions


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
    W = 100

    print()
    print(f"  ╔{'═' * (W - 4)}╗")
    print(f"  ║  BUG Tempo vs {meta_name:<30}  BUG is {play_draw:<20}       ║")
    print(f"  ╚{'═' * (W - 4)}╝")
    print()
    print(f"  BUG opening ({7 - bug_mulls} cards, mull {bug_mulls}): {fmt_hand(gs.bug)}")
    print(f"  OPP opening ({7 - opp_mulls} cards, mull {opp_mulls}): {fmt_hand(gs.opp)}")
    print()
    print(f"  {'─' * W}")

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

            if label == 'BUG':
                raw_lines = bug_turn(gs, rnd)
            else:
                raw_lines = opp_turn(gs, rnd, matchup)

            actions = fmt_actions(raw_lines)
            hand = fmt_hand(player)
            creatures = fmt_creatures(player)
            lands = fmt_lands(player)
            n_lands = len(player.lands)

            # ── Print turn header ──
            print()
            print(f"  ┌─ T{display_turn} [{label}] ── Life: {player.life} {'─' * 60}")
            print(f"  │")

            # ── Print each action with reasoning ──
            if not actions:
                print(f"  │  (pass)")
                print(f"  │    ↳ No plays available this turn.")
            else:
                for raw_line, act in zip(raw_lines, actions):
                    act_display = act
                    print(f"  │  {act_display}")
                    reason = reason_action(raw_line, label, player, opponent, gs, display_turn)
                    if reason:
                        print(f"  │    ↳ {reason}")

            # ── State summary ──
            print(f"  │")
            print(f"  │  Hand ({len(player.hand)}): [{hand}]")
            print(f"  │  Board: {creatures}")
            print(f"  │  Lands ({n_lands}): {lands}")
            print(f"  └{'─' * (W - 2)}")

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

    # ── Result ──
    print()
    print(f"  ╔{'═' * (W - 4)}╗")
    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    print(f"  ║  ★ {winner} WINS on T{display_turn}")
    print(f"  ║  Reason: {gs.win_reason}")
    print(f"  ║  Final life: BUG {gs.bug.life} | OPP {gs.opp.life}")
    print(f"  ║  BUG board: {fmt_creatures(gs.bug)}")
    print(f"  ║  OPP board: {fmt_creatures(gs.opp)}")
    print(f"  ╚{'═' * (W - 4)}╝")
    print()


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_table_game(matchup, seed)
