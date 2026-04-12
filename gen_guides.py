#!/usr/bin/env python3
"""Generate full-featured deck guides for all decks in MTGSimClaude."""
import json, random, os, sys
from collections import Counter, defaultdict

sys.path.insert(0, '/home/claude/MTGSimClaude')
from sim import run_game
from cards import DECKS

with open('/home/claude/meta_fresh.json') as f: meta = json.load(f)
with open('/home/claude/deck_agg.json') as f: agg = json.load(f)
A=meta['a'];W=meta['w'];M=meta['m'];decks=meta['d']

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

# Run sim data collection
print("Collecting sim data for all decks...", flush=True)
random.seed(2026)
all_data = {}

for dk in sorted(DECKS.keys()):
    if dk == 'burn': continue
    games = []
    opps = [x for x in decks if x!=dk]
    for i in range(500):
        opp = random.choice(opps)
        try:
            r = run_game(dk, opp)
            hand_cards = list(r.p1_opening_hand) if r.p1_opening_hand else []
            games.append({
                'won': r.winner=='p1',
                'kill_turn': r.kill_turn or r.game_length,
                'hand': hand_cards,
                'opp': opp,
                'logs': r.log_lines[:12] if r.log_lines else [],
                'length': r.game_length,
                'mulls': r.p1_mulls or 0,
            })
        except: pass
    
    wins = [g for g in games if g['won']]
    kt_counts = Counter(min(g['kill_turn'],10) for g in wins)
    total_wins = max(len(wins),1)
    kt_dist = {t: round(kt_counts.get(t,0)/total_wins*100,1) for t in range(1,11)}
    
    hand_groups = defaultdict(lambda: {'wins':0,'total':0})
    for g in games:
        if not g['hand']: continue
        lands = sum(1 for c in g['hand'] if any(x in c.lower() for x in ['mountain','island','forest','swamp','plains','sea','tarn','strand','delta','mesa','foothills','mire','heath','catacombs','tomb','city','cavern','temple','port','waste','vantage','islet','ring','saga','depths','stage','bayou','volcanic','tropical','underground','tundra','savannah','scrubland','badlands','plateau','taiga','field','post','tower','mine','karakas','boseiju','otawara','seat','vault','foundry','den','arbor','nexus','mishra','urza']))
        lands = min(lands, 7)
        key = str(lands) + 'L-' + str(len(g['hand'])-lands) + 'S'
        hand_groups[key]['total'] += 1
        if g['won']: hand_groups[key]['wins'] += 1
    
    archetypes = [(k,round(d['wins']/d['total']*100,1),d['total']) for k,d in hand_groups.items() if d['total']>=10]
    archetypes.sort(key=lambda x:-x[1])
    baseline = round(len(wins)/max(len(games),1)*100,1)
    
    all_data[dk] = {
        'kt_dist': kt_dist,
        'archetypes': archetypes[:6],
        'baseline': baseline,
        'win_ex': sorted([g for g in wins if g['hand'] and g['kill_turn']<=8], key=lambda g:g['kill_turn'])[:2],
        'loss_ex': [g for g in games if not g['won'] and g['hand']][:1],
        'avg_kill': round(sum(g['kill_turn'] for g in wins)/total_wins,1) if wins else 0,
    }
    print(f"  {dk}: {len(games)} games, {len(wins)} wins, avg T{all_data[dk]['avg_kill']}", flush=True)

print(f"\nGenerating HTML guides...", flush=True)

for dk in sorted(DECKS.keys()):
    if dk == 'burn': continue
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
    arch_html=''.join(f'<div class="arch-row"><span class="arch-name">{k} ({n})</span><div class="arch-bar"><div class="arch-fill" style="width:{wr}%;background:{muc(wr)}"></div></div><span class="arch-val" style="color:{muc(wr)}">{wr}%</span></div>\n' for k,wr,n in archs[:6])
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
    
    # Tournament sim
    random.seed(42)
    wd=[]
    for _ in range(10000):
        w=0
        for rd in range(8):
            opps2=[x for x in decks if x!=d];wts=[max(0.1,A.get(x,30)) for x in opps2]
            opp=random.choices(opps2,weights=wts,k=1)[0]
            if random.random()<M.get(d+'|'+opp,[50])[0]/100: w+=1
        wd.append(w)
    c2=Counter(wd);avg=sum(wd)/len(wd);top8=sum(1 for w in wd if w>=6)/len(wd)*100
    hist={w:round(c2[w]/10000*100,1) for w in range(9)}
    
    # Archetype WR bars
    ag={}
    for x in decks:
        if x==d: continue
        a=agg.get(x,{}).get('type','?')
        if a not in ag: ag[a]=[]
        ag[a].append(M.get(d+'|'+x,[50])[0])
    awd={a:round(sum(v)/len(v),1) for a,v in ag.items()}
    ab=''.join(f'<div style="display:flex;align-items:center;gap:6px"><span style="width:60px;text-align:right;font-size:11px;color:#555">{a}</span><div style="flex:1;height:14px;background:#f5f5f5;border-radius:2px;overflow:hidden"><div style="width:{w}%;height:100%;background:{muc(w)};border-radius:2px"></div></div><span style="width:36px;font-weight:700;font-size:11px;text-align:right;color:{muc(w)}">{w:.0f}%</span></div>\n' for a,w in sorted(awd.items(),key=lambda x:-x[1]))
    
    # Tournament histogram
    th=''.join(f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%"><div style="font-size:8px;color:{"#1f7040" if w>=6 else "#854f0b" if w>=4 else "#b02020"}">{hist.get(w,0):.0f}%</div><div style="width:100%;background:{"#1f7040" if hist.get(w,0)==max(hist.get(i,0) for i in range(2,9)) else "#d0f0d0" if w>=6 else "#fff0e0" if w>=4 else "#fde8e8"};border-radius:2px 2px 0 0;height:{hist.get(w,0)}%"></div><div style="font-size:8px;color:#aaa">{w}-{8-w}</div></div>\n' for w in range(2,9))
    
    # Triptych
    prey=len([x for x in decks if x!=d and M.get(d+'|'+x,[50])[0]>=80])
    comp=len([x for x in decks if x!=d and 50<=M.get(d+'|'+x,[50])[0]<80])
    dng=len([x for x in decks if x!=d and M.get(d+'|'+x,[50])[0]<50])
    
    # Danger cards
    dangers=sorted([(M.get(d+'|'+x,[50])[0],x,agg.get(x,{}).get('type','?')) for x in decks if x!=d and M.get(d+'|'+x,[50])[0]<50])[:3]
    dc=''
    if dangers:
        dc='<div style="display:grid;grid-template-columns:'+' '.join(['1fr']*len(dangers))+';gap:12px;margin:12px 0">\n'
        for wr,nm,ar in dangers:
            dc+='<div style="border:1px solid #e8d0d0;border-radius:6px;overflow:hidden"><div style="background:linear-gradient(135deg,#b02020,#801818);padding:12px 14px;display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:13px;font-weight:700;color:#fff">'+nm+'</div><div style="font-size:9px;color:#ffb0b0;text-transform:uppercase">'+ar+'</div></div><div style="font-size:28px;font-weight:700;color:#fff">'+str(int(wr))+'%</div></div></div>\n'
        dc+='</div>\n'
    
    # Matchup spread
    mu='';cur_tier=''
    for d2 in sorted(decks,key=lambda x:-W.get(x,0)):
        if d2==d: continue
        owr=W.get(d2,0);t='T1' if owr>=58 else 'T2' if owr>=48 else 'T3' if owr>=33 else 'T4'
        if t!=cur_tier:
            cur_tier=t
            mu+='<div class="tier-hdr">'+t+'</div>\n'
        wr=M.get(d+'|'+d2,[50])[0];ar=agg.get(d2,{}).get('type','?');col=muc(wr)
        mu+='<div class="mu-row"><span class="mu-name">'+d2+'</span><span class="mu-type">'+ar+'</span><div class="mu-bar"><div class="mu-fill" style="width:'+str(wr)+'%;background:'+col+'"></div></div><span class="mu-val" style="color:'+col+'">'+str(wr)+'%</span></div>\n'
    
    # Write using string concatenation (no f-strings for JS)
    with open('/mnt/user-data/outputs/guide_'+dk+'.html','w') as f:
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
            f.write('<div class="section-title">Hand Archetype Win Rates — 500 Games</div>\n')
            f.write(arch_html)
        
        # Real hands
        if hands_html:
            f.write('<div class="section-title">Real Hands From Sim</div>\n')
            f.write(hands_html)
        
        # Metagame strategy
        f.write('<div class="section-title">Metagame Strategy</div>\n')
        f.write('<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0">\n')
        f.write('<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">Win Rate by Archetype</div>'+ab+'</div>\n')
        f.write('<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">8-Round Tournament Sim</div>')
        f.write('<div style="display:flex;align-items:flex-end;gap:3px;height:80px;margin-bottom:4px">'+th+'</div>')
        f.write('<div style="display:flex;justify-content:space-between;margin-top:8px;padding:6px 8px;background:#f0faf0;border-radius:3px"><span style="font-size:11px;color:#555">Avg: <b style="color:#1f7040">'+str(round(avg,1))+'</b></span><span style="font-size:11px;color:#555">Top 8: <b style="color:#1f7040">'+str(round(top8,1))+'%</b></span></div></div></div>\n')
        
        # Triptych
        f.write('<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0">')
        f.write('<div style="border:1px solid #e0e0e0;border-left:3px solid #1f7040;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#1f7040;font-weight:700;margin-bottom:6px">✓ Prey ('+str(prey)+')</div><div style="font-size:22px;font-weight:700;color:#1f7040">80%+</div></div>')
        f.write('<div style="border:1px solid #e0e0e0;border-left:3px solid #854f0b;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#854f0b;font-weight:700;margin-bottom:6px">⚖ Competitive ('+str(comp)+')</div><div style="font-size:22px;font-weight:700;color:#854f0b">50-80%</div></div>')
        f.write('<div style="border:1px solid #e0e0e0;border-left:3px solid #b02020;border-radius:0 4px 4px 0;padding:10px 12px"><div style="font-size:9px;text-transform:uppercase;color:#b02020;font-weight:700;margin-bottom:6px">⚠ Danger ('+str(dng)+')</div><div style="font-size:22px;font-weight:700;color:#b02020">&lt;50%</div></div></div>\n')
        
        f.write(dc)
        
        # Tournament arc
        f.write('<div style="border:1px solid #e0e0e0;border-radius:4px;padding:14px;margin:12px 0"><div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#888;margin-bottom:10px">Tournament Arc</div><div style="display:flex;gap:2px;height:24px;border-radius:3px;overflow:hidden"><div style="flex:3;background:#d0f0d0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#1f7040">R1-3 Bank</div><div style="flex:3;background:#fff0e0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#854f0b">R4-6 Gauntlet</div><div style="flex:2;background:#fde8e8;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#b02020">R7-8 Top</div></div></div>\n')
        
        # Matchup spread
        f.write('<div class="section-title">Matchup Spread</div>\n')
        f.write(mu)
        
        # Provenance
        f.write('<div class="prov">MTGSimClaude · 500 games/deck · '+str(len(decks))+' decks · April 12 2026</div>\n')
        
        # JS hover
        f.write(JS_HOVER)
        f.write('\n</body></html>')

# Summary
print("\nAll guides:")
for dk in sorted(DECKS.keys()):
    fn = '/mnt/user-data/outputs/guide_'+dk+'.html'
    sz = os.path.getsize(fn)//1024
    c = open(fn).read()
    flags = ('✓' if 'two-col' in c else '✗') + ('✓' if 'kt-col' in c else '✗') + ('✓' if 'arch-row' in c else '✗') + ('✓' if 'hand-box' in c else '✗') + ('✓' if 'finding' in c else '✗') + ('✓' if 'card-tip' in c else '✗') + ('✓' if 'Tournament' in c else '✗')
    print('  '+dk.ljust(15)+str(sz).rjust(3)+'KB '+flags)
print("  Flags: 2col|kt|arch|hands|find|hover|meta")
