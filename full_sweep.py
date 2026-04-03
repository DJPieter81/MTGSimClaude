"""
full_sweep.py — 3k re-sweep for all 17 MED decks.
Run this in Claude Code where there's no timeout.
Takes ~4 hours. Checkpoints after each deck.
"""
import sys, json, time
sys.path.insert(0, '.')

from sim import run_any_bo3
from cards import DECKS
from sim import STRATEGIES
from decks.eight_cast import _strategy_eight_cast, make_eight_cast_deck
from decks.tes import _strategy_tes, make_tes_deck
DECKS['eight_cast'] = make_eight_cast_deck; DECKS['tes'] = make_tes_deck
STRATEGIES['eight_cast'] = _strategy_eight_cast; STRATEGIES['tes'] = _strategy_tes

FIELD = {
    'uwx':0.182,'mardu':0.121,'prison':0.061,'reanimator':0.061,
    'dimir':0.061,'dimir_b':0.061,'lands':0.061,'show':0.061,'storm':0.061,
    'dimir_flash':0.030,'oops':0.030,'doomsday':0.030,'eldrazi':0.030,
    'painter':0.030,'dnt':0.030,'mono_black':0.030,'boros':0.030,'ur_aggro':0.030,
}
total = sum(FIELD.values()); FIELD = {k:v/total for k,v in FIELD.items()}

# All MED decks to re-sweep (storm already done)
ALL = ['bug','dimir','uwx','show','eight_cast','reanimator','mono_black',
       'painter','dnt','elves','eldrazi','mardu','boros','prison','lands',
       'oops','doomsday']

s = json.load(open('results/overnight_sweep.json'))

for proto in ALL:
    if proto not in DECKS:
        print(f"skip {proto} (not in DECKS)"); continue
    print(f"\n=== {proto} ==="); t0 = time.time(); ev = 0.0; pm = {}
    for ant, w in sorted(FIELD.items(), key=lambda x: -x[1]):
        if ant not in DECKS: continue
        r = run_any_bo3(proto, ant, 3000)
        wr = round(r['match_wr']*100, 1); ev += w*wr; pm[ant] = wr
        print(f"  {proto} vs {ant}: {wr:.1f}%", flush=True)
    s['completed'][proto] = round(ev, 2)
    s['per_matchup'][proto] = pm
    s['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    json.dump(s, open('results/overnight_sweep.json','w'), indent=2)
    print(f"  DONE {proto}: {round(ev,2)}% ({(time.time()-t0)/60:.1f}min)")

print("\n=== ALL COMPLETE ===")
for d, ev in sorted(s['completed'].items(), key=lambda x: -x[1]):
    print(f"  {d:<15} {ev:.1f}%")
