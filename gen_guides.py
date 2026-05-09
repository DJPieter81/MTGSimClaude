#!/usr/bin/env python3
"""Generate full-featured deck guides for all decks in MTGSimClaude.

Env overrides:
    MTGSIM_META       path to meta_fresh.json  (default: ./meta_fresh.json,
                      fallback: /home/claude/meta_fresh.json for legacy)
    MTGSIM_AGG        path to deck_agg.json    (default: ./deck_agg.json,
                      fallback: /home/claude/deck_agg.json for legacy)
    MTGSIM_OUT_DIR    directory to write guide_*.html
                      (default: ./guides, fallback: /mnt/user-data/outputs)

Regenerate the meta inputs from a fresh matrix with:
    python3 build_meta_inputs.py
"""
import json, random, os, sys
from collections import Counter, defaultdict

# Support both the original /home/claude/... env and local checkouts.
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.exists('/home/claude/MTGSimClaude') and _HERE != '/home/claude/MTGSimClaude':
    sys.path.insert(0, '/home/claude/MTGSimClaude')
sys.path.insert(0, _HERE)

from sim import run_game
from cards import DECKS


def _resolve(path_candidates):
    for p in path_candidates:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"None of the candidate paths exist: {path_candidates}")


META_PATH = os.environ.get('MTGSIM_META') or _resolve([
    os.path.join(_HERE, 'meta_fresh.json'),
    '/home/claude/meta_fresh.json',
])
AGG_PATH = os.environ.get('MTGSIM_AGG') or _resolve([
    os.path.join(_HERE, 'deck_agg.json'),
    '/home/claude/deck_agg.json',
])
OUT_DIR = os.environ.get('MTGSIM_OUT_DIR') or os.path.join(_HERE, 'guides')
os.makedirs(OUT_DIR, exist_ok=True)

with open(META_PATH) as f: meta = json.load(f)
with open(AGG_PATH) as f: agg = json.load(f)
A=meta['a'];W=meta['w'];M=meta['m'];decks=meta['d']

# Optional: card-level data (for Stars of the Sim + What Kills You sections).
# Graceful fallback to empty dict if missing so guides still generate.
_CARD_PATH = os.path.join(_HERE, 'card_trimmed.json')
CARD_DATA = {}
if os.path.exists(_CARD_PATH):
    try:
        with open(_CARD_PATH) as f: CARD_DATA = json.load(f)
    except Exception as e:
        print(f"warn: failed to load card_trimmed.json: {e}", flush=True)

# Optional: latest Bo3 matrix (for G1 → Match Swing section).
# Picks newest matrix_bo3_*.json by filename sort.
_BO3 = {}
_bo3_files = sorted([f for f in os.listdir(os.path.join(_HERE, 'results'))
                     if f.startswith('matrix_bo3_') and f.endswith('.json')]) \
             if os.path.isdir(os.path.join(_HERE, 'results')) else []
if _bo3_files:
    try:
        with open(os.path.join(_HERE, 'results', _bo3_files[-1])) as f:
            _bo3raw = json.load(f)
        # Normalize _vs_ keys to | and store [match_wr_pct, game_wr_pct]
        for k, v in _bo3raw.get('matchups', {}).items():
            nk = k.replace('_vs_', '|')
            if isinstance(v, list) and len(v) >= 2:
                _BO3[nk] = [round(v[0]*100, 1), round(v[1]*100, 1)]
        print(f"loaded bo3 matrix: {_bo3_files[-1]} ({len(_BO3)} matchups)", flush=True)
    except Exception as e:
        print(f"warn: failed to load bo3 matrix: {e}", flush=True)

def muc(w): return '#1f7040' if w>=65 else '#854f0b' if w>=45 else '#b02020'

def assign_role(card):
    n=card.name.lower(); t=(getattr(card,'tag','') or '').lower()
    is_land=card.is_land(); is_cre=hasattr(card,'power') and card.power is not None
    if any(x in n for x in ['force of will','daze','flusterstorm','counterspell','spell pierce']): return 'protect','counter'
    if 'veil' in n: return 'protect','anti-blue'
    if any(x in n for x in ['thoughtseize','unmask','grief','cabal therapy','duress']): return 'hate','discard'
    if any(x in n for x in ['chalice','trinisphere']): return 'hate','lock'
    if 'wasteland' in n: return 'hate','mana denial'
    if any(x in n for x in ['reanimate','animate dead','exhume','entomb','dread return']): return 'kill','combo'
    if any(x in n for x in ['show and tell','sneak attack','omniscience']): return 'kill','cheat'
    if 'dark depths' in n or "thespian" in n: return 'kill','combo'
    if any(x in n for x in ['charbelcher','grindstone','tendrils']): return 'kill','combo'
    if 'oracle' in n and 'thassa' in n: return 'kill','combo'
    if any(x in n for x in ['craterhoof','natural order']): return 'kill','finisher'
    if any(x in n for x in ['emrakul','griselbrand','atraxa','archon']): return 'kill','finisher'
    if is_cre:
        if getattr(card,'haste',False): return 'threat','haste'
        if (card.power or 0)>=4: return 'threat','beater'
        if any(x in n for x in ['bowmasters','channeler','delver','guide','swiftspear']): return 'threat',''
        if any(x in n for x in ['stoneforge','recruiter','lackey','heritage']): return 'engine','tutor'
        if any(x in n for x in ['thalia','eidolon','containment','ethersworn']): return 'engine','tax'
        return 'threat',''
    if any(x in n for x in ['lotus petal','chrome mox','mox opal','mox diamond','lion','dark ritual','cabal ritual','rite of flame','seething','simian','elvish spirit','desperate','tinder']): return 'enabler','fast mana'
    if any(x in n for x in ['brainstorm','ponder','preordain','stock up','gitaxian','thoughtcast','expressive iteration','thought monitor']): return 'draw','cantrip'
    if any(x in n for x in ['lightning bolt','chain lightning','lava spike','rift bolt','fireblast','price of progress','searing']): return 'burn','dmg'
    if 'skullcrack' in n: return 'reach','anti-lifegain'
    if any(x in n for x in ['swords to plowshares','push','unholy heat','prismatic ending','dismember']): return 'removal',''
    if any(x in n for x in ['invigorate','berserk','vines','mutagenic','become immense','scale up']): return 'reach','pump'
    if any(x in n for x in ['crop rotation',"green sun",'once upon','land grant','burning wish','infernal tutor']): return 'draw','tutor'
    if 'vial' in n: return 'engine','cheat'
    if is_land:
        if any(x in n for x in ['tomb','city of traitors']): return 'enabler','sol land'
        if any(x in n for x in ['cavern','saga','karakas','boseiju','otawara']): return 'flex','utility'
        return 'flex','land'
    return 'flex',''

badge_map={'threat':'b-threat','burn':'b-burn','reach':'b-reach','engine':'b-engine','kill':'b-kill','enabler':'b-enabler','removal':'b-removal','draw':'b-draw','protect':'b-protect','hate':'b-hate','flex':'b-flex'}

JS_HOVER = '<script>\ndocument.addEventListener("DOMContentLoaded",function(){var p=document.createElement("div");p.id="card-popup";p.innerHTML=\'<img id="card-img">\';document.body.appendChild(p);var img=document.getElementById("card-img"),cache={};document.addEventListener("mouseover",function(e){var el=e.target.closest(".card-tip");if(!el)return;var n=el.dataset.card;if(!n)return;var u="https://api.scryfall.com/cards/named?fuzzy="+encodeURIComponent(n)+"&format=image&version=normal";img.src=cache[n]||u;if(!cache[n])cache[n]=u;p.style.display="block"});document.addEventListener("mouseout",function(e){if(e.target.closest(".card-tip"))p.style.display="none"});document.addEventListener("mousemove",function(e){if(p.style.display==="block"){p.style.left=Math.min(e.clientX+16,innerWidth-260)+"px";p.style.top=Math.max(8,Math.min(e.clientY-170,innerHeight-350))+"px"}})});\n</script>'


# ------------------------------------------------------------------
# Card aggregation helpers (Stars of the Sim, What Kills You)
# ------------------------------------------------------------------
# CARD_DATA keys: "<deck>|<opp>", values: {f, c1, c2, a1, a2} where
# each is a list of [card_name, count]. "f" in key "X|Y" is X's
# finishing cards (when X won). c1/a1 = X's casts/attackers;
# c2/a2 = Y's (the opponent's).
#
# Tokens and sim-bookkeeping strings like "Unknown" should be filtered
# before displaying — Scryfall can't resolve them.
_TOKEN_NAMES = {
    'unknown', 'construct', 'monk token', 'orc army', 'elvish spirit guide',
    'simian spirit guide', 'eldrazi spawn', 'karn construct', 'karnstruct',
    'marit lage', 'endurance', 'poison (infect)', 'goblin charbelcher',
    'dragon\'s rage channeler', 'griselbrand', 'archon of cruelty',
    'grindstone', 'librarian', 'nimble pilferer', 'inquisitive student',
    'bane of nightmares', 'guardian of thraben', 'lurker of the loch',
    'the aeons torn', 'grand unifier', 'master thopterist', 'exuberant shepherd',
    'the ceaseless hunger', 'arisen nightmare',  # paired-name fragments
}
# Sim log strings (not real cards)
_SIM_LOGS_PREFIXES = ('Hand dump', 'P1 Force', 'OPP Force', 'Cast ', 'Play ',
                      'Flash ', 'OPP Bow', '-> ', 'Stage copies', 'Marit Lage attacks',
                      'Dark Depths combo', 'No Borrower', 'Lackey trigger', 'Mentor trigger',
                      'Rishadan Port taps', 'Urza\'s Saga', 'Street Wraith cycles',
                      'Edge of Autumn cycles', 'Combo (', 'Inkmoth Nexus', 'LETHAL',
                      'Storm Ad Nauseam', 'Storm Past', 'Storm Tendrils',
                      'Oops resolves', 'Once Upon', 'Muxus from', 'Fury evoke',
                      'Brazen Borrower bounces', 'Grief ETB', 'Emrakul, the Aeons Torn attacks',
                      'Show and Tell ->')

def _is_real_card(name):
    """Filter out tokens, sim-log strings, and noise from card lists."""
    if not name: return False
    nl = name.lower().strip()
    if nl in _TOKEN_NAMES: return False
    if name.startswith(_SIM_LOGS_PREFIXES): return False
    if 'attacks!' in name or 'cycles' in name.lower() or 'triggers' in name.lower(): return False
    if name == 'Vial' or name == 'Petal': return False  # fragments of Aether Vial / Lotus Petal
    if name == 'SSG' or name == 'Tendrils': return False
    return True

def aggregate_stars(deck):
    """Aggregate deck's own cards across all matchups it played in.
    Returns {finishers, casts, attackers} where each is sorted [(card, count)]."""
    fin = Counter(); cas = Counter(); att = Counter()
    prefix = deck + '|'
    for k, v in CARD_DATA.items():
        if not k.startswith(prefix): continue
        for name, cnt in v.get('f', []):
            if _is_real_card(name): fin[name] += cnt
        for name, cnt in v.get('c1', []):
            if _is_real_card(name): cas[name] += cnt
        for name, cnt in v.get('a1', []):
            if _is_real_card(name): att[name] += cnt
    return {
        'finishers': fin.most_common(10),
        'casts': cas.most_common(10),
        'attackers': att.most_common(10),
    }

def aggregate_what_kills(deck):
    """Aggregate opponent finishers that closed games vs this deck.
    Returns sorted [(card, count)] from opponent side."""
    kill = Counter()
    suffix = '|' + deck
    for k, v in CARD_DATA.items():
        if not k.endswith(suffix): continue
        # In key "Y|deck", f is Y's finishers when Y won → what killed this deck.
        for name, cnt in v.get('f', []):
            if _is_real_card(name): kill[name] += cnt
    return kill.most_common(10)

def compute_bo3_swings(deck):
    """For each matchup, compute Bo3 match_wr - Bo1 wr.
    Returns list of (opp, bo1_wr, bo3_match_wr, swing) sorted by |swing|."""
    out = []
    for opp in decks:
        if opp == deck: continue
        bo1 = M.get(deck + '|' + opp, [None])[0]
        bo3 = _BO3.get(deck + '|' + opp, [None, None])[0]
        if bo1 is None or bo3 is None: continue
        swing = round(bo3 - bo1, 1)
        out.append((opp, bo1, bo3, swing))
    out.sort(key=lambda x: -abs(x[3]))
    return out

# Run sim data collection
print("Collecting sim data for all decks...", flush=True)
random.seed(2026)

# Parallelise per-deck data collection. Each deck's 2,000 games are
# independent so we fan out one task per deck across a process pool.
# The worker (in parallel.py) does exactly what the previous inline
# loop did and returns a dict matching the all_data[dk] schema.
# `decks` (from meta_fresh.json) is the opponent pool; `DECKS.keys()`
# is the set we collect data for. They overlap heavily but aren't
# identical so we pass both explicitly.
from parallel import parallel_gen_guides
all_data = parallel_gen_guides(sorted(DECKS.keys()),
                               opp_pool=decks,
                               n_games=2000,
                               seed=2026)

print(f"\nGenerating HTML guides...", flush=True)

# Hand-crafted guides opt out of regeneration by including the sentinel
# <!-- HAND-CRAFTED: do not regenerate --> near the top. Burn is always
# skipped (its full hand-craft lives in templates/reference_deck_guide.html).
_HANDCRAFT_SENTINEL = '<!-- HAND-CRAFTED: do not regenerate -->'

def _is_handcrafted(guide_path):
    try:
        with open(guide_path) as _f:
            return _HANDCRAFT_SENTINEL in _f.read(2048)
    except FileNotFoundError:
        return False


# ------------------------------------------------------------------
# Pure section builders — each returns a complete HTML fragment
# (wrapper + content) given the subject deck key `i`, a data context
# `D` with keys {'decks', 'A', 'W', 'M'}, and the archetype map `arch`.
# These mirror the section_* architecture in MTGSimManu's build_guide.py
# so blocks can be lifted across repos without modification.
# ------------------------------------------------------------------

def section_archetype_wr(i, D, arch):
    decks, M = D['decks'], D['M']
    ag = {}
    for x in decks:
        if x == i: continue
        a = arch.get(x, {}).get('type', '?')
        if a not in ag: ag[a] = []
        ag[a].append(M.get(i+'|'+x, [50])[0])
    awd = {a: round(sum(v)/len(v), 1) for a, v in ag.items()}
    bars = ''.join(f'<div style="display:flex;align-items:center;gap:6px"><span style="width:60px;text-align:right;font-size:11px;color:#555">{a}</span><div style="flex:1;height:14px;background:#f5f5f5;border-radius:2px;overflow:hidden"><div style="width:{w}%;height:100%;background:{muc(w)};border-radius:2px"></div></div><span style="width:36px;font-weight:700;font-size:11px;text-align:right;color:{muc(w)}">{w:.0f}%</span></div>\n' for a,w in sorted(awd.items(),key=lambda x:-x[1]))
    return '<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">Win Rate by Archetype</div>'+bars+'</div>\n'


def section_tournament_sim(i, D, arch):
    decks, A, M = D['decks'], D['A'], D['M']
    random.seed(42)
    wd = []
    for _ in range(10000):
        w = 0
        for _rd in range(8):
            opps2 = [x for x in decks if x != i]; wts = [max(0.1, A.get(x, 30)) for x in opps2]
            opp = random.choices(opps2, weights=wts, k=1)[0]
            if random.random() < M.get(i+'|'+opp, [50])[0]/100: w += 1
        wd.append(w)
    c2 = Counter(wd); avg = sum(wd)/len(wd); top8 = sum(1 for w in wd if w >= 6)/len(wd)*100
    hist = {w: round(c2[w]/10000*100, 1) for w in range(9)}
    th = ''.join(f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%"><div style="font-size:8px;color:{"#1f7040" if w>=6 else "#854f0b" if w>=4 else "#b02020"}">{hist.get(w,0):.0f}%</div><div style="width:100%;background:{"#1f7040" if hist.get(w,0)==max(hist.get(_i,0) for _i in range(2,9)) else "#d0f0d0" if w>=6 else "#fff0e0" if w>=4 else "#fde8e8"};border-radius:2px 2px 0 0;height:{hist.get(w,0)}%"></div><div style="font-size:8px;color:#aaa">{w}-{8-w}</div></div>\n' for w in range(2,9))
    out = '<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">8-Round Tournament Sim</div>'
    out += '<div style="display:flex;align-items:flex-end;gap:3px;height:80px;margin-bottom:4px">'+th+'</div>'
    out += '<div style="display:flex;justify-content:space-between;margin-top:8px;padding:6px 8px;background:#f0faf0;border-radius:3px"><span style="font-size:11px;color:#555">Avg: <b style="color:#1f7040">'+str(round(avg,1))+'</b></span><span style="font-size:11px;color:#555">Top 8: <b style="color:#1f7040">'+str(round(top8,1))+'%</b></span></div></div>\n'
    return out


def section_tournament_arc(i, D, arch):
    return '<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px;margin:12px 0"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">Tournament Arc</div><div style="display:flex;gap:2px;height:24px;border-radius:3px;overflow:hidden"><div style="flex:3;background:#d0f0d0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#1f7040">R1-3 Bank</div><div style="flex:3;background:#fff0e0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#854f0b">R4-6 Gauntlet</div><div style="flex:2;background:#fde8e8;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#b02020">R7-8 Top</div></div></div>\n'


def section_danger_cards(i, D, arch):
    decks, M = D['decks'], D['M']
    dangers = sorted([(M.get(i+'|'+x, [50])[0], x, arch.get(x, {}).get('type', '?')) for x in decks if x != i and M.get(i+'|'+x, [50])[0] < 50])[:3]
    if not dangers:
        return ''
    out = '<div style="display:grid;grid-template-columns:'+' '.join(['1fr']*len(dangers))+';gap:12px;margin:12px 0">\n'
    for wr, nm, ar in dangers:
        out += '<div style="border:1px solid #e8d0d0;border-radius:6px;overflow:hidden"><div style="background:linear-gradient(135deg,#b02020,#801818);padding:12px 14px;display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:13px;font-weight:700;color:#fff">'+nm+'</div><div style="font-size:9px;color:#ffb0b0;text-transform:uppercase">'+ar+'</div></div><div style="font-size:28px;font-weight:700;color:#fff">'+str(int(wr))+'%</div></div></div>\n'
    out += '</div>\n'
    return out


def section_delta_proof(i, D, arch):
    decks, W = D['decks'], D['W']
    wtd = W.get(i, 50)
    rank = sorted(decks, key=lambda x: -W.get(x, 0)).index(i)+1 if i in decks else 99
    out = '<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px;margin:12px 0">'
    out += f'<div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">Why {i.replace("_"," ").title()} is #{rank} — The Delta Proof</div>'
    out += '<div style="display:flex;flex-direction:column;gap:3px">'
    ref_decks = sorted(decks, key=lambda x: -W.get(x, 0))
    ref_decks = [x for x in ref_decks if x != i][:5] + [x for x in reversed(ref_decks) if x != i][:2]
    for rd in ref_decks:
        rd_wr = round(W.get(rd, 50), 1)
        rd_delta = round(wtd - rd_wr, 1)
        col = '#1f7040' if rd_delta > 0 else '#b02020' if rd_delta < -5 else '#854f0b'
        bar_w = min(100, max(5, rd_wr))
        out += f'<div style="display:flex;align-items:center;gap:6px"><span style="width:70px;font-size:11px;color:#555;text-align:right">{rd.replace("_"," ").title()}</span><div style="flex:1;height:10px;background:#f0f0f0;border-radius:2px;overflow:hidden;max-width:120px"><div style="width:{bar_w}%;height:100%;background:{col};border-radius:2px"></div></div><span style="font-size:11px;font-weight:700;color:{col}">{rd_delta:+.1f}pp</span></div>'
    out += '</div></div>\n'
    return out


def section_tier_triptych(i, D, arch):
    decks, M = D['decks'], D['M']
    prey = len([x for x in decks if x != i and M.get(i+'|'+x, [50])[0] >= 80])
    comp = len([x for x in decks if x != i and 50 <= M.get(i+'|'+x, [50])[0] < 80])
    dng = len([x for x in decks if x != i and M.get(i+'|'+x, [50])[0] < 50])
    out = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0">'
    out += '<div style="border:1px solid #e0e0e0;border-left:3px solid #1f7040;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#1f7040;font-weight:700;margin-bottom:6px">✓ Prey ('+str(prey)+')</div><div style="font-size:22px;font-weight:700;color:#1f7040">80%+</div></div>'
    out += '<div style="border:1px solid #e0e0e0;border-left:3px solid #854f0b;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#854f0b;font-weight:700;margin-bottom:6px">⚖ Competitive ('+str(comp)+')</div><div style="font-size:22px;font-weight:700;color:#854f0b">50-80%</div></div>'
    out += '<div style="border:1px solid #e0e0e0;border-left:3px solid #b02020;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#b02020;font-weight:700;margin-bottom:6px">⚠ Danger ('+str(dng)+')</div><div style="font-size:22px;font-weight:700;color:#b02020">&lt;50%</div></div></div>\n'
    return out


D_CTX = {'decks': decks, 'A': A, 'W': W, 'M': M}

for dk in sorted(DECKS.keys()):
    _guide_fn = os.path.join(OUT_DIR, 'guide_'+dk+'.html')
    d=dk; flat=A.get(d,50); wtd=W.get(d,50); delta=round(wtd-flat,1)
    rank=sorted(decks,key=lambda x:-W.get(x,0)).index(d)+1 if d in decks else 99
    best=max([(M.get(d+'|'+d2,[50])[0],d2) for d2 in decks if d2!=d],default=(50,'?'))
    worst=min([(M.get(d+'|'+d2,[50])[0],d2) for d2 in decks if d2!=d],default=(50,'?'))
    da=agg.get(d,{}); dtype=da.get('type','?'); plan=da.get('plan','')
    tier='T1' if wtd>=58 else 'T2' if wtd>=48 else 'T3' if wtd>=33 else 'T4'
    tier_cls='g' if wtd>=58 else 'a' if wtd>=48 else 'r'
    sd=all_data.get(dk,{})
    colors_map={'tempo':'#0969da','combo':'#9a6700','aggro':'#b02020','control':'#6639ba','midrange':'#5a3e1b','ramp':'#1a7f37','prison':'#555','unknown':'#666'}
    color=colors_map.get(dtype,'#666')
    
    # Decklist
    try: cards_list=DECKS[dk]()
    except: cards_list=[]
    card_data={}
    for c in cards_list:
        role,note=assign_role(c)
        if c.name not in card_data: card_data[c.name]={'count':0,'role':role,'note':note,'is_land':c.is_land()}
        card_data[c.name]['count']+=1
    sorted_cards=sorted(card_data.items(),key=lambda x:(x[1]['is_land'],x[1]['role']=='flex',-x[1]['count']))
    main_html=''.join(f'<div class="card-row"><span class="card-count">{info["count"]}</span><span class="card-name"><span class="card-tip" data-card="{name}">{name}</span><span class="badge {badge_map.get(info["role"],"b-flex")}">{info["role"]}</span></span><span class="card-note">{info["note"]}</span></div>\n' for name,info in sorted_cards)
    
    # Kill turn
    kt=sd.get('kt_dist',{})
    peak=max(kt.values()) if kt and max(kt.values())>0 else 1
    kt_html=''.join(f'<div class="kt-col"><div class="kt-pct">{kt.get(t,0):.0f}%</div><div class="kt-fill" style="height:{max(kt.get(t,0)/peak*80,2):.0f}%"></div><div class="kt-label">T{t}</div></div>\n' for t in range(2,10) if kt.get(t,0)>=0.5)
    
    # Hand archetypes
    archs=sd.get('archetypes',[])
    base=sd.get('baseline',50)
    arch_html=''.join(f'<div class="arch-row"><span class="arch-name">{k} ({n})</span><div class="arch-bar"><div class="arch-fill" style="width:{wr}%;background:{muc(wr)}"></div></div><span class="arch-val" style="color:{muc(wr)}">{wr}% <span style="font-size:9px;font-weight:400;color:{"#1f7040" if wr>base else "#b02020"}">{wr-base:+.1f}pp</span></span></div>\n' for k,wr,n in archs[:6])
    if arch_html: arch_html+=f'<div class="arch-base">── baseline {base}% ──</div>\n'
    
    # Hands
    hands_html=''
    for g in sd.get('win_ex',[]):
        cs=', '.join(f'<span class="card-tip" data-card="{c}">{c}</span>' for c in g['hand'])
        logs='<br>'.join(g['logs'][:8])
        hands_html+=f'<div class="hand-box keep"><div class="hand-verdict keep">✓ WON T{g["kill_turn"]} vs {g["opp"]}</div><div class="hand-cards">{cs}</div><div class="hand-why">{logs}</div></div>\n'
    for g in sd.get('loss_ex',[]):
        cs=', '.join(f'<span class="card-tip" data-card="{c}">{c}</span>' for c in g['hand'])
        hands_html+=f'<div class="hand-box mull"><div class="hand-verdict mull">✗ LOST vs {g["opp"]} (T{g["length"]})</div><div class="hand-cards">{cs}</div><div class="hand-why">Opponent was faster or had better interaction.</div></div>\n'
    
    # Findings
    findings_html=f'<div class="finding"><span class="finding-label">Flat → weighted</span><span class="finding-val {"r" if delta<0 else "g"}">{delta:+.1f}pp</span></div>\n'
    findings_html+=f'<div class="finding"><span class="finding-label">Avg kill turn</span><span class="finding-val">{sd.get("avg_kill","?")}</span></div>\n'
    findings_html+=f'<div class="finding"><span class="finding-label">Best: {best[1]}</span><span class="finding-val g">{best[0]:.0f}%</span></div>\n'
    findings_html+=f'<div class="finding"><span class="finding-label">Worst: {worst[1]}</span><span class="finding-val r">{worst[0]:.0f}%</span></div>\n'
    
    archetype_wr_html = section_archetype_wr(d, D_CTX, agg)
    tournament_sim_html = section_tournament_sim(d, D_CTX, agg)
    tier_triptych_html = section_tier_triptych(d, D_CTX, agg)
    tournament_arc_html = section_tournament_arc(d, D_CTX, agg)
    delta_proof_html = section_delta_proof(d, D_CTX, agg)
    danger_cards_html = section_danger_cards(d, D_CTX, agg)

    # Matchup spread
    mu='';cur_tier=''
    for d2 in sorted(decks,key=lambda x:-W.get(x,0)):
        if d2==d: continue
        owr=W.get(d2,0);t='T1' if owr>=58 else 'T2' if owr>=48 else 'T3' if owr>=33 else 'T4'
        if t!=cur_tier:
            cur_tier=t
            mu+='<div class="tier-hdr">'+t+'</div>\n'
        wr=M.get(d+'|'+d2,[50])[0];ar=agg.get(d2,{}).get('type','?');col=muc(wr);dpp=round(wr-50,1)
        mu+='<div class="mu-row"><span class="mu-name">'+d2+'</span><span class="mu-type">'+ar+'</span><div class="mu-bar"><div class="mu-fill" style="width:'+str(wr)+'%;background:'+col+'"></div></div><span class="mu-val" style="color:'+col+'">'+str(wr)+'% <span style="font-size:9px;font-weight:400">'+f'{dpp:+.0f}pp'+'</span></span></div>\n'
    
    # ------------------------------------------------------------------
    # Stars of the Sim — 4 featured cards w/ Scryfall images.
    # MVP Finisher, MVP Caster, MVP Attacker, and an Overperformer
    # (a card that ranks top-3 in casts or attacks but *isn't* in the
    # deck's obvious "kill" card pool — surfaces role players).
    # ------------------------------------------------------------------
    stars_html = ''
    stars = aggregate_stars(dk) if CARD_DATA else None
    if stars and (stars['finishers'] or stars['casts'] or stars['attackers']):
        # Total games sampled (approx): finishers are killing-blows only,
        # but total casts gives us a richer denominator.
        total_casts = sum(c for _, c in stars['casts']) or 1
        # Build 4 star cards
        cards_used = set()
        star_items = []
        if stars['finishers']:
            n, c = stars['finishers'][0]
            star_items.append(('MVP — #1 Finisher', n, f'{c} kills',
                               f'Closed more games than any other card in the deck', 'mvp'))
            cards_used.add(n.lower())
        if stars['casts']:
            # Top caster that isn't already the MVP finisher
            for n, c in stars['casts']:
                if n.lower() not in cards_used:
                    star_items.append(('MVP — #1 Caster', n, f'{c} casts',
                                       f'The engine — most-played spell across every matchup', 'mvp'))
                    cards_used.add(n.lower())
                    break
        if stars['attackers']:
            # Top attacker that isn't the MVP finisher / caster
            for n, c in stars['attackers']:
                if n.lower() not in cards_used:
                    star_items.append(('MVP — #1 Attacker', n, f'{c} attacks',
                                       f'Leads the combat step more than any other creature', 'mvp'))
                    cards_used.add(n.lower())
                    break
        # Overperformer: cast top-3 but NOT in finishers top-3
        fin_top3 = {n.lower() for n, _ in stars['finishers'][:3]}
        for n, c in stars['casts'][:5]:
            if n.lower() in cards_used: continue
            if n.lower() in fin_top3: continue
            # Also skip lands (they always top cast counts for fair decks)
            nl = n.lower()
            if any(x in nl for x in ['wasteland', 'tarn', 'delta', 'mesa', 'strand',
                                     'island', 'swamp', 'forest', 'mountain', 'plains',
                                     'underground sea', 'volcanic', 'tropical', 'tundra',
                                     'plateau', 'badlands', 'taiga', 'bayou', 'savannah',
                                     'scrubland']):
                continue
            star_items.append(('Overperformer', n, f'{c} casts',
                               'Not the headliner, but consistently punches above its mana cost', 'surprise'))
            cards_used.add(n.lower())
            break
        star_items = star_items[:4]
        if star_items:
            stars_html = '<div class="section-title">Stars of the Sim — 2,000 Games</div>\n'
            stars_html += '<div class="star-cards">\n'
            for label, name, stat, desc, klass in star_items:
                fuzzy = name.replace(" ", "+").replace(",", "%2C").replace("'", "%27")
                stars_html += (f'<div class="star-card">'
                               f'<span class="star-label {klass}">{label}</span>'
                               f'<img src="https://api.scryfall.com/cards/named?fuzzy={fuzzy}&format=image&version=normal" alt="{name}" loading="lazy">'
                               f'<div class="star-name">{name}</div>'
                               f'<div class="star-stat">{stat}</div>'
                               f'<div class="star-desc">{desc}</div>'
                               f'</div>\n')
            stars_html += '</div>\n'

    # ------------------------------------------------------------------
    # Bo3 Swing — G1 vs Match WR. Uses Bo3 matrix match_wr - bo1 wr.
    # Positive = Bo3 compounds your edge; negative = variance-prone.
    # Sim has no real sideboards, so this is best read as a proxy for
    # matchup reliability across a 3-game series.
    # ------------------------------------------------------------------
    bo3_swing_html = ''
    if _BO3:
        swings = compute_bo3_swings(dk)
        if swings:
            # Show top 4 positive + top 4 negative swings
            pos = [s for s in swings if s[3] > 0][:4]
            neg = sorted([s for s in swings if s[3] < 0], key=lambda x: x[3])[:4]
            rows = pos + neg
            if rows:
                bo3_swing_html = '<div class="section-title">Bo3 Swing — G1 vs Match WR</div>\n'
                bo3_swing_html += ('<div style="font-size:11px;color:#666;margin-bottom:10px;line-height:1.5">'
                                   'How the Bo3 match win rate differs from the Bo1 (G1) rate. '
                                   'Positive = your edge compounds over a series. Negative = variance-prone, can be stolen. '
                                   '<em>Note: sim has no real sideboards — treat as a reliability proxy.</em></div>\n')
                bo3_swing_html += '<div style="display:flex;flex-direction:column;gap:4px;margin:8px 0">\n'
                for opp, bo1, bo3, swing in rows:
                    swing_col = '#1f7040' if swing > 0 else '#b02020'
                    bar_dir = 'margin-left:50%' if swing > 0 else f'margin-left:{max(0, 50 + swing):.0f}%'
                    bar_w = min(50, abs(swing) * 2)  # scale ±25pp to 50% bar width
                    bo3_swing_html += (f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #f5f5f5">'
                                       f'<span style="width:110px;font-size:11px;color:#555;text-align:right">{opp.replace("_"," ").title()}</span>'
                                       f'<span style="width:62px;font-size:10px;color:#888;text-align:right">G1 {bo1:.0f}%</span>'
                                       f'<div style="flex:1;height:10px;background:#f0f0f0;border-radius:2px;overflow:hidden;position:relative;max-width:180px">'
                                       f'<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#ccc"></div>'
                                       f'<div style="height:100%;background:{swing_col};{bar_dir};width:{bar_w}%;border-radius:2px"></div>'
                                       f'</div>'
                                       f'<span style="width:68px;font-size:10px;color:#888;text-align:left">Bo3 {bo3:.0f}%</span>'
                                       f'<span style="width:52px;font-size:11px;font-weight:700;color:{swing_col};text-align:right">{swing:+.1f}pp</span>'
                                       f'</div>\n')
                bo3_swing_html += '</div>\n'

    # ------------------------------------------------------------------
    # What Kills You — Removal Blind Spots. Aggregate opponent finishers
    # across all matchups where opponent beat this deck. Top 8 shown.
    # ------------------------------------------------------------------
    what_kills_html = ''
    if CARD_DATA:
        killers = aggregate_what_kills(dk)
        if killers:
            top = killers[:8]
            max_cnt = max(c for _, c in top) if top else 1
            what_kills_html = '<div class="section-title">What Kills You — Removal Blind Spots</div>\n'
            what_kills_html += ('<div style="font-size:11px;color:#666;margin-bottom:10px;line-height:1.5">'
                                'Cards that closed games against this deck across the metagame. '
                                'If your removal suite doesn\'t have an answer to the top 3, you have a blind spot.</div>\n')
            what_kills_html += '<div style="display:flex;flex-direction:column;gap:3px">\n'
            for name, cnt in top:
                bar_w = cnt / max_cnt * 100
                what_kills_html += (f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                                    f'<span style="width:170px;font-size:12px;color:#333;text-align:right">'
                                    f'<span class="card-tip" data-card="{name}">{name}</span></span>'
                                    f'<div style="flex:1;height:12px;background:#f5f5f5;border-radius:2px;overflow:hidden;max-width:240px">'
                                    f'<div style="width:{bar_w:.0f}%;height:100%;background:#b02020;border-radius:2px"></div>'
                                    f'</div>'
                                    f'<span style="width:60px;font-size:11px;font-weight:700;color:#b02020;text-align:right">{cnt} kills</span>'
                                    f'</div>\n')
            what_kills_html += '</div>\n'

    # Write using string concatenation (no f-strings for JS)
    _out_path = os.path.join(OUT_DIR, 'guide_'+dk+'.html')
    with open(_out_path,'w') as f:
        f.write('<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">\n')
        f.write('<title>'+d.replace('_',' ').title()+' — Legacy Deck Guide</title>\n')
        f.write('<style>\n')
        f.write('*{box-sizing:border-box;margin:0;padding:0}\n')
        f.write("body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fff;color:#111;font-size:14px;padding:24px;max-width:960px;margin:0 auto}\n")
        f.write('h1{font-size:24px;font-weight:700;margin-bottom:6px}.subtitle{font-size:12px;color:#888;margin-bottom:20px}\n')
        f.write('.hero{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #e0e0e0;border-radius:4px;margin-bottom:24px;overflow:hidden}\n')
        f.write('.hero-item{padding:14px 16px;border-right:1px solid #e0e0e0}.hero-item:last-child{border-right:none}\n')
        f.write('.hero-label{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:4px}\n')
        f.write('.hero-val{font-size:28px;font-weight:700;line-height:1}.hero-val.g{color:#1f7040}.hero-val.r{color:#b02020}.hero-val.a{color:#854f0b}\n')
        f.write('.hero-sub{font-size:11px;color:#666;margin-top:5px}\n')
        f.write('.two-col{display:grid;grid-template-columns:1fr 1fr;gap:28px}@media(max-width:640px){.two-col{grid-template-columns:1fr}}\n')
        f.write('.section-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#666;margin-bottom:12px;margin-top:24px;border-bottom:1px solid #e8e8e8;padding-bottom:6px}\n')
        f.write('.card-row{display:flex;align-items:baseline;gap:8px;padding:3px 0;border-bottom:1px solid #f5f5f5;font-size:13px}\n')
        f.write('.card-count{font-weight:700;color:#111;min-width:14px;text-align:right;flex-shrink:0}.card-name{flex:1;color:#222}.card-note{font-size:10px;color:#999;flex-shrink:0}\n')
        f.write('.badge{display:inline-block;font-size:9px;padding:1px 5px;border-radius:3px;margin-left:4px;font-weight:600;vertical-align:middle}\n')
        f.write('.b-threat{background:#e8f0e8;color:#306030}.b-burn{background:#fff0e8;color:#c04010}.b-reach{background:#f0e8ff;color:#7030a0}\n')
        f.write('.b-engine{background:#fff0e0;color:#c06010}.b-kill{background:#ffe0e0;color:#a01010}.b-enabler{background:#e8ffe8;color:#207020}\n')
        f.write('.b-removal{background:#ffe8e8;color:#c02020}.b-draw{background:#e0f0ff;color:#1060a0}.b-protect{background:#e8eef8;color:#2a5090}\n')
        f.write('.b-hate{background:#f8e8f8;color:#802080}.b-flex{background:#f0f0f0;color:#666}\n')
        f.write('.finding{display:flex;align-items:baseline;gap:8px;padding:6px 0;border-bottom:1px solid #f0f0f0}\n')
        f.write('.finding-label{flex:1;font-size:12px;color:#333}.finding-val{font-size:11px;font-weight:700}.finding-val.g{color:#1f7040}.finding-val.r{color:#b02020}\n')
        f.write('.phase{background:#f9f9f9;border-left:3px solid '+color+';border-radius:0 4px 4px 0;padding:10px 14px;margin:8px 0}\n')
        f.write('.phase-title{font-size:11px;font-weight:700;color:'+color+';text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}\n')
        f.write('.phase-body{font-size:13px;color:#444;line-height:1.6}\n')
        f.write('.kt-bar{display:flex;align-items:flex-end;gap:3px;height:100px;padding-bottom:18px;position:relative;margin:8px 0}\n')
        f.write(".kt-bar::after{content:'';position:absolute;bottom:18px;left:0;right:0;border-top:1px solid #e8e8e8}\n")
        f.write('.kt-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}\n')
        f.write('.kt-pct{font-size:9px;font-weight:700;color:'+color+';margin-bottom:2px}.kt-fill{width:100%;background:'+color+';border-radius:2px 2px 0 0}.kt-label{font-size:9px;color:#aaa;margin-top:3px}\n')
        f.write('.arch-row{display:flex;align-items:center;gap:8px;padding:3px 0}.arch-name{width:100px;text-align:right;font-size:11px;color:#555}\n')
        f.write('.arch-bar{flex:1;height:14px;background:#f5f5f5;border-radius:2px;overflow:hidden}.arch-fill{height:100%;border-radius:2px}\n')
        f.write('.arch-val{width:40px;font-weight:700;font-size:11px;text-align:right}.arch-base{border-bottom:1px dashed #ccc;margin:4px 0;padding:2px 0;font-size:10px;color:#aaa;text-align:center}\n')
        f.write('.hand-box{border:1px solid #e0e0e0;border-radius:4px;padding:12px 14px;margin:8px 0}\n')
        f.write('.hand-box.keep{border-left:4px solid #1f7040}.hand-box.mull{border-left:4px solid #b02020}\n')
        f.write('.hand-verdict{font-size:12px;font-weight:700;margin-bottom:4px}.hand-verdict.keep{color:#1f7040}.hand-verdict.mull{color:#b02020}\n')
        f.write(".hand-cards{font-size:12px;color:"+color+";margin-bottom:6px;font-family:'SF Mono','Fira Code',monospace}.hand-why{font-size:12px;color:#555;line-height:1.6}\n")
        f.write('.mu-row{display:flex;align-items:center;gap:6px;padding:3px 0;font-size:12px}.mu-name{width:120px;text-align:right;color:#555;font-size:11px}\n')
        f.write('.mu-type{width:52px;font-size:9px;color:#aaa;text-align:center}.mu-bar{flex:1;height:10px;background:#f0f0f0;border-radius:2px;overflow:hidden;max-width:160px}\n')
        f.write('.mu-fill{height:100%;border-radius:2px}.mu-val{width:36px;font-weight:700;font-size:11px;text-align:right}\n')
        f.write('.tier-hdr{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#aaa;margin:14px 0 4px;padding:4px 0;border-bottom:1px solid #f0f0f0}\n')
        f.write('.prov{font-size:9px;color:#bbb;text-align:center;margin-top:30px;border-top:1px solid #eee;padding-top:10px}\n')
        f.write('.card-tip{position:relative;cursor:pointer;border-bottom:1px dotted #ccc}.card-tip:hover{color:'+color+'}\n')
        f.write('#card-popup{position:fixed;z-index:999;pointer-events:none;display:none;border-radius:8px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.35);width:244px;height:340px;background:#111}\n')
        f.write('#card-popup img{width:100%;height:100%;object-fit:contain}\n')
        # Stars of the Sim — 4-column card grid
        f.write('.star-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}\n')
        f.write('@media(max-width:720px){.star-cards{grid-template-columns:repeat(2,1fr)}}\n')
        f.write('.star-card{border:1px solid #e0e0e0;border-radius:8px;padding:10px;display:flex;flex-direction:column;align-items:center;background:#fafafa}\n')
        f.write('.star-label{display:inline-block;font-size:9px;padding:2px 8px;border-radius:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}\n')
        f.write('.star-label.mvp{background:#fff0e0;color:#c06010}.star-label.surprise{background:#e8f0ff;color:#2060c0}\n')
        f.write('.star-card img{width:100%;max-width:140px;border-radius:6px;margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,.15)}\n')
        f.write('.star-name{font-size:12px;font-weight:700;color:#222;text-align:center;margin-bottom:4px;line-height:1.3}\n')
        f.write('.star-stat{font-size:15px;font-weight:700;color:#1f7040;margin-bottom:4px}\n')
        f.write('.star-desc{font-size:10px;color:#666;text-align:center;line-height:1.4}\n')
        f.write('</style></head><body>\n')
        
        # Hero
        f.write('<h1>'+d.replace('_',' ').title()+'</h1>\n')
        f.write('<div class="subtitle">'+dtype.title()+' · Legacy · April 2026</div>\n')
        wt_col = '#1f7040' if wtd>=58 else '#854f0b' if wtd>=48 else '#b02020'
        f.write('<div class="hero"><div class="hero-item"><div class="hero-label">Format</div><div class="hero-val" style="font-size:18px;padding-top:4px">Legacy</div><div class="hero-sub">'+dtype.title()+'</div></div>')
        f.write('<div class="hero-item"><div class="hero-label">Sim WR (flat)</div><div class="hero-val '+tier_cls+'">'+str(flat)+'%</div><div class="hero-sub">⚖ <span style="color:'+wt_col+'">'+str(wtd)+'%</span> weighted</div></div>')
        f.write('<div class="hero-item"><div class="hero-label">Rank</div><div class="hero-val '+tier_cls+'" style="font-size:22px;padding-top:2px">#'+str(rank)+'</div><div class="hero-sub">'+tier+' · '+str(delta)+'pp</div></div>')
        f.write('<div class="hero-item"><div class="hero-label">Best / Worst</div><div class="hero-val g" style="font-size:18px;padding-top:2px">'+str(int(best[0]))+'%</div><div class="hero-sub">vs '+best[1]+' / worst '+str(int(worst[0]))+'% vs '+worst[1]+'</div></div></div>\n')
        
        # Two-column: decklist + findings
        f.write('<div class="two-col"><div>\n')
        f.write('<div class="section-title">Decklist — '+str(len(cards_list))+' Cards</div>\n')
        f.write(main_html)
        f.write('</div><div>\n')
        f.write('<div class="section-title">Deck Construction Findings</div>\n')
        f.write(findings_html)
        f.write('</div></div>\n')
        
        # Stars of the Sim (NEW — card-level MVPs w/ Scryfall images)
        if stars_html:
            f.write(stars_html)
        
        # Game plan
        if plan:
            f.write('<div class="section-title">Game Plan</div>\n')
            f.write('<div class="phase"><div class="phase-body">'+plan+'</div></div>\n')
        
        # Kill turn
        if kt_html:
            f.write('<div class="section-title">Kill Turn Distribution</div>\n')
            f.write('<div class="kt-bar">'+kt_html+'</div>\n')
        
        # Hand archetypes
        if arch_html:
            f.write('<div class="section-title">Hand Archetype Win Rates — 2,000 Games</div>\n')
            f.write(arch_html)
        
        # Real hands
        if hands_html:
            f.write('<div class="section-title">Real Hands From Sim</div>\n')
            f.write(hands_html)
        
        # Metagame strategy
        f.write('<div class="section-title">Metagame Strategy</div>\n')
        f.write('<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0">\n')
        f.write(archetype_wr_html)
        f.write(tournament_sim_html)
        f.write('</div>\n')
        
        f.write(tier_triptych_html)
        
        f.write(danger_cards_html)
        
        f.write(tournament_arc_html)
        
        # Delta proof
        f.write(delta_proof_html)
        
        # Bo3 Swing (NEW — match_wr vs bo1 wr per matchup)
        if bo3_swing_html:
            f.write(bo3_swing_html)
        
        # What Kills You (NEW — opponent finisher cards aggregated)
        if what_kills_html:
            f.write(what_kills_html)
        
        # Matchup spread
        f.write('<div class="section-title">Matchup Spread</div>\n')
        f.write(mu)
        
        # Provenance
        f.write('<div class="prov">MTGSimClaude · 2000 games/deck · '+str(len(decks))+' decks · April 12 2026</div>\n')
        
        # JS hover
        f.write(JS_HOVER)
        f.write('\n</body></html>')

# Summary
print("\nAll guides:")
for dk in sorted(DECKS.keys()):
    fn = os.path.join(OUT_DIR, 'guide_'+dk+'.html')
    if not os.path.exists(fn):
        # Guide not found (check for generation errors)
        # would indicate a real error.
        print('  '+dk.ljust(15)+'SKIP (not generated)')
        continue
    sz = os.path.getsize(fn)//1024
    c = open(fn).read()
    flags = ('✓' if 'two-col' in c else '✗') + ('✓' if 'kt-col' in c else '✗') + ('✓' if 'arch-row' in c else '✗') + ('✓' if 'hand-box' in c else '✗') + ('✓' if 'finding' in c else '✗') + ('✓' if 'card-tip' in c else '✗') + ('✓' if 'Tournament' in c else '✗')
    print('  '+dk.ljust(15)+str(sz).rjust(3)+'KB '+flags)
print("  Flags: 2col|kt|arch|hands|find|hover|meta")
