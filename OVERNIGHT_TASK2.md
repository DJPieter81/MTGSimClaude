# OVERNIGHT_TASK.md — Autonomous Small-Fix Iteration Loop (v2)

## Goal
Improve strategy accuracy for underperforming decks by making **one small fix per iteration**, testing, measuring, and committing if positive.

## Required Reading (before any work)
```bash
cat CLAUDE.md    # API, architecture, "Never" list
cat PLANNING.md  # known bugs, priorities, session log
```

## Architecture: Where Strategies Live

Strategies are dispatched via `deck_registry.py` → `decks/*.py`. Two patterns exist:

**Wrapper decks** (~40-50 lines in `decks/*.py`): Delegate to `engine.py`.
Storm, Doomsday, Painter, Mardu, Show, Reanimator, BUG, Dimir, DNT, Ocelot, Mono Black, Boros, Eldrazi, Lands, Oops, Prison, UWx, UR Aggro.
→ **Edit the strategy function in `engine.py`**

**Self-contained decks** (~200-500 lines in `decks/*.py`): Full strategy inline.
Goblins, Eight Cast, Affinity, Burn, Cephalid, Cloudpost, Depths, Dimir B/C/D, Dimir Flash, Elves, Infect, Sneak A/B, TES, UR Delver, UR Tempo, Wan Shi Tong, Belcher.
→ **Edit the strategy function in `decks/DECKNAME.py`**

To find which: `head -5 decks/DECKNAME.py` — if it says "wrapper for built-in deck" → edit `engine.py`.

## Constraints (HARD)
- **Max 15 lines changed per iteration** (check with `git diff --stat`)
- **Edit strategy functions only** — in `engine.py` OR `decks/*.py` (see above)
- **Never edit**: `sim.py`, `game.py`, `rules.py`, `cards.py`, `deck_registry.py`, `config.py`
- **Tests must pass** after every change: `python3 -c "from sim import run_rules_tests; run_rules_tests()"` → must say `147 passed, 0 failed`
- **If test count drops below 147** → revert immediately, stop, log the issue
- **No hardcoded magic numbers** — use card properties, game state, or `config.py` constants (see CLAUDE.md §4)
- **Never touch Burn strategy** — it's hand-tuned and correct
- **Never change the matrix or re-run it** — only sweep individual matchups
- **Git commit each successful fix** with message: `overnight: [deck] [what] [±Xpp vs opponent]`
- **Stop after 25 iterations OR first test failure OR 3 consecutive no-improvement iterations**

## Baseline (run FIRST before any changes)
```python
python3 -c "
from sim import run_sweep
pairs = [
    ('storm','dnt'), ('doomsday','dimir'), ('painter','dimir'),
    ('mardu','burn'), ('reanimator','uwx'), ('show','dnt'),
    ('goblins','dimir'), ('eight_cast','burn'), ('belcher','dimir_b'),
    ('ur_aggro','eldrazi'), ('prison','infect'), ('cephalid','elves'),
    ('wan_shi_tong','cloudpost'), ('ocelot','burn'), ('lands','oops'),
]
for d,o in pairs:
    s = run_sweep(d, o, n_games=200)
    print(f'{d:15s} vs {o:15s}: {s[\"p1_wr\"]:.1%}')
"
```
Save this output as the baseline in `overnight_log.md`.

## Target List (priority order)

### Tier 1 — Known issues from PLANNING.md
| # | Deck | Matchup | Flat WR | Issue |
|---|------|---------|---------|-------|
| 1 | storm | dnt | 43% | Won't cast cantrips under Thalia tax; ritual chain too conservative |
| 2 | doomsday | dimir | 33% | Strategy may not deploy DD aggressively enough |
| 3 | painter | dimir | 35% | Karn lockout partially implemented; combo deployment gaps |

### Tier 2 — Structural underperformers
| # | Deck | Matchup | Flat WR | Likely issue |
|---|------|---------|---------|--------------|
| 4 | mardu | burn | 36% | May not sequence removal + threats optimally |
| 5 | goblins | dimir | 40% | Lackey/Vial deployment; Muxus timing |
| 6 | eight_cast | burn | 44% | Artifact swarm speed vs direct damage |
| 7 | reanimator | uwx | 41% | Combo speed vs control interaction |
| 8 | show | dnt | 40% | Fixed in v1; check if more S&T targets needed |

### Tier 3 — Stretch goals
| # | Deck | Matchup | Flat WR | Likely issue |
|---|------|---------|---------|--------------|
| 9 | belcher | dimir_b | 37% | May need faster combo assembly |
| 10 | ur_aggro | eldrazi | 39% | Creature sizing; removal targeting |
| 11 | prison | infect | 43% | Lock pieces not deployed fast enough |
| 12 | cephalid | elves | 44% | Combo race timing |
| 13 | wan_shi_tong | cloudpost | 37% | Strategy gaps |
| 14 | ocelot | burn | 48% | Threat sequencing vs burn |
| 15 | lands | oops | 45% | Marit Lage race vs T1 combo |

## Iteration Loop

For each target:

### Step 1: Diagnose (read-only)
```python
import random
from sim import run_game
for seed in [42, 99, 7]:
    random.seed(seed)
    r = run_game('TARGET_DECK', 'OPPONENT', verbose=True)
    print(f"\n=== Seed {seed}: {r.winner} T{r.kill_turn} ===")
    for line in r.log_lines:
        print(line)
```

**Checklist — scan logs for these patterns:**
- [ ] Card in hand 3+ turns but never played → missing cast logic
- [ ] Mana >= card.cmc but card not cast → missing branch in strategy
- [ ] Win condition available but not attempted → combo execution gap
- [ ] Removal sitting in hand while opponent has threats → missing removal branch
- [ ] Cantrip not cast when looking for combo piece → missing cantrip priority
- [ ] Creature deployed but never attacks → combat logic gap
- [ ] Fast mana cracked without follow-up → needs combo gate pattern
- [ ] Tax effect present but spells cast at original cost → tax not accounted for

**If none of these patterns appear clearly → SKIP to next target** (don't force a fix).

### Step 2: Find the right file
```bash
head -5 decks/TARGET_DECK.py
# If "wrapper" → edit engine.py, function _strategy_TARGET_DECK
# If full strategy → edit decks/TARGET_DECK.py, function strategy or _strategy_TARGET_DECK
```

### Step 3: Fix (one branch)
Add ONE if/elif branch. Max 15 lines. Examples:

```python
# Cast cantrip even under Thalia tax
effective_cost = c.cmc + (1 if gs_has_thalia else 0)
if mana >= effective_cost and c.tag in ('bs', 'ponder'):
    mana -= effective_cost
    # ... cast logic

# Deploy win condition that was sitting in hand
if mana >= fatty.cmc and fatty in hand:
    player.put_creature_in_play(fatty)
    hand.remove(fatty)

# Use removal on biggest opponent threat
threats = sorted(opponent.battlefield, key=lambda p: p.power, reverse=True)
if removal_card in hand and threats and mana >= removal_card.cmc:
    # ... removal logic
```

### Step 4: Test
```bash
python3 -c "from sim import run_rules_tests; run_rules_tests()"
# MUST print: 147 passed, 0 failed
# If test count != 147 → git checkout engine.py decks/ && STOP
```

### Step 5: Measure
```python
from sim import run_sweep

# Primary matchup
s = run_sweep('TARGET_DECK', 'OPPONENT', n_games=200)
print(f"Primary: {s['p1_wr']:.1%}")

# Spot-check 2 other matchups for regression
for opp in ['dimir', 'burn']:  # pick 2 different archetypes
    if opp != 'OPPONENT':
        s2 = run_sweep('TARGET_DECK', opp, n_games=100)
        print(f"Check vs {opp}: {s2['p1_wr']:.1%}")
```

**Accept if:** primary WR improved ≥2pp AND spot checks didn't regress >5pp.
**Reject if:** primary WR didn't improve, OR any spot check regressed >5pp.

### Step 6: Commit or Revert
```bash
# If accepted:
git add -A
git commit -m "overnight: [deck] [what changed] [+Xpp vs opponent]"

# If rejected:
git checkout engine.py decks/
```

### Step 7: Log
Append to `overnight_log.md`:
```
## Iteration N — DECK vs OPPONENT
- **File**: engine.py / decks/DECK.py
- **Diagnosis**: [pattern found in verbose logs]
- **Fix**: [what branch added, which function, approx line]
- **Lines changed**: N
- **Before**: X.X% (n=200)
- **After**: Y.Y% (n=200)
- **Spot checks**: vs A: X%, vs B: Y%
- **Delta**: +/-Zpp
- **Result**: COMMITTED [hash] / REVERTED / SKIPPED
- **Time**: ~Nm
```

## Stop Conditions
1. **25 iterations completed** → stop, summarize
2. **Test count != 147** → revert, stop, log which change broke it
3. **3 consecutive no-improvement iterations** → stop, summarize
4. **All 15 targets attempted** → stop, summarize

## Final Steps (always, even after early stop)
```bash
# Verify clean state
python3 -c "from sim import run_rules_tests; run_rules_tests()"

# Final sweep of all changed decks vs their targets
# (list all decks that got committed fixes)

# Summary block in overnight_log.md
echo "=== OVERNIGHT RUN v2 COMPLETE ===" >> overnight_log.md
echo "Iterations: N" >> overnight_log.md
echo "Committed: N fixes" >> overnight_log.md
echo "Reverted: N" >> overnight_log.md
echo "Skipped: N" >> overnight_log.md
echo "Net WR impact: +Xpp across N matchups" >> overnight_log.md
echo "Test count: 147 passed" >> overnight_log.md
```

## Anti-Patterns (NEVER do these)
- Don't add cards to decklists — only fix strategy logic for existing cards
- Don't change how mana is calculated — only how it's spent
- Don't add new game mechanics — only use existing engine features
- Don't "fix" a matchup by nerfing the opponent's strategy
- Don't chain multiple fixes before testing — one fix, one test, one commit
- Don't spend >10 minutes diagnosing one matchup — skip to next target
- Don't re-run the matrix — use run_sweep() for targeted measurement
- Don't edit sim.py, game.py, rules.py, cards.py, config.py, or deck_registry.py
- Don't create new files — only modify existing strategy code
- Don't change mulligan logic (keep functions) — only in-game strategy
