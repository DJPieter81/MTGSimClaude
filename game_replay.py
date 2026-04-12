"""
game_replay.py — Generate interactive HTML game replay.

Usage: python3 game_replay.py [matchup] [seed]
  e.g. python3 game_replay.py sneak_a 2
"""

import sys, random, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cards import DECKS
from game import PlayerState, GameState, london_mulligan, bug_keep, opp_keep
from engine import play_turn, opp_turn
# Legacy compat: game_replay.py predates the symmetric engine; alias old
# BUG-specific turn entry point to the symmetric play_turn.
def bug_turn(gs, turn, matchup=''):
    # Legacy signature allowed optional matchup; just pass it through via gs.
    if matchup and not getattr(gs, 'matchup', None):
        gs.matchup = matchup
    return play_turn(gs, turn, who='p1')

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
    'Cloudpost': 'CPost', 'Glimmerpost': 'GPost', 'City of Traitors': 'City',
    'Orim\'s Chant': 'Chant', 'Swords to Plowshares': 'StP',
    'Voice of Victory': 'Voice', 'Unholy Heat': 'Heat', 'Dread Return': 'Dread',
    'Narcomoeba': 'Narco', 'Flusterstorm': 'Fluster', 'Archon of Cruelty': 'Archon',
    'Mox Opal': 'Opal', "Urza's Bauble": 'UBauble', 'Pinnacle Emissary': 'Emissary',
    'Emry, Lurker of the Loch': 'Emry', 'Shadowspear': 'Spear',
    'Lavaspur Boots': 'Boots', 'Krang, Master Mind': 'Krang',
    'Seat of the Synod': 'Seat', 'Otawara, Soaring City': 'Otawara',
    'Boseiju, Who Endures': 'Boseiju', 'Bojuka Bog': 'Bog',
}

def ab(name): return ABBREV.get(name, name)
def ab_line(line):
    for f, s in ABBREV.items(): line = line.replace(f, s)
    return line

def fmt_hand(player): return [ab(c.name) for c in player.hand]
def fmt_creatures(player):
    r = []
    for c in player.creatures:
        n = ab(c.card.name)
        if len(n)>14: n=n[:12]+'..'
        r.append({'name':n,'power':c.power,'toughness':c.toughness,'sick':c.summoning_sick})
    return r
def fmt_lands(player): return [ab(l.card.name) for l in player.lands]
def fmt_artifacts(player): return [ab(p.card.name) for p in player.artifacts]
def fmt_enchantments(player): return [ab(p.card.name) for p in player.enchantments]
def fmt_planeswalkers(player): return [ab(p.card.name) for p in player.planeswalkers]
def fmt_graveyard(player): return [ab(c.name) for c in player.graveyard]

def reason(line):
    lo = line.lower()
    if 'play+crack' in lo and '→' in lo: return "fix mana + shuffle"
    if lo.startswith('play') and 'waste' in lo: return "threaten mana denial"
    if lo.startswith('land:') or (lo.startswith('play ') and '→' not in lo): return "develop mana"
    if 'wasteland' in lo and 'destroys' in lo: return "deny opponent mana"
    if 'thoughtseize' in lo and 'strips' in lo: return "rip their best card"
    if 'thoughtseize' in lo and 'life' in lo: return "pay 2 life to see hand + take best card"
    if 'brainstorm' in lo and ('draw' in lo or '3 draws' in lo): return "dig 3 deep, put back 2 worst"
    if 'ponder' in lo and ('draw' in lo or 'keeps' in lo): return "look at top 3, keep the best"
    if 'stock' in lo and 'draw' in lo: return "instant-speed draw 2"
    if 'puts back' in lo: return "hide bad cards on top"
    if 'cast tamiyo' in lo: return "0/3 that flips to planeswalker"
    if 'tamiyo flips' in lo: return "FLIP! Card-advantage engine online"
    if 'flash bowmasters' in lo: return "punishes every draw: 1 ping + grows Army"
    if 'goyf' in lo and 'cast' in lo: return "cheap threat, grows with GY"
    if 'murktide' in lo and 'delve' in lo: return "5/5 flyer for ~2 mana via delve"
    if 'cast kaito' in lo: return "hexproof threat + card advantage"
    if 'push' in lo and ('kills' in lo or '→' in lo): return "1-mana removal"
    if 'snuff out' in lo: return "free removal (pay 4 life)"
    if 'bolt' in lo and ('→' in lo or 'damage' in lo): return "3 damage removal or burn"
    if 'fow counters' in lo or 'force of will counters' in lo: return "FREE counter (exile blue card)"
    if 'daze counters' in lo: return "free counter (bounce own land)"
    if 'countered' in lo: return "COUNTERED!"
    if 'show and tell' in lo and '->' in lo: return "COMBO! Cheat huge threat into play"
    if 'sneak attack' in lo and '->' in lo: return "COMBO! Sneak creature in with haste"
    if 'emrakul attacks' in lo: return "15 damage + annihilator = GG"
    if 'omniscience' in lo and 'free' in lo: return "COMBO! Cast everything free = GG"
    if 'atraxa etb' in lo: return "draw ~4 cards off ETB"
    if 'petal' in lo and ('+1 mana' in lo or 'mana=' in lo): return "sacrifice for fast mana"
    if 'bowmasters t' in lo and 'orc army' in lo: return "PING! Draw trigger fires"
    if 'attack:' in lo and 'unblocked' in lo: return "swing for damage"
    if 'attack:' in lo and 'blocked' in lo: return "attack (got blocked)"
    if 'attack:' in lo: return "combat"
    if 'cephalid' in lo and 'combo' in lo: return "COMBO! Mill library + Oracle wins"
    if 'karn' in lo and 'lattice' in lo: return "LOCK! Opponent's lands shut off"
    if 'crop rotation' in lo: return "sac land + tutor Cloudpost"
    if 'ugin' in lo and 'exile' in lo: return "board wipe all colored creatures"
    if lo.startswith('draw:'): return "draw for turn"
    if 'bauble' in lo: return "free artifact, draws next turn"
    return ""


def classify_play(line):
    """Classify a play line into a visual category. Minimize 'other' — everything gets a badge."""
    lo = line.lower()
    if lo.startswith('draw:') or 'upkeep draw' in lo: return 'draw'
    if 'play+crack' in lo and '→' in lo: return 'fetch'
    if lo.startswith('land:') or lo.startswith('play '): return 'land'
    if 'attack:' in lo or 'attacks for' in lo or 'unblocked' in lo or 'blocks' in lo: return 'combat'
    # Counter — before removal so "FoW counters X" isn't tagged removal
    if 'counter' in lo or 'countered' in lo or 'fluster' in lo: return 'counter'
    # Hand disruption (including TKS exile, abbreviated names)
    if 'thoughtseize' in lo or 'unmask' in lo or 'strips' in lo: return 'discard'
    if 'tks exiles' in lo or ('exile' in lo and ('fow' in lo or 'force' in lo)): return 'discard'
    # Death/destruction
    if 'dies' in lo or 'destroyed' in lo or 'kills' in lo: return 'death'
    # Exile removal
    if 'exile' in lo and ('ending' in lo or 'binding' in lo or 'swords' in lo or 'stp' in lo): return 'exile'
    # SBA
    if 'legend rule' in lo or 'sacrifice' in lo: return 'sba'
    # Removal — bolt/push/heat/snuff targeting creatures (check → or ->)
    if ('bolt' in lo or 'push' in lo or 'heat' in lo or 'snuff' in lo) and ('→' in lo or '->' in lo or '&gt;' in lo): return 'removal'
    # Combo / lethal / wins
    if '★' in line or 'combo' in lo or 'lethal' in lo or 'wins' in lo: return 'combo'
    # Wasteland / mana denial (abbreviated 'Waste →' or full 'Wasteland destroys')
    if ('waste' in lo and ('→' in lo or '->' in lo or '&gt;' in lo)) or ('wasteland' in lo and 'destroy' in lo): return 'interact'
    # Cantrips and draw spells (including abbreviated KozCmd)
    if 'brainstorm' in lo or 'ponder' in lo or 'stock' in lo or 'preordain' in lo: return 'cantrip'
    if ('kozcmd' in lo or "kozilek's command" in lo) and 'draw' in lo: return 'cantrip'
    # Fast mana (abbreviated SSG, Petal, etc.)
    if 'petal' in lo or 'mox' in lo or 'ritual' in lo or 'ssg' in lo or 'spirit guide' in lo: return 'mana'
    if '+1 mana' in lo or '+2 mana' in lo or 'mana=' in lo: return 'mana'
    # Explicit casts
    if 'cast ' in lo or 'flash ' in lo: return 'spell'
    # Triggers / ETB
    if 'bowmasters' in lo or 'orc army' in lo or 'enters' in lo or 'trigger' in lo or 'etb' in lo or 'energy' in lo: return 'trigger'
    # Planeswalker
    if 'flips' in lo or 'loyalty' in lo or 'planeswalker' in lo: return 'pw'
    # Damage / life
    if 'damage' in lo or 'drain' in lo or 'ping' in lo: return 'damage'
    if 'life' in lo and ('gain' in lo or 'pay' in lo or 'lose' in lo): return 'life'
    # Veil of Summer / protection
    if 'veil' in lo or 'blanked' in lo: return 'counter'
    # Chalice lock
    if 'chalice' in lo and 'blank' in lo: return 'combo'
    # Fallback: any non-empty line is a spell/creature deployment
    if lo.strip() and not lo.startswith('(') and not lo.startswith('-'):
        return 'spell'
    return 'other'


def _explain_hand(hand, deck_key):
    """Explain why a hand is keepable or not based on composition."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = [c for c in nonlands if c.is_creature()]
    cantrips = [c for c in nonlands if c.tag in ('bs', 'ponder', 'preordain', 'probe')]
    counters = [c for c in nonlands if c.tag in ('fow', 'fon', 'daze', 'fluster', 'pact_neg', 'vos')]
    removal = [c for c in nonlands if c.tag in ('push', 'bolt', 'heat', 'stp', 'ad', 'dismember', 'snuff')]
    fast_mana = [c for c in nonlands if c.tag in ('petal', 'led', 'chrome_mox', 'darkrit', 'opal', 'ssg', 'mox_diamond')]
    combo = [c for c in nonlands if c.tag in ('show', 'sneak', 'omni', 'entomb', 'reanimate', 'exhume',
             'animate_dead', 'oops', 'spy', 'depths', 'stage', 'crop')]

    parts = []
    parts.append(f"{lc}L/{len(threats)}T/{len(cantrips)}can")
    if counters: parts.append(f"{len(counters)} protection")
    if fast_mana: parts.append(f"{len(fast_mana)} fast mana")
    if combo: parts.append(f"{len(combo)} combo")
    if removal: parts.append(f"{len(removal)} removal")

    issues = []
    if lc == 0: issues.append("no lands")
    elif lc >= 5: issues.append("flood (5+ lands)")
    if not threats and not combo and not cantrips: issues.append("no action")
    if lc == 1 and not cantrips and not fast_mana: issues.append("1 land no cantrip")

    strengths = []
    if combo and (fast_mana or lc >= 1): strengths.append("combo ready")
    if threats and counters: strengths.append("threat + protection")
    if lc in (2, 3) and cantrips: strengths.append("good mana + cantrips")
    if fast_mana and combo: strengths.append("explosive start")

    summary = " · ".join(parts)
    if issues: summary += " — ISSUES: " + ", ".join(issues)
    if strengths: summary += " — " + ", ".join(strengths)
    return summary


def _narrate_turn(td, prev_td, game_context):
    """Generate strategic commentary for a turn based on plays and board state."""
    plays = td.get('plays', [])
    if not plays: return ""

    notes = []
    cats = [p.get('cat', '') for p in plays]
    texts = [p.get('text', '').lower() for p in plays]
    all_text = ' '.join(texts)

    # Combo resolution
    if 'combo' in cats:
        notes.append("COMBO TURN — going for the win")
    # Counter war
    if any('counter' in t for t in texts):
        if any('veil' in t for t in texts):
            notes.append("Veil of Summer blanks all blue interaction before comboing")
        else:
            notes.append("Stack interaction — counter war")
    # Land + pass (developing)
    if set(cats) <= {'land', 'draw', 'other'} and len(plays) <= 3:
        hand_size = len(td.get('hand_before', []))
        if hand_size > 5:
            notes.append("Developing mana, holding cards — waiting for the right moment")
    # Aggressive combat
    if 'combat' in cats:
        damage_plays = [p for p in plays if 'unblocked' in p.get('text', '').lower()]
        if damage_plays:
            notes.append("Pressing damage — clock is ticking")
    # Cantrip-heavy turn
    cantrip_count = sum(1 for c in cats if c == 'cantrip')
    if cantrip_count >= 2:
        notes.append("Digging hard — looking for a specific answer or combo piece")
    # Wasteland
    if any('wasteland' in t and 'destroys' in t for t in texts):
        notes.append("Mana denial — cutting opponent off key colours")
    # Discard
    if any('thoughtseize' in t or 'unmask' in t for t in texts):
        notes.append("Stripping opponent's best card before committing")
    # No land drop when expected
    if td.get('life', 20) > 0 and 'land' not in cats and len(td.get('hand_before', [])) > 0:
        if prev_td and len(prev_td.get('lands', [])) < 3:
            notes.append("Missed land drop — mana screw risk")

    return " · ".join(notes) if notes else ""


def run_one_game(matchup, seed=None, protagonist='bug'):
    """Run a single game and return structured data.
    protagonist: deck key for the protagonist ('bug' uses bug_turn AI, others use protagonist_turn).
    """
    if seed is not None: random.seed(seed)

    from sim import protagonist_turn

    # Wrap mulligan to capture history
    pro_keep = bug_keep if protagonist == 'bug' else opp_keep
    pro_deck = DECKS.get(protagonist, DECKS['bug'])

    pro_mull_history = []
    def _tracking_keep_pro(hand, matchup_arg=''):
        kept = pro_keep(hand, matchup_arg)
        pro_mull_history.append({
            'hand': [ab(c.name) for c in hand],
            'size': len(hand),
            'kept': kept,
            'reason': _explain_hand(hand, protagonist),
        })
        return kept

    opp_mull_history = []
    def _tracking_keep_opp(hand, matchup_arg=''):
        kept = opp_keep(hand, matchup_arg)
        opp_mull_history.append({
            'hand': [ab(c.name) for c in hand],
            'size': len(hand),
            'kept': kept,
            'reason': _explain_hand(hand, matchup),
        })
        return kept

    pro_hand, pro_lib, pro_mulls = london_mulligan(pro_deck, _tracking_keep_pro, protagonist if protagonist != 'bug' else None)
    opp_hand, opp_lib, opp_mulls = london_mulligan(DECKS[matchup], _tracking_keep_opp, matchup)
    pro_goes_first = random.random() < 0.5

    gs = GameState(
        p1=PlayerState(name='b', hand=list(pro_hand), library=list(pro_lib)),
        p2=PlayerState(name='o', hand=list(opp_hand), library=list(opp_lib)),
        p1_goes_first=pro_goes_first)
    gs.matchup = matchup

    pro_label = protagonist.upper().replace('_', ' ')
    meta_name = matchup.replace('_', ' ').title()
    pro_open = fmt_hand(gs.p1)
    opp_open = fmt_hand(gs.p2)

    turns_data = []
    display_turn = 0
    life_pro = [20]
    life_opp = [20]

    for rnd in range(1, 16):
        if gs.game_over: break
        gs.turn = rnd

        def do_one(label):
            nonlocal display_turn
            display_turn += 1
            is_pro = (label == 'PRO')
            player = gs.p1 if is_pro else gs.p2
            opponent = gs.p2 if is_pro else gs.p1
            hand_before = fmt_hand(player)
            life_before = player.life

            if is_pro:
                if protagonist == 'bug':
                    raw = bug_turn(gs, rnd)
                else:
                    raw = protagonist_turn(gs, rnd, protagonist)
            else:
                raw = opp_turn(gs, rnd, matchup)

            plays = []
            for line in raw:
                line = line.strip()
                if not line: continue
                disp = html.escape(ab_line(line))
                r = reason(line)
                is_key = '★' in line or 'combo' in line.lower() or 'lethal' in line.lower()
                is_counter = 'countered' in line.lower()
                cat = classify_play(line)
                plays.append({'text': disp, 'reason': r, 'key': is_key, 'counter': is_counter, 'cat': cat})

            display_label = pro_label if is_pro else 'OPP'
            td = {
                'num': display_turn, 'label': display_label,
                'label_cls': 'bug' if is_pro else 'opp',
                'life': player.life, 'life_before': life_before,
                'opp_life': opponent.life,
                'hand_before': hand_before,
                'hand_after': fmt_hand(player),
                'creatures': fmt_creatures(player),
                'opp_creatures': fmt_creatures(opponent),
                'lands': fmt_lands(player),
                'opp_lands': fmt_lands(opponent),
                'artifacts': fmt_artifacts(player),
                'opp_artifacts': fmt_artifacts(opponent),
                'enchantments': fmt_enchantments(player),
                'opp_enchantments': fmt_enchantments(opponent),
                'planeswalkers': fmt_planeswalkers(player),
                'opp_planeswalkers': fmt_planeswalkers(opponent),
                'graveyard': fmt_graveyard(player),
                'opp_graveyard': fmt_graveyard(opponent),
                'plays': plays,
            }
            prev = turns_data[-1] if turns_data else None
            td['narrative'] = _narrate_turn(td, prev, {})
            turns_data.append(td)
            life_pro.append(gs.p1.life)
            life_opp.append(gs.p2.life)
            return gs.game_over

        if pro_goes_first:
            if do_one('PRO'): break
            if do_one('OPP'): break
        else:
            if do_one('OPP'): break
            if do_one('PRO'): break

    winner = pro_label if gs.winner == 'p1' else 'OPP'
    if not gs.game_over:
        pp = sum(c.power for c in gs.p1.creatures)
        ap = sum(c.power for c in gs.p2.creatures)
        winner = pro_label if (pp > ap or gs.p1.life > gs.p2.life + 3) else 'OPP'

    return {
        'matchup': matchup, 'meta_name': meta_name, 'seed': seed,
        'protagonist': protagonist, 'pro_label': pro_label,
        'bug_goes_first': pro_goes_first,
        'bug_mulls': pro_mulls, 'opp_mulls': opp_mulls,
        'bug_mull_history': pro_mull_history, 'opp_mull_history': opp_mull_history,
        'bug_open': pro_open, 'opp_open': opp_open,
        'turns_data': turns_data, 'life_bug': life_pro, 'life_opp': life_opp,
        'display_turn': display_turn, 'winner': winner, 'win_reason': gs.win_reason or '',
        'bug_life': gs.p1.life, 'opp_life': gs.p2.life,
        'bug_board': fmt_creatures(gs.p1), 'opp_board': fmt_creatures(gs.p2),
    }


def generate_html(matchup, seeds, protagonist='bug'):
    """Generate HTML for one or more games (Bo1 or Bo3)."""
    if isinstance(seeds, (int, type(None))):
        seeds = [seeds]

    # Bo3: stop when either player reaches 2 wins
    games = []
    p1_wins = 0
    p2_wins = 0
    for s in seeds:
        g = run_one_game(matchup, s, protagonist=protagonist)
        games.append(g)
        if g.get('winner') == 'p1' or g.get('winner') == protagonist:
            p1_wins += 1
        else:
            p2_wins += 1
        if p1_wins >= 2 or p2_wins >= 2:
            break
    meta_name = games[0]['meta_name']
    pro_label = games[0].get('pro_label', 'BUG')
    is_bo3 = len(games) > 1

    pro_wins = sum(1 for g in games if g['winner'] == pro_label)
    opp_wins = sum(1 for g in games if g['winner'] == 'OPP')
    series_winner = pro_label if pro_wins > opp_wins else 'OPP'

    # Build HTML
    h = []
    title = f'Bo3 Replay: {pro_label} vs {html.escape(meta_name)}' if is_bo3 else f'Game Replay: {pro_label} vs {html.escape(meta_name)}'
    h.append(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#ffffff;color:#1f2328;font-family:'Segoe UI',system-ui,sans-serif;padding:20px;max-width:920px;margin:0 auto;font-size:13px}}
.header{{background:linear-gradient(135deg,#f0f4f8,#e8edf2);border:1px solid #d0d7de;border-radius:12px;padding:24px;margin-bottom:16px}}
.header h1{{font-size:1.5em;margin-bottom:6px;color:#1f2328}}
.header h1 .vs{{color:#9198a1}}
.header .bug-name{{color:#0969da}}
.header .opp-name{{color:#d1242f}}
.header .meta{{color:#656d76;font-size:0.85em;margin-top:4px}}
.series-score{{font-size:1.3em;margin-top:8px;font-weight:700}}
.series-score .bug-s{{color:#0969da}}.series-score .opp-s{{color:#d1242f}}
.legend-box{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:11px}}
.legend-title{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#9198a1;margin-bottom:8px}}
.legend-row{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.leg-item{{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.leg-label{{color:#656d76;font-size:10px}}
.legend-note{{margin-top:8px;font-size:10px;color:#9198a1;font-style:italic;border-top:1px solid #d0d7de;padding-top:6px}}
.game-tabs{{display:flex;gap:4px;margin-bottom:0}}
.game-tab{{background:#eaeef2;color:#656d76;border:1px solid #d0d7de;border-radius:8px 8px 0 0;padding:10px 20px;cursor:pointer;font-weight:600;font-size:0.9em;transition:background .15s}}
.game-tab:hover{{background:#d0d7de}}
.game-tab.active{{background:#ffffff;color:#1f2328;border-bottom-color:#ffffff}}
.game-tab .winner-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:6px}}
.game-tab .winner-dot.bug{{background:#0969da}}.game-tab .winner-dot.opp{{background:#d1242f}}
.game-panel{{display:none;background:#ffffff;border:1px solid #d0d7de;border-top:none;border-radius:0 8px 8px 8px;padding:16px;margin-bottom:16px}}.game-panel.active{{display:block}}
.hands{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}}
.hand-box{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:12px}}
.hand-box h3{{font-size:0.8em;color:#656d76;margin-bottom:8px;font-weight:600}}
.hand-box.bug{{border-left:3px solid #0969da}}.hand-box.opp{{border-left:3px solid #d1242f}}
.pill{{display:inline-block;background:#eaeef2;border:1px solid #d0d7de;border-radius:10px;padding:2px 8px;margin:2px;font-size:0.78em;font-family:'Fira Code','Consolas',monospace;color:#9a6700}}
.controls{{display:flex;gap:8px;margin-bottom:12px;align-items:center}}
.controls button{{background:#f6f8fa;color:#1f2328;border:1px solid #d0d7de;border-radius:5px;padding:5px 12px;cursor:pointer;font-size:0.82em}}
.controls button:hover{{background:#eaeef2;border-color:#0969da}}
.life-chart{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:14px;margin-bottom:12px}}
.life-chart h3{{font-size:0.82em;color:#656d76;margin-bottom:10px;font-weight:600}}
.life-chart svg{{width:100%;height:80px}}
.turn{{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;margin-bottom:6px;overflow:hidden;transition:border-color .15s}}
.turn.bug{{border-left:3px solid #0969da}}.turn.opp{{border-left:3px solid #d1242f}}
.turn.active{{border-color:#bf8700!important}}
.turn-header{{padding:10px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none;transition:background .1s}}
.turn-header:hover{{background:#eaeef2}}
.turn-header .left{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.turn-header .tnum{{font-weight:700;font-size:1.05em;min-width:32px;font-family:'Fira Code',monospace}}
.turn-header .tnum.bug{{color:#0969da}}.turn-header .tnum.opp{{color:#d1242f}}
.turn-header .player{{font-weight:600;font-size:0.82em;padding:2px 7px;border-radius:4px}}
.turn-header .player.bug{{background:#ddf4ff;color:#0969da}}.turn-header .player.opp{{background:#ffebe9;color:#d1242f}}
.turn-header .life{{font-size:0.85em;color:#656d76}}
.turn-header .life b{{color:#1f2328}}
.hand-count{{font-size:.75em;color:#9198a1;background:#eaeef2;padding:1px 5px;border-radius:3px;font-family:'Fira Code',monospace}}
.turn-header .arrow{{color:#9198a1;transition:transform 0.2s;font-size:0.75em;flex-shrink:0}}
.turn.open .arrow{{transform:rotate(90deg)}}
.turn-body{{display:none;padding:0 14px 14px;border-top:1px solid #d0d7de}}
.turn.open .turn-body{{display:block}}
.section-label{{font-size:0.7em;text-transform:uppercase;letter-spacing:1px;color:#9198a1;margin:10px 0 5px;font-weight:600}}
.hand-pills{{margin-bottom:4px}}
.draw-row{{margin-bottom:4px;display:flex;align-items:center;gap:4px}}
.play{{padding:5px 0;display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap;border-bottom:1px solid #eaeef2}}
.play .step{{color:#9198a1;font-size:0.82em;min-width:18px;text-align:right;padding-top:2px;flex-shrink:0}}
.play .action{{font-family:'Fira Code','Consolas',monospace;font-size:0.82em;color:#1f2328;flex:1}}
.play .action.key{{color:#9a6700;font-weight:600}}
.play .action.counter{{color:#d1242f;text-decoration:line-through;opacity:0.7}}
.play .reasoning{{font-size:0.75em;color:#656d76;font-style:italic;width:100%;padding:2px 0 2px 24px;margin-top:1px;border-left:2px solid #d0d7de;margin-left:24px;display:none}}
body.show-reasoning .play .reasoning{{display:block}}
.reasoning-toggle{{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;background:#f6f8fa;border:1px solid #d0d7de;border-radius:4px;cursor:pointer;font-size:0.8em;color:#656d76;user-select:none;margin-left:8px}}
.reasoning-toggle:hover{{background:#eaeef2;color:#1f2328}}
body.show-reasoning .reasoning-toggle{{background:#ddf4ff;color:#0969da;border-color:#0969da60}}
.reasoning-toggle::before{{content:"·";font-size:1.4em;line-height:0}}
body.show-reasoning .reasoning-toggle::before{{content:"✓"}}
.play .cat-badge{{font-size:0.62em;text-transform:uppercase;letter-spacing:0.5px;padding:1px 5px;border-radius:3px;font-weight:700;margin-right:3px;font-family:system-ui;min-width:46px;text-align:center;display:inline-block;flex-shrink:0}}
.cat-draw{{background:#f0f0ff;color:#5a5a9a}}.cat-land{{background:#dafbe1;color:#1a7f37}}.cat-combat{{background:#ffebe9;color:#d1242f}}.cat-interact{{background:#f5f0ff;color:#8250df}}
.cat-discard{{background:#fff8c5;color:#9a6700}}.cat-removal{{background:#ffebe9;color:#d1242f}}.cat-combo{{background:#fff0f8;color:#bf4b8a}}.cat-spell{{background:#ddf4ff;color:#0969da}}
.cat-trigger{{background:#fff8c5;color:#9a6700}}.cat-cantrip{{background:#ddf4ff;color:#0969da}}.cat-mana{{background:#dafbe1;color:#1a7f37}}.cat-other{{background:#f6f8fa;color:#656d76}}
.cat-fetch{{background:#f5f0ff;color:#6639ba}}.cat-counter{{background:#f5f0ff;color:#8250df}}.cat-death{{background:#ffebe9;color:#d1242f}}.cat-exile{{background:#f5f0ff;color:#6639ba}}
.cat-sba{{background:#f6f8fa;color:#9198a1}}.cat-pw{{background:#ddf4ff;color:#0969da}}.cat-damage{{background:#ffebe9;color:#d1242f}}.cat-life{{background:#dafbe1;color:#1a7f37}}
.board-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px}}
.board-side{{background:#ffffff;border:1px solid #d0d7de;border-radius:6px;padding:8px 10px}}
.board-side h4{{font-size:0.7em;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;font-weight:600}}
.board-side.bug h4{{color:#0969da}}.board-side.opp h4{{color:#d1242f}}
.combat-detail{{background:#fff8f8;border:1px solid #f5b8b0;border-radius:5px;padding:6px 10px;margin:3px 0;font-family:'Fira Code','Consolas',monospace;font-size:0.8em;color:#1f2328}}
.combat-detail .atk-line{{color:#9a6700;margin-bottom:2px}}.combat-detail .blk-line{{color:#8250df;margin-bottom:2px}}
.combat-detail .dmg-line{{color:#d1242f;font-weight:600}}.combat-detail .death-line{{color:#d1242f;opacity:0.8;font-style:italic}}
.board{{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}}
.creature-badge{{background:#ddf4ff;border:1px solid #a8d8f0;border-radius:5px;padding:3px 8px;font-family:'Fira Code','Consolas',monospace;font-size:0.78em;color:#0969da;display:inline-flex;align-items:center;gap:4px}}
.creature-badge .pt{{color:#656d76;font-size:0.9em}}
.creature-badge .sick{{color:#d1242f;font-size:0.7em}}
.land-list{{font-family:'Fira Code','Consolas',monospace;font-size:0.78em;color:#1a7f37}}
.perm-list{{font-family:'Fira Code','Consolas',monospace;font-size:0.78em}}
.art-list{{color:#9a6700}}
.ench-list{{color:#8250df}}
.pw-list{{color:#0969da}}
.gy-list{{color:#9198a1;font-size:0.72em}}
.mull-step{{display:flex;align-items:center;gap:8px;margin:5px 0 2px;font-size:0.8em}}
.mull-label{{color:#656d76;font-weight:600}}
.keep-tag{{color:#1a7f37;font-weight:700;font-size:0.82em;padding:1px 6px;background:#dafbe1;border-radius:3px}}
.mull-tag{{color:#d1242f;font-weight:700;font-size:0.82em;padding:1px 6px;background:#ffebe9;border-radius:3px}}
.mull-pills{{opacity:0.5;margin:2px 0}}
.mull-pills .pill{{font-size:0.7em;text-decoration:line-through}}
.mull-reason{{font-size:0.75em;color:#d1242f;margin:2px 0 6px;font-style:italic;padding-left:6px;border-left:2px solid #f5b8b0}}
.hand-analysis{{font-size:0.75em;color:#1a7f37;margin-top:5px;padding:3px 7px;background:#dafbe1;border-radius:3px;border-left:2px solid #4ac26b}}
.turn-narrative{{font-size:0.8em;color:#8250df;background:#f5f0ff;border-left:2px solid #d2a8ff;padding:4px 10px;margin:8px 0;border-radius:0 4px 4px 0;font-style:italic}}
.play-response{{background:#fff8e1;border-left:3px solid #bf8700;border-radius:0 4px 4px 0;padding:5px 6px;margin:2px 0}}
.respond-badge{{font-size:.75em;font-weight:700;margin-right:6px;letter-spacing:.3px}}
.reason-toggle{{color:#9198a1;font-size:1.1em;cursor:pointer;padding:0 4px;border-radius:3px;user-select:none;flex-shrink:0}}.reason-toggle:hover{{color:#1f2328;background:#eaeef2}}.reason-toggle.open{{color:#0969da}}
.result{{background:linear-gradient(135deg,#f0f4f8,#e8edf2);border:2px solid #d0d7de;border-radius:12px;padding:24px;text-align:center;margin-top:16px}}
.result h2{{font-size:1.8em;margin-bottom:6px}}
.result h2.bug-win{{color:#0969da}}.result h2.opp-win{{color:#d1242f}}
.result .reason{{color:#656d76;font-size:0.9em;margin-bottom:4px}}
.result .stats{{color:#9198a1;font-size:0.85em}}
.kbd{{font-size:0.75em;color:#9198a1;margin-left:auto}}
</style></head><body>
""")

    # Header
    h.append(f'<div class="header">')
    h.append(f'<h1><span class="bug-name">{html.escape(pro_label)}</span> <span class="vs">vs</span> <span class="opp-name">{html.escape(meta_name)}</span></h1>')
    if is_bo3:
        h.append(f'<div class="series-score"><span class="bug-s">{html.escape(pro_label)} {pro_wins}</span> — <span class="opp-s">{opp_wins} OPP</span></div>')
        sw_cls = 'bug-name' if series_winner != 'OPP' else 'opp-name'
        h.append(f'<div class="meta"><span class="{sw_cls}">{series_winner} wins the series</span></div>')
    h.append(f'</div>')

    # Game tabs (if Bo3)
    if is_bo3:
        h.append(f'<div class="game-tabs">')
        for gi, g in enumerate(games):
            act = ' active' if gi == 0 else ''
            dot_cls = 'bug' if g['winner'] != 'OPP' else 'opp'
            h.append(f'<div class="game-tab{act}" onclick="showGame({gi})">Game {gi+1}<span class="winner-dot {dot_cls}"></span></div>')
        h.append(f'</div>')

    # Each game panel
    for gi, g in enumerate(games):
        act = ' active' if gi == 0 else ''
        h.append(f'<div class="game-panel{act}" id="game-{gi}">')

        # Opening hands with mulligan history
        play_str = 'ON THE PLAY' if g['bug_goes_first'] else 'ON THE DRAW'
        h.append(f'<div class="meta" style="margin-bottom:12px;color:#656d76">{html.escape(pro_label)} is {play_str} &nbsp;|&nbsp; Seed: {g["seed"]}</div>')
        h.append(f'<div class="hands">')
        # Protagonist mulligan history
        h.append(f'<div class="hand-box bug"><h3>{html.escape(pro_label)} (mull {g["bug_mulls"]})</h3>')
        for mi, mh in enumerate(g.get('bug_mull_history', [])):
            kept_cls = 'keep-tag' if mh['kept'] else 'mull-tag'
            kept_txt = '✓ KEEP' if mh['kept'] else '✗ MULL'
            if mi > 0 or not mh['kept']:
                h.append(f'<div class="mull-step">')
                h.append(f'<span class="mull-label">{mh["size"]} cards</span>')
                h.append(f'<span class="{kept_cls}">{kept_txt}</span>')
                h.append(f'</div>')
            if not mh['kept']:
                h.append(f'<div class="mull-pills">')
                for c in mh['hand']: h.append(f'<span class="pill mull-pill">{html.escape(c)}</span>')
                h.append(f'</div>')
                h.append(f'<div class="mull-reason">{html.escape(mh["reason"])}</div>')
        # Final kept hand
        for c in g['bug_open']: h.append(f'<span class="pill">{html.escape(c)}</span>')
        final_mh = g.get('bug_mull_history', [{}])[-1] if g.get('bug_mull_history') else {}
        if final_mh.get('reason'):
            h.append(f'<div class="hand-analysis">{html.escape(final_mh["reason"])}</div>')
        h.append(f'</div>')
        # Opponent mulligan history
        h.append(f'<div class="hand-box opp"><h3>OPP (mull {g["opp_mulls"]})</h3>')
        for mi, mh in enumerate(g.get('opp_mull_history', [])):
            if not mh['kept']:
                h.append(f'<div class="mull-step"><span class="mull-label">{mh["size"]} cards</span><span class="mull-tag">✗ MULL</span></div>')
                h.append(f'<div class="mull-pills">')
                for c in mh['hand']: h.append(f'<span class="pill mull-pill">{html.escape(c)}</span>')
                h.append(f'</div>')
                h.append(f'<div class="mull-reason">{html.escape(mh["reason"])}</div>')
        for c in g['opp_open']: h.append(f'<span class="pill">{html.escape(c)}</span>')
        final_opp_mh = g.get('opp_mull_history', [{}])[-1] if g.get('opp_mull_history') else {}
        if final_opp_mh.get('reason'):
            h.append(f'<div class="hand-analysis">{html.escape(final_opp_mh["reason"])}</div>')
        h.append(f'</div></div>')

        # Life chart
        lb, lo = g['life_bug'], g['life_opp']
        mt = len(lb)
        h.append(f'<div class="life-chart"><h3>Life Totals</h3><svg viewBox="0 0 {mt*40} 80">')
        for i in range(1, len(lb)):
            x = i * 40 - 20
            by = max(5, 75 - (max(lb[i],0) / 22 * 70))
            oy = max(5, 75 - (max(lo[i],0) / 22 * 70))
            if i > 1:
                px = (i-1)*40-20
                pby = max(5, 75 - (max(lb[i-1],0)/22*70))
                poy = max(5, 75 - (max(lo[i-1],0)/22*70))
                h.append(f'<line x1="{px}" y1="{pby}" x2="{x}" y2="{by}" stroke="#0969da" stroke-width="2"/>')
                h.append(f'<line x1="{px}" y1="{poy}" x2="{x}" y2="{oy}" stroke="#d1242f" stroke-width="2"/>')
            h.append(f'<circle cx="{x}" cy="{by}" r="3" fill="#0969da"/>')
            h.append(f'<circle cx="{x}" cy="{oy}" r="3" fill="#d1242f"/>')
            h.append(f'<text x="{x}" y="{by-6}" text-anchor="middle" fill="#0969da" font-size="9">{lb[i]}</text>')
            h.append(f'<text x="{x}" y="{oy+12}" text-anchor="middle" fill="#d1242f" font-size="9">{lo[i]}</text>')
        h.append(f'</svg></div>')

        # Controls
        h.append(f'<div class="controls">')
        h.append(f'<button onclick="expandAll()">Expand All</button>')
        h.append(f'<button onclick="collapseAll()">Collapse All</button>')
        h.append(f'<span class="reasoning-toggle" onclick="toggleReasoning()" title="Toggle AI reasoning annotations">AI reasoning</span>')
        h.append(f'<span class="kbd">↑↓ navigate &nbsp; Enter: toggle &nbsp; R: reasoning</span>')
        h.append(f'</div>')

        # Turns
        for i, td in enumerate(g['turns_data']):
            label = td['label']
            cls = td.get('label_cls', label.lower())
            is_last = (i == len(g['turns_data']) - 1)
            open_cls = ' open' if is_last else ''

            delta = td['life'] - td['life_before']
            delta_str = f' ({delta:+d})' if delta != 0 else ''

            h.append(f'<div class="turn {cls}{open_cls}" data-idx="{i}">')
            h.append(f'<div class="turn-header" onclick="toggle(this.parentElement)">')
            h.append(f'<div class="left">')
            h.append(f'<span class="tnum {cls}">T{td["num"]}</span>')
            h.append(f'<span class="player {cls}">{label}</span>')
            h.append(f'<span class="life">Life: <b>{td["life"]}{delta_str}</b> &nbsp;|&nbsp; Opp: {td["opp_life"]}</span>')
            # Quick summary badges in header
            cats_in_turn = set(p.get('cat','') for p in td['plays'])
            summary_parts = []
            n_combat = sum(1 for p in td['plays'] if p.get('cat') == 'combat')
            n_spells = sum(1 for p in td['plays'] if p.get('cat') in ('spell','cantrip'))
            n_interact = sum(1 for p in td['plays'] if p.get('cat') in ('interact','discard','removal'))
            n_combo = sum(1 for p in td['plays'] if p.get('cat') == 'combo')
            if n_combat: summary_parts.append(f'<span style="color:#d1242f;font-size:0.75em">⚔{n_combat}</span>')
            if n_spells: summary_parts.append(f'<span style="color:#0969da;font-size:0.75em">🃏{n_spells}</span>')
            if n_interact: summary_parts.append(f'<span style="color:#d2a8ff;font-size:0.75em">🛡{n_interact}</span>')
            if n_combo: summary_parts.append(f'<span style="color:#f778ba;font-size:0.75em">★{n_combo}</span>')
            if summary_parts:
                h.append(f'<span style="margin-left:8px">{" ".join(summary_parts)}</span>')
            h.append(f'</div><span class="arrow">&#9654;</span></div>')

            h.append(f'<div class="turn-body">')
            h.append(f'<div class="section-label">Hand</div><div class="hand-pills">')
            for c in td['hand_before']:
                h.append(f'<span class="pill">{html.escape(c)}</span>')
            h.append(f'</div>')

            h.append(f'<div class="section-label">Plays</div>')
            for j, p in enumerate(td['plays']):
                cls_p = ' key' if p['key'] else (' counter' if p['counter'] else '')
                cat = p.get('cat', 'other')
                cat_label = {'draw':'DRAW','land':'LAND','fetch':'FETCH','combat':'COMBAT',
                             'counter':'COUNTER','interact':'COUNTER',
                             'discard':'DISCARD','removal':'REMOVE','combo':'COMBO','spell':'CAST',
                             'trigger':'TRIGGER','cantrip':'DIG','mana':'MANA',
                             'death':'DIES','exile':'EXILE','sba':'SBA','pw':'PW',
                             'damage':'DMG','life':'LIFE','other':''}.get(cat,'')
                is_combat = cat == 'combat'
                h.append(f'<div class="play"><span class="step">{j+1}.</span>')
                if cat_label:
                    h.append(f'<span class="cat-badge cat-{cat}">{cat_label}</span>')
                h.append(f'<span class="action{cls_p}">{p["text"]}</span>')
                if p['reason']:
                    h.append(f'<span class="reasoning">&larr; {html.escape(p["reason"])}</span>')
                h.append(f'</div>')
                # Enhanced combat detail: parse attack lines for creature-level breakdown
                if is_combat and ('unblocked' in p['text'].lower() or 'blocks' in p['text'].lower() or 'attacks for' in p['text'].lower()):
                    h.append(f'<div class="combat-detail">')
                    text = p['text']
                    if 'unblocked' in text.lower():
                        # Parse "Attack: X, Y — N unblocked → player at M"
                        if '—' in text or '&#x2014;' in text:
                            parts = text.replace('&#x2014;', '—').split('—', 1)
                            names_part = parts[0].replace('Attack:', '').strip() if len(parts) > 1 else ''
                            dmg_part = parts[1].strip() if len(parts) > 1 else text
                            if names_part:
                                h.append(f'<div class="atk-line">⚔ Attackers: {names_part}</div>')
                            h.append(f'<div class="dmg-line">→ {dmg_part}</div>')
                    elif 'blocks' in text.lower():
                        h.append(f'<div class="blk-line">🛡 {text}</div>')
                    elif 'attacks for' in text.lower():
                        h.append(f'<div class="dmg-line">💀 {text}</div>')
                    h.append(f'</div>')
                # Enhanced: show creature deaths inline
                if 'dies' in p['text'].lower():
                    h.append(f'<div class="combat-detail"><div class="death-line">☠ {p["text"]}</div></div>')
            if not td['plays']:
                h.append(f'<div class="play"><span class="step">-</span><span class="action" style="color:#484f58">(no plays)</span></div>')

            # Strategic narrative
            narrative = td.get('narrative', '')
            if narrative:
                h.append(f'<div class="turn-narrative">{html.escape(narrative)}</div>')

            # Enhanced board: show BOTH sides
            h.append(f'<div class="section-label">Board State</div>')
            h.append(f'<div class="board-grid">')
            # Player side
            side_label = td['label']
            side_cls = td.get('label_cls', 'bug')
            opp_cls = 'opp' if side_cls == 'bug' else 'bug'
            opp_label = 'OPP' if side_cls == 'bug' else pro_label
            h.append(f'<div class="board-side {side_cls}">')
            h.append(f'<h4>{side_label} — {len(td["lands"])} lands</h4>')
            h.append(f'<div class="board">')
            for c in td['creatures']:
                sick = ' <span class="sick">(sick)</span>' if c['sick'] else ''
                h.append(f'<span class="creature-badge">{html.escape(c["name"])}<span class="pt">{c["power"]}/{c["toughness"]}</span>{sick}</span>')
            if not td['creatures']:
                h.append(f'<span style="color:#484f58;font-size:0.8em">no creatures</span>')
            h.append(f'</div>')
            h.append(f'<div class="land-list" style="margin-top:4px">{", ".join(html.escape(l) for l in td["lands"]) if td["lands"] else "none"}</div>')
            if td.get('artifacts'):
                h.append(f'<div class="perm-list art-list" style="margin-top:4px">⚙️ {", ".join(html.escape(a) for a in td["artifacts"])}</div>')
            if td.get('enchantments'):
                h.append(f'<div class="perm-list ench-list" style="margin-top:4px">✨ {", ".join(html.escape(e) for e in td["enchantments"])}</div>')
            if td.get('planeswalkers'):
                h.append(f'<div class="perm-list pw-list" style="margin-top:4px">🔮 {", ".join(html.escape(p) for p in td["planeswalkers"])}</div>')
            if td.get('graveyard'):
                gy = td["graveyard"]
                gy_display = ", ".join(html.escape(c) for c in gy[:8])
                if len(gy) > 8: gy_display += f" (+{len(gy)-8} more)"
                h.append(f'<div class="perm-list gy-list" style="margin-top:4px">🪦 {gy_display}</div>')
            h.append(f'</div>')
            # Opponent side
            h.append(f'<div class="board-side {opp_cls}">')
            h.append(f'<h4>{opp_label} — {len(td["opp_lands"])} lands</h4>')
            h.append(f'<div class="board">')
            for c in td.get('opp_creatures', []):
                sick = ' <span class="sick">(sick)</span>' if c['sick'] else ''
                h.append(f'<span class="creature-badge">{html.escape(c["name"])}<span class="pt">{c["power"]}/{c["toughness"]}</span>{sick}</span>')
            if not td.get('opp_creatures', []):
                h.append(f'<span style="color:#484f58;font-size:0.8em">no creatures</span>')
            h.append(f'</div>')
            h.append(f'<div class="land-list" style="margin-top:4px">{", ".join(html.escape(l) for l in td.get("opp_lands", [])) if td.get("opp_lands") else "none"}</div>')
            if td.get('opp_artifacts'):
                h.append(f'<div class="perm-list art-list" style="margin-top:4px">⚙️ {", ".join(html.escape(a) for a in td["opp_artifacts"])}</div>')
            if td.get('opp_enchantments'):
                h.append(f'<div class="perm-list ench-list" style="margin-top:4px">✨ {", ".join(html.escape(e) for e in td["opp_enchantments"])}</div>')
            if td.get('opp_planeswalkers'):
                h.append(f'<div class="perm-list pw-list" style="margin-top:4px">🔮 {", ".join(html.escape(p) for p in td["opp_planeswalkers"])}</div>')
            if td.get('opp_graveyard'):
                gy = td["opp_graveyard"]
                gy_display = ", ".join(html.escape(c) for c in gy[:8])
                if len(gy) > 8: gy_display += f" (+{len(gy)-8} more)"
                h.append(f'<div class="perm-list gy-list" style="margin-top:4px">🪦 {gy_display}</div>')
            h.append(f'</div>')
            h.append(f'</div>')  # board-grid
            h.append(f'</div></div>')

        # Game result
        wcls = 'bug-win' if g['winner'] != 'OPP' else 'opp-win'
        h.append(f'<div class="result">')
        h.append(f'<h2 class="{wcls}">{g["winner"]} WINS</h2>')
        h.append(f'<div class="reason">{html.escape(g["win_reason"])}</div>')
        h.append(f'<div class="stats">Final life: {pro_label} {g["bug_life"]} | OPP {g["opp_life"]} &nbsp;|&nbsp; Length: T{g["display_turn"]}</div>')
        for side, board in [(pro_label, g['bug_board']), ('OPP', g['opp_board'])]:
            if board:
                h.append(f'<div class="stats" style="margin-top:6px">{side}: ')
                for c in board:
                    h.append(f'<span class="creature-badge">{html.escape(c["name"])}<span class="pt">{c["power"]}/{c["toughness"]}</span></span> ')
                h.append(f'</div>')
        h.append(f'</div>')
        h.append(f'</div>')  # game-panel

    # JS
    h.append("""
<script>
function toggle(el) { el.classList.toggle('open'); }
function expandAll() { document.querySelectorAll('.game-panel.active .turn').forEach(t => t.classList.add('open')); }
function collapseAll() { document.querySelectorAll('.game-panel.active .turn').forEach(t => t.classList.remove('open')); }
function toggleReasoning() {
  document.body.classList.toggle('show-reasoning');
  try { localStorage.setItem('mtg_show_reasoning', document.body.classList.contains('show-reasoning') ? '1' : '0'); } catch(e) {}
}
// Restore reasoning-toggle state from last session
try { if (localStorage.getItem('mtg_show_reasoning') === '1') document.body.classList.add('show-reasoning'); } catch(e) {}
function showGame(idx) {
  document.querySelectorAll('.game-tab').forEach((t,i) => t.classList.toggle('active', i===idx));
  document.querySelectorAll('.game-panel').forEach((p,i) => p.classList.toggle('active', i===idx));
}
document.addEventListener('keydown', e => {
  const active = document.querySelector('.game-panel.active');
  if (!active) return;
  const turns = active.querySelectorAll('.turn');
  let cur = [...turns].findIndex(t => t.classList.contains('active'));
  if (e.key === 'ArrowDown') { e.preventDefault(); if(cur<turns.length-1){turns.forEach(t=>t.classList.remove('active'));turns[cur+1].classList.add('active');turns[cur+1].scrollIntoView({behavior:'smooth',block:'center'});} }
  else if (e.key === 'ArrowUp') { e.preventDefault(); if(cur>0){turns.forEach(t=>t.classList.remove('active'));turns[cur-1].classList.add('active');turns[cur-1].scrollIntoView({behavior:'smooth',block:'center'});} }
  else if (e.key === 'Enter' && cur>=0) { e.preventDefault(); toggle(turns[cur]); }
  else if (e.key === 'r' || e.key === 'R') { e.preventDefault(); toggleReasoning(); }
});
</script>
</body></html>""")

    return '\n'.join(h)


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'

    # Parse --pro protagonist (default: bug)
    protagonist = 'bug'
    if '--pro' in sys.argv:
        idx = sys.argv.index('--pro')
        protagonist = sys.argv[idx + 1]
        # Remove --pro and its value from argv so seed parsing works
        sys.argv = sys.argv[:idx] + sys.argv[idx+2:]

    # Parse seeds: single seed, or --bo3 seed1 seed2 seed3
    if '--bo3' in sys.argv:
        idx = sys.argv.index('--bo3')
        seeds = [int(s) for s in sys.argv[idx+1:idx+4]]
        html_content = generate_html(matchup, seeds, protagonist=protagonist)
    elif len(sys.argv) > 2 and sys.argv[2] != '--bo3':
        html_content = generate_html(matchup, int(sys.argv[2]), protagonist=protagonist)
    else:
        html_content = generate_html(matchup, None, protagonist=protagonist)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'game_replay.html')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(html_content)
    print(f"Game replay written to: {out_path}")
