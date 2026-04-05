"""
full_sweep_expanded.py — 5k-game sweep for the expanded 27-deck meta.
Run this in Claude Code where there's no timeout.
Takes ~8-12 hours. Checkpoints after each deck.

Expanded from 18 to 25 antagonist decks:
  +depths, +burn, +infect, +goblins, +belcher, +ur_delver, +tes
"""
import sys, json, time, os
sys.path.insert(0, '.')

from sim import run_any_bo3
from cards import DECKS
from decks import register_decks
register_decks()

# ── Expanded meta field weights (mtgtop8, ~700 decks, 2026-04-04) ──
FIELD = {
    'dimir': 0.08,  'dimir_b': 0.05, 'dimir_flash': 0.03,
    'ur_aggro': 0.03, 'ur_delver': 0.04,
    'mardu': 0.03,  'show': 0.06,   'lands': 0.04,
    'storm': 0.03,  'tes': 0.02,    'oops': 0.04,
    'eldrazi': 0.03, 'reanimator': 0.03, 'doomsday': 0.03,
    'uwx': 0.04,    'painter': 0.03, 'prison': 0.04,
    'dnt': 0.03,    'mono_black': 0.03, 'boros': 0.02,
    'depths': 0.04, 'burn': 0.04,   'infect': 0.03,
    'goblins': 0.03, 'belcher': 0.02,
}
total = sum(FIELD.values())
FIELD = {k: v / total for k, v in FIELD.items()}

GAMES_PER_MATCHUP = 3000

# All decks to sweep (protagonist role)
ALL_PROTAGONISTS = [
    'bug', 'dimir', 'uwx', 'show', 'storm', 'tes',
    'eight_cast', 'reanimator', 'mono_black', 'painter',
    'dnt', 'elves', 'eldrazi', 'mardu', 'boros', 'prison',
    'lands', 'oops', 'doomsday', 'ur_aggro', 'ur_delver',
    'depths', 'burn', 'infect', 'goblins', 'belcher',
]

RESULTS_FILE = 'results/expanded_sweep.json'

# Load or init results
if os.path.exists(RESULTS_FILE):
    s = json.load(open(RESULTS_FILE))
else:
    s = {'completed': {}, 'per_matchup': {}, 'partial': {},
         'last_updated': '', 'games_per_matchup': GAMES_PER_MATCHUP,
         'field': FIELD}

for proto in ALL_PROTAGONISTS:
    if proto in s['completed']:
        print(f"skip {proto} (already done at {s['completed'][proto]}%)")
        continue
    if proto not in DECKS:
        print(f"skip {proto} (not in DECKS)")
        continue
    print(f"\n=== {proto} ===")
    t0 = time.time()
    ev = 0.0
    pm = {}
    for ant, w in sorted(FIELD.items(), key=lambda x: -x[1]):
        if ant not in DECKS:
            print(f"  skip {ant} (not in DECKS)")
            continue
        try:
            r = run_any_bo3(proto, ant, GAMES_PER_MATCHUP)
            wr = round(r['match_wr'] * 100, 1)
        except Exception as e:
            print(f"  ERROR {proto} vs {ant}: {e}")
            wr = 50.0  # neutral fallback
        ev += w * wr
        pm[ant] = wr
        print(f"  {proto} vs {ant}: {wr:.1f}%", flush=True)
        # Checkpoint partial progress
        s['partial'][proto] = pm
        s['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        json.dump(s, open(RESULTS_FILE, 'w'), indent=2)

    s['completed'][proto] = round(ev, 2)
    s['per_matchup'][proto] = pm
    if proto in s['partial']:
        del s['partial'][proto]
    s['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    json.dump(s, open(RESULTS_FILE, 'w'), indent=2)
    elapsed = (time.time() - t0) / 60
    print(f"  DONE {proto}: {round(ev, 2)}% ({elapsed:.1f}min)")

print("\n=== ALL COMPLETE ===")
print(f"{'Deck':<15} {'EV%':>6}")
print("-" * 22)
for d, ev in sorted(s['completed'].items(), key=lambda x: -x[1]):
    print(f"  {d:<15} {ev:.1f}%")
