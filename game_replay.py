"""
game_replay.py — Generate interactive HTML game replay.

Usage: python3 game_replay.py [matchup] [seed]
  e.g. python3 game_replay.py sneak_a 2
"""

import sys, random, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    """Classify a play line into a visual category."""
    lo = line.lower()
    if lo.startswith('draw:') or 'upkeep draw' in lo: return 'draw'
    if lo.startswith('land:') or lo.startswith('play ') or lo.startswith('play+crack'): return 'land'
    if 'attack:' in lo or 'attacks for' in lo or 'unblocked' in lo or 'blocks' in lo: return 'combat'
    if 'counter' in lo or 'daze' in lo and 'counter' in lo or 'fow' in lo and 'counter' in lo: return 'interact'
    if 'thoughtseize' in lo or 'strips' in lo: return 'discard'
    if 'kills' in lo or 'push' in lo and '→' in lo or 'snuff' in lo or 'bolt' in lo: return 'removal'
    if '★' in line or 'combo' in lo: return 'combo'
    if 'cast ' in lo or 'flash ' in lo: return 'spell'
    if 'bowmasters t' in lo or 'orc army' in lo or 'ping' in lo: return 'trigger'
    if 'brainstorm' in lo or 'ponder' in lo or 'stock' in lo: return 'cantrip'
    if 'wasteland' in lo and 'destroys' in lo: return 'interact'
    if 'petal' in lo or 'mox' in lo or 'ritual' in lo: return 'mana'
    return 'other'


def run_one_game(matchup, seed=None):
    """Run a single game and return structured data."""
    if seed is not None: random.seed(seed)

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

    turns_data = []
    display_turn = 0
    life_bug = [20]
    life_opp = [20]

    for rnd in range(1, 16):
        if gs.game_over: break
        gs.turn = rnd

        def do_one(label):
            nonlocal display_turn
            display_turn += 1
            player = gs.bug if label == 'BUG' else gs.opp
            opponent = gs.opp if label == 'BUG' else gs.bug
            hand_before = fmt_hand(player)
            life_before = player.life

            if label == 'BUG':
                raw = bug_turn(gs, rnd)
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

            td = {
                'num': display_turn, 'label': label,
                'life': player.life, 'life_before': life_before,
                'opp_life': opponent.life,
                'hand_before': hand_before,
                'hand_after': fmt_hand(player),
                'creatures': fmt_creatures(player),
                'opp_creatures': fmt_creatures(opponent),
                'lands': fmt_lands(player),
                'opp_lands': fmt_lands(opponent),
                'plays': plays,
            }
            turns_data.append(td)
            life_bug.append(gs.bug.life)
            life_opp.append(gs.opp.life)
            return gs.game_over

        if bug_goes_first:
            if do_one('BUG'): break
            if do_one('OPP'): break
        else:
            if do_one('OPP'): break
            if do_one('BUG'): break

    winner = 'BUG' if gs.winner == 'bug' else 'OPP'
    win_reason = gs.win_reason or ''

    return {
        'matchup': matchup, 'meta_name': meta_name, 'seed': seed,
        'bug_goes_first': bug_goes_first,
        'bug_mulls': bug_mulls, 'opp_mulls': opp_mulls,
        'bug_open': bug_open, 'opp_open': opp_open,
        'turns_data': turns_data, 'life_bug': life_bug, 'life_opp': life_opp,
        'display_turn': display_turn, 'winner': winner, 'win_reason': win_reason,
        'bug_life': gs.bug.life, 'opp_life': gs.opp.life,
        'bug_board': fmt_creatures(gs.bug), 'opp_board': fmt_creatures(gs.opp),
    }


def generate_html(matchup, seeds):
    """Generate HTML for one or more games (Bo1 or Bo3)."""
    if isinstance(seeds, (int, type(None))):
        seeds = [seeds]

    games = [run_one_game(matchup, s) for s in seeds]
    meta_name = games[0]['meta_name']
    is_bo3 = len(games) > 1

    bug_wins = sum(1 for g in games if g['winner'] == 'BUG')
    opp_wins = sum(1 for g in games if g['winner'] == 'OPP')
    series_winner = 'BUG' if bug_wins > opp_wins else 'OPP'

    # Build HTML
    h = []
    title = f'Bo{len(games)} Replay: BUG vs {html.escape(meta_name)}' if is_bo3 else f'Game Replay: BUG vs {html.escape(meta_name)}'
    h.append(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',system-ui,sans-serif;padding:20px;max-width:900px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#161b22,#1c2333);border:1px solid #30363d;border-radius:12px;padding:24px;margin-bottom:20px}}
.header h1{{font-size:1.6em;margin-bottom:8px;color:#f0f6fc}}
.header h1 .vs{{color:#666}}
.header .bug-name{{color:#58a6ff}}
.header .opp-name{{color:#f85149}}
.header .meta{{color:#8b949e;font-size:0.9em;margin-top:4px}}
.series-score{{font-size:1.3em;margin-top:8px;font-weight:700}}
.series-score .bug-s{{color:#58a6ff}}.series-score .opp-s{{color:#f85149}}
.game-tabs{{display:flex;gap:4px;margin-bottom:16px}}
.game-tab{{background:#21262d;color:#8b949e;border:1px solid #30363d;border-radius:8px 8px 0 0;padding:10px 20px;cursor:pointer;font-weight:600;font-size:0.95em}}
.game-tab:hover{{background:#30363d}}
.game-tab.active{{background:#161b22;color:#f0f6fc;border-bottom-color:#161b22}}
.game-tab .winner-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:6px}}
.game-tab .winner-dot.bug{{background:#58a6ff}}.game-tab .winner-dot.opp{{background:#f85149}}
.game-panel{{display:none}}.game-panel.active{{display:block}}
.hands{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}}
.hand-box{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px}}
.hand-box h3{{font-size:0.85em;color:#8b949e;margin-bottom:8px}}
.hand-box.bug{{border-left:3px solid #58a6ff}}.hand-box.opp{{border-left:3px solid #f85149}}
.pill{{display:inline-block;background:#21262d;border:1px solid #30363d;border-radius:12px;padding:2px 10px;margin:2px;font-size:0.8em;font-family:'Fira Code','Consolas',monospace;color:#e3b341}}
.controls{{display:flex;gap:8px;margin-bottom:16px}}
.controls button{{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:0.85em}}
.controls button:hover{{background:#30363d}}
.life-chart{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:20px}}
.life-chart h3{{font-size:0.85em;color:#8b949e;margin-bottom:12px}}
.life-chart svg{{width:100%;height:80px}}
.turn{{background:#161b22;border:1px solid #30363d;border-radius:8px;margin-bottom:8px;overflow:hidden;transition:all 0.2s}}
.turn.bug{{border-left:3px solid #58a6ff}}.turn.opp{{border-left:3px solid #f85149}}
.turn.active{{border-color:#e3b341}}
.turn-header{{padding:12px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none}}
.turn-header:hover{{background:#1c2333}}
.turn-header .left{{display:flex;align-items:center;gap:12px}}
.turn-header .tnum{{font-weight:700;font-size:1.1em;min-width:36px}}
.turn-header .tnum.bug{{color:#58a6ff}}.turn-header .tnum.opp{{color:#f85149}}
.turn-header .player{{font-weight:600;font-size:0.9em;padding:2px 8px;border-radius:4px}}
.turn-header .player.bug{{background:#0d2847;color:#58a6ff}}.turn-header .player.opp{{background:#3d1418;color:#f85149}}
.turn-header .life{{font-size:0.9em;color:#8b949e}}
.turn-header .life b{{color:#f0f6fc}}
.turn-header .arrow{{color:#484f58;transition:transform 0.2s;font-size:0.8em}}
.turn.open .arrow{{transform:rotate(90deg)}}
.turn-body{{display:none;padding:0 16px 16px;border-top:1px solid #21262d}}
.turn.open .turn-body{{display:block}}
.section-label{{font-size:0.75em;text-transform:uppercase;letter-spacing:1px;color:#484f58;margin:12px 0 6px}}
.hand-pills{{margin-bottom:4px}}
.play{{padding:6px 0;display:flex;gap:8px;align-items:flex-start}}
.play .step{{color:#484f58;font-size:0.85em;min-width:20px;text-align:right;padding-top:1px}}
.play .action{{font-family:'Fira Code','Consolas',monospace;font-size:0.85em;color:#c9d1d9;flex:1}}
.play .action.key{{color:#e3b341;font-weight:600}}
.play .action.counter{{color:#f85149;text-decoration:line-through;opacity:0.7}}
.play .reasoning{{font-size:0.8em;color:#6e7681;font-style:italic;margin-left:4px}}
.play .cat-badge{{font-size:0.65em;text-transform:uppercase;letter-spacing:0.5px;padding:1px 5px;border-radius:3px;font-weight:600;margin-right:4px;font-family:'Segoe UI',system-ui,sans-serif;min-width:50px;text-align:center;display:inline-block}}
.cat-draw{{background:#1a1a2e;color:#8b8bb8}}.cat-land{{background:#0d2611;color:#7ee787}}.cat-combat{{background:#3d1418;color:#f85149}}.cat-interact{{background:#2d1b4e;color:#d2a8ff}}
.cat-discard{{background:#3d2e14;color:#e3b341}}.cat-removal{{background:#3d1418;color:#ff7b72}}.cat-combo{{background:#4a1942;color:#f778ba}}.cat-spell{{background:#0d2847;color:#58a6ff}}
.cat-trigger{{background:#2a2000;color:#d29922}}.cat-cantrip{{background:#0a2540;color:#79c0ff}}.cat-mana{{background:#1a2e1a;color:#56d364}}.cat-other{{background:#1c1c1c;color:#6e7681}}
.board-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px}}
.board-side{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:8px 10px}}
.board-side h4{{font-size:0.7em;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;font-weight:600}}
.board-side.bug h4{{color:#58a6ff}}.board-side.opp h4{{color:#f85149}}
.combat-detail{{background:#1a0a0a;border:1px solid #3d1418;border-radius:6px;padding:8px 12px;margin:4px 0;font-family:'Fira Code','Consolas',monospace;font-size:0.82em}}
.combat-detail .atk-line{{color:#e3b341;margin-bottom:2px}}.combat-detail .blk-line{{color:#d2a8ff;margin-bottom:2px}}
.combat-detail .dmg-line{{color:#f85149;font-weight:600}}.combat-detail .death-line{{color:#f85149;opacity:0.8;font-style:italic}}
.board{{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}}
.creature-badge{{background:#0d2847;border:1px solid #1f3d5c;border-radius:6px;padding:4px 10px;font-family:'Fira Code','Consolas',monospace;font-size:0.8em;color:#58a6ff}}
.creature-badge .pt{{color:#e3b341;font-weight:700;margin-left:4px}}
.creature-badge .sick{{color:#f85149;font-size:0.7em}}
.land-list{{font-family:'Fira Code','Consolas',monospace;font-size:0.8em;color:#7ee787}}
.result{{background:linear-gradient(135deg,#161b22,#1c2333);border:2px solid #30363d;border-radius:12px;padding:24px;text-align:center;margin-top:20px}}
.result h2{{font-size:1.8em;margin-bottom:8px}}
.result h2.bug-win{{color:#58a6ff}}.result h2.opp-win{{color:#f85149}}
.result .reason{{color:#8b949e;font-size:1em;margin-bottom:12px}}
.result .stats{{color:#6e7681;font-size:0.9em}}
.kbd{{font-size:0.75em;color:#6e7681;margin-left:auto}}
</style></head><body>
""")

    # Header
    h.append(f'<div class="header">')
    h.append(f'<h1><span class="bug-name">BUG Tempo</span> <span class="vs">vs</span> <span class="opp-name">{html.escape(meta_name)}</span></h1>')
    if is_bo3:
        h.append(f'<div class="series-score"><span class="bug-s">BUG {bug_wins}</span> — <span class="opp-s">{opp_wins} OPP</span></div>')
        sw_cls = 'bug-name' if series_winner == 'BUG' else 'opp-name'
        h.append(f'<div class="meta"><span class="{sw_cls}">{series_winner} wins the series</span></div>')
    h.append(f'</div>')

    # Game tabs (if Bo3)
    if is_bo3:
        h.append(f'<div class="game-tabs">')
        for gi, g in enumerate(games):
            act = ' active' if gi == 0 else ''
            dot_cls = 'bug' if g['winner'] == 'BUG' else 'opp'
            h.append(f'<div class="game-tab{act}" onclick="showGame({gi})">Game {gi+1}<span class="winner-dot {dot_cls}"></span></div>')
        h.append(f'</div>')

    # Each game panel
    for gi, g in enumerate(games):
        act = ' active' if gi == 0 else ''
        h.append(f'<div class="game-panel{act}" id="game-{gi}">')

        # Opening hands
        play_str = 'ON THE PLAY' if g['bug_goes_first'] else 'ON THE DRAW'
        h.append(f'<div class="meta" style="margin-bottom:12px;color:#8b949e">BUG is {play_str} &nbsp;|&nbsp; Seed: {g["seed"]}</div>')
        h.append(f'<div class="hands">')
        h.append(f'<div class="hand-box bug"><h3>BUG opening (mull {g["bug_mulls"]})</h3>')
        for c in g['bug_open']: h.append(f'<span class="pill">{html.escape(c)}</span>')
        h.append(f'</div><div class="hand-box opp"><h3>OPP opening (mull {g["opp_mulls"]})</h3>')
        for c in g['opp_open']: h.append(f'<span class="pill">{html.escape(c)}</span>')
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
                h.append(f'<line x1="{px}" y1="{pby}" x2="{x}" y2="{by}" stroke="#58a6ff" stroke-width="2"/>')
                h.append(f'<line x1="{px}" y1="{poy}" x2="{x}" y2="{oy}" stroke="#f85149" stroke-width="2"/>')
            h.append(f'<circle cx="{x}" cy="{by}" r="3" fill="#58a6ff"/>')
            h.append(f'<circle cx="{x}" cy="{oy}" r="3" fill="#f85149"/>')
            h.append(f'<text x="{x}" y="{by-6}" text-anchor="middle" fill="#58a6ff" font-size="9">{lb[i]}</text>')
            h.append(f'<text x="{x}" y="{oy+12}" text-anchor="middle" fill="#f85149" font-size="9">{lo[i]}</text>')
        h.append(f'</svg></div>')

        # Controls
        h.append(f'<div class="controls">')
        h.append(f'<button onclick="expandAll()">Expand All</button>')
        h.append(f'<button onclick="collapseAll()">Collapse All</button>')
        h.append(f'<span class="kbd">↑↓ navigate &nbsp; Enter: toggle</span>')
        h.append(f'</div>')

        # Turns
        for i, td in enumerate(g['turns_data']):
            label = td['label']
            cls = label.lower()
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
            if n_combat: summary_parts.append(f'<span style="color:#f85149;font-size:0.75em">⚔{n_combat}</span>')
            if n_spells: summary_parts.append(f'<span style="color:#58a6ff;font-size:0.75em">🃏{n_spells}</span>')
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
                cat_label = {'draw':'DRAW','land':'LAND','combat':'COMBAT','interact':'COUNTER',
                             'discard':'DISCARD','removal':'REMOVE','combo':'COMBO','spell':'CAST',
                             'trigger':'TRIGGER','cantrip':'DIG','mana':'MANA','other':''}.get(cat,'')
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

            # Enhanced board: show BOTH sides
            h.append(f'<div class="section-label">Board State</div>')
            h.append(f'<div class="board-grid">')
            # Player side
            side_label = td['label']
            opp_label = 'OPP' if side_label == 'BUG' else 'BUG'
            h.append(f'<div class="board-side {side_label.lower()}">')
            h.append(f'<h4>{side_label} — {len(td["lands"])} lands</h4>')
            h.append(f'<div class="board">')
            for c in td['creatures']:
                sick = ' <span class="sick">(sick)</span>' if c['sick'] else ''
                h.append(f'<span class="creature-badge">{html.escape(c["name"])}<span class="pt">{c["power"]}/{c["toughness"]}</span>{sick}</span>')
            if not td['creatures']:
                h.append(f'<span style="color:#484f58;font-size:0.8em">no creatures</span>')
            h.append(f'</div>')
            h.append(f'<div class="land-list" style="margin-top:4px">{", ".join(html.escape(l) for l in td["lands"]) if td["lands"] else "none"}</div>')
            h.append(f'</div>')
            # Opponent side
            h.append(f'<div class="board-side {"opp" if side_label == "BUG" else "bug"}">')
            h.append(f'<h4>{opp_label} — {len(td["opp_lands"])} lands</h4>')
            h.append(f'<div class="board">')
            for c in td.get('opp_creatures', []):
                sick = ' <span class="sick">(sick)</span>' if c['sick'] else ''
                h.append(f'<span class="creature-badge">{html.escape(c["name"])}<span class="pt">{c["power"]}/{c["toughness"]}</span>{sick}</span>')
            if not td.get('opp_creatures', []):
                h.append(f'<span style="color:#484f58;font-size:0.8em">no creatures</span>')
            h.append(f'</div>')
            h.append(f'<div class="land-list" style="margin-top:4px">{", ".join(html.escape(l) for l in td.get("opp_lands", [])) if td.get("opp_lands") else "none"}</div>')
            h.append(f'</div>')
            h.append(f'</div>')  # board-grid
            h.append(f'</div></div>')

        # Game result
        wcls = 'bug-win' if g['winner'] == 'BUG' else 'opp-win'
        h.append(f'<div class="result">')
        h.append(f'<h2 class="{wcls}">{g["winner"]} WINS</h2>')
        h.append(f'<div class="reason">{html.escape(g["win_reason"])}</div>')
        h.append(f'<div class="stats">Final life: BUG {g["bug_life"]} | OPP {g["opp_life"]} &nbsp;|&nbsp; Length: T{g["display_turn"]}</div>')
        for side, board in [('BUG', g['bug_board']), ('OPP', g['opp_board'])]:
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
});
</script>
</body></html>""")

    return '\n'.join(h)


if __name__ == '__main__':
    matchup = sys.argv[1] if len(sys.argv) > 1 else 'sneak_a'

    # Parse seeds: single seed, or --bo3 seed1 seed2 seed3
    if '--bo3' in sys.argv:
        idx = sys.argv.index('--bo3')
        seeds = [int(s) for s in sys.argv[idx+1:idx+4]]
        html_content = generate_html(matchup, seeds)
    elif len(sys.argv) > 2 and sys.argv[2] != '--bo3':
        html_content = generate_html(matchup, int(sys.argv[2]))
    else:
        html_content = generate_html(matchup, None)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'game_replay.html')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        f.write(html_content)
    print(f"Game replay written to: {out_path}")
