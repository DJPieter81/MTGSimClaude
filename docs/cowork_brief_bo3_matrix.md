# Cowork Brief: Full Bo3 Matrix (PLANNING_REFERENCE §9 #5)

## One-sentence task
Wire `run_any_bo3()` into `run_meta_matrix()` and build sideboard plans for the 22 full-strategy decks so the meta matrix reports Bo3 match WRs alongside G1 game WRs.

## Why this matters
The current matrix is **Bo1 only**. In real Legacy, sideboards swing matchups by 10-15 pp per pair. Bo3 data would:
- Fix the "Burn ceiling" problem — Burn loses to graveyard/lifegain/prison sideboards, so its Bo3 match WR is much lower than its Bo1 game WR
- Let us report the format's actual tournament-relevant WRs
- Enable sideboard-tuning analyses that currently don't exist

## What's already in place
- `sim.py:691` — `run_any_bo3(protagonist, antagonist, n_matches)` — existing Bo3 wrapper
- `run_meta.py --bo3 D1 D2 -n N` — single-matchup CLI (committed in `4ef0c55`)
- `cards.py` — has `make_postboard_any_deck(p, a)` and `make_postboard_opp_vs_protagonist(p, a)` — sideboard-aware deck builders, but only for a handful of matchups
- `symmetrise_matrix()` in `meta_results.py` — will work on Bo3 matrix identically

## Scope

### Part 1 — Sideboard plans for 22 decks (BIG)

Each full-strategy deck needs a `sideboard_plan(opponent_deck_key)` function that returns the post-SB 60-card decklist. The 22 full-strategy decks (from `gameplans/` + engine strategies):

| Deck | Core SB cards (typical Legacy) |
|------|-------------------------------|
| burn | Pyroblast, Roiling Vortex, Smash to Smithereens, Searing Blood, Ensnaring Bridge |
| storm | Abrupt Decay, Thoughtseize, Flusterstorm, Bayou, Xantid Swarm |
| dimir | Surgical Extraction, Hydroblast, Force of Negation, Null Rod |
| oops | Pact of Negation, Xantid Swarm, Endurance |
| doomsday | Echoing Truth, Duress, Thoughtseize |
| reanimator | Unmask, Echoing Truth, Faerie Macabre |
| lands | Sphere of Resistance, Chalice of the Void, Krosan Grip |
| prison | Chalice variants, Null Rod, Pithing Needle |
| show | Spell Pierce, Echoing Truth, Defense Grid |
| dnt | Cataclysm, Sanctum Prelate, Containment Priest |
| eldrazi | Warping Wail, Grafdigger's Cage |
| bug | Engineered Explosives, Liliana's Triumph |
| ur_delver | Pyroblast, Meltdown, Submerge |
| ur_tempo | Same as ur_delver |
| ur_aggro | Smash to Smithereens, Pyroblast |
| mono_black | Nihil Spellbomb, Leyline of the Void |
| mardu | Leyline of the Void, Pyroblast |
| boros | Rest in Peace, Pyroblast |
| elves | Endurance, Cavern of Souls |
| painter | Defense Grid, Boseiju |
| uwx | Rest in Peace, Surgical Extraction |
| infect | Spellskite, Viridian Corrupter |

Each `sideboard_plan()` specifies: "vs combo, swap out X and bring in Y". ~10-15 lines per deck. Validated by checking post-SB deck has exactly 60 cards and sideboard has exactly 15.

### Part 2 — Wire into matrix

```python
# meta_results.py (new function)
def run_meta_matrix_bo3(decks, n_matches=100, symmetrise=True):
    matrix = {}
    for d1 in decks:
        for d2 in decks:
            if d1 == d2: continue
            r = run_any_bo3(d1, d2, n_matches)
            matrix[f"{d1}_vs_{d2}"] = {
                'match_wr': r['match_wr'],
                'game_wr': r['game_wr'],
            }
    # Save with type='matrix_bo3'
    return matrix
```

```python
# run_meta.py --bo3-matrix flag
parser.add_argument('--bo3-matrix', action='store_true', ...)
```

### Part 3 — HTML rendering

Extend `build_matrix_html.py` to accept either a G1 or Bo3 matrix JSON. The template already has a match-WR vs game-WR toggle in the data — wire the actual values through.

## Performance budget
- G1 matrix at n=200 takes ~7 min for 36×36
- Bo3 at n=100 matches = 300 games per pair worst case → ~20 min for 36×36
- Acceptable per PLANNING_REFERENCE's "3.5-10 min" band

## Branch / PR shape
- Branch name: `claude/mtgsim-bo3-matrix-<suffix>`
- Commits:
  1. Add 22 sideboard_plan functions (one per deck module in `decks/`)
  2. `run_meta_matrix_bo3()` in meta_results.py + `--bo3-matrix` CLI
  3. build_matrix_html.py accepts Bo3 matrix
  4. Run the matrix, commit the JSON + HTML
- Tests: `verify.py tests` must still pass; each `sideboard_plan()` has a unit test that round-trips through `run_any_match()` without crashing

## Validation checklist for the new matrix
- All 1260 matchups have both match_wr and game_wr
- Burn's meta-weighted match WR should drop materially vs G1 (sign of SB working)
- Combo decks' match WRs drop post-SB (everyone brings Leyline/Thoughtseize)
- Fair decks' match WRs stay roughly the same

## Files the cowork session will touch
- NEW: one file per deck, e.g. `decks/burn_sb.py`, OR a new section in each existing `decks/*.py`
- MODIFY: `meta_results.py`, `run_meta.py`, `build_matrix_html.py`
- NEW JSON: `results/matrix_bo3_<ts>.json`
- NEW HTML: `results/meta_matrix_bo3_<ts>.html`

## Starting point
```bash
git fetch origin && git checkout -b claude/mtgsim-bo3-matrix-<suffix> origin/main
grep -n "make_postboard_any_deck\|make_postboard_opp_deck\|make_postboard_opp_vs_protagonist" cards.py
# Read those functions to see the existing sideboard shape
```
