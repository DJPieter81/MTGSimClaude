# OVERNIGHT_TASK.md — 6-7 Hour Autonomous Strategy Improvement Run (v3)

## Goal
Improve Legacy metagame simulation accuracy by fixing strategy logic gaps.
Each fix must use **zero hardcoded numbers** — all thresholds derived from game state.

---

## Setup (do this first, before any iteration)

### 1. Read project docs
```bash
cat CLAUDE.md
cat PLANNING.md
```

### 2. Understand the no-hardcoding rule (CRITICAL)
This project forbids ALL hardcoded numeric thresholds, arbitrary scores, magic
constants, and invented ranges in strategy code. This is the #1 constraint.

**FORBIDDEN patterns — never write these:**
```python
if opponent.life <= 12:           # ← magic number 12
if mana >= 4:                     # ← magic number 4 (use card.cmc instead)
score = 50                        # ← arbitrary score
if win_rate > 0.6:                # ← invented threshold
if len(hand) >= 3:                # ← arbitrary hand size
if turn >= 5:                     # ← arbitrary turn number
if power >= 4:                    # ← magic power threshold
DAMAGE_THRESHOLD = 8              # ← named but still arbitrary
if storm_count >= 10:             # ← magic storm count
if len(creatures) > 2:            # ← arbitrary board count
```

**ALLOWED patterns — derive everything from game state:**
```python
# Compare to actual card properties
if mana >= card.cmc:
if mana >= c.cmc + (1 if thalia_out else 0):
effective_cost = max(c.cmc, 3) if trinisphere else c.cmc

# Derive from board state
lethal = sum(c.power for c in player.battlefield if c.is_creature())
if lethal >= opponent.life:

# Derive from hand contents
has_followup = any(c.cmc <= mana - spell.cmc for c in hand if c != spell)
can_combo = has_enabler and has_payoff

# Use card tags and properties
is_removal = c.tag in ('bolt', 'push', 'stp', 'dismember')
is_threat = c.is_creature() or c.tag in ('jace', 'teferi')
biggest_threat = max(opponent.battlefield, key=lambda p: p.power, default=None)

# Mana arithmetic from the cards themselves
ritual_net = 3 - c.cmc  # Dark Ritual: pay 1, get BBB = net 2
can_chain = mana + ritual_net >= next_spell.cmc

# Count-based but from game objects
lands_in_play = sum(1 for p in player.battlefield if p.is_land)
creatures_in_play = [p for p in player.battlefield if p.is_creature()]
```

### 3. Verify tests pass
```bash
python3 -c "from sim import run_rules_tests; run_rules_tests()"
```
Must print `147 passed, 0 failed`. This is the baseline. Every iteration must maintain this.

### 4. Run baseline sweeps
```python
python3 -c "
from sim import run_sweep
targets = [
    ('storm','dnt'),('storm','ur_delver'),('storm','ocelot'),
    ('doomsday','dimir'),('doomsday','ocelot'),
    ('painter','ocelot'),('painter','dimir'),('painter','doomsday'),('painter','oops'),
    ('show','ocelot'),('show','dimir'),
    ('reanimator','ocelot'),('reanimator','oops'),('reanimator','ur_delver'),
    ('belcher','ocelot'),('belcher','dimir'),('belcher','ur_delver'),
    ('goblins','oops'),('goblins','dimir_b'),
    ('prison','oops'),('prison','ocelot'),
    ('eight_cast','dimir'),('eight_cast','oops'),
    ('cephalid','ocelot'),
    ('wan_shi_tong','ocelot'),
    ('lands','doomsday'),
    ('ur_aggro','ocelot'),
    ('elves','oops'),
    ('mardu','oops'),
    ('ocelot','oops'),
    ('boros','ur_delver'),
    ('cloudpost','doomsday'),('cloudpost','oops'),
    ('mono_black','oops'),
]
for d,o in targets:
    s = run_sweep(d, o, n_games=200)
    print(f'{d:15s} vs {o:15s}: {s[\"p1_wr\"]:.1%}')
"
```
Save full output to `overnight_log.md` under `## Baseline`.

---

## Architecture: Where Strategies Live

**Wrapper decks** (delegate to `engine.py`):
Storm, Doomsday, Painter, Show, Reanimator, BUG, Dimir, DNT, Ocelot, Mono Black,
Boros, Eldrazi, Lands, Oops, Prison, UWx, UR Aggro, Mardu.
→ Edit `_strategy_DECKNAME()` in **engine.py**

**Self-contained decks** (full strategy in module):
Goblins, Eight Cast, Affinity, Burn, Cephalid, Cloudpost, Depths, Dimir B/C/D,
Dimir Flash, Elves, Infect, Sneak A/B, TES, UR Delver, UR Tempo, Wan Shi Tong, Belcher.
→ Edit strategy in **decks/DECKNAME.py**

Check with: `head -5 decks/DECKNAME.py` — "wrapper" → engine.py, else → decks/*.py.

---

## Constraints (HARD — violating any of these = immediate revert)

1. **ZERO hardcoded numbers in new code.** Every numeric value must trace to a card
   property (.cmc, .power, .toughness), a game state value (opponent.life, mana,
   len(hand)), or a config.py constant. See examples above.
2. **Max 20 lines changed per iteration.** Check: `git diff --stat`.
3. **Edit only strategy code**: `engine.py` strategy functions OR `decks/*.py` strategy
   functions. Never: `sim.py`, `game.py`, `rules.py`, `cards.py`, `config.py`,
   `deck_registry.py`.
4. **Tests must stay at 147/0.** If count changes → revert → log → continue to next.
5. **Never touch Burn** — hand-tuned and correct.
6. **Never re-run the matrix.** Use `run_sweep()` only.
7. **No new imports** except from modules already imported in the target file.
8. **No new files.** Only modify existing.
9. **No changes to mulligan/keep functions.** Strategy only.

---

## Target List (34 matchups, sorted by meta-weighted impact)

Each row shows the **specific matchup WR from the matrix** (not deck average).

| # | Deck | vs Opponent | Matrix WR | Opp Meta | Notes |
|---|------|------------|-----------|----------|-------|
| 1 | wan_shi_tong | ocelot | 26% | 12% | Biggest meta-weighted gap |
| 2 | painter | ocelot | 29% | 12% | Combo vs tempo |
| 3 | cephalid | ocelot | 30% | 12% | Combo race |
| 4 | belcher | ocelot | 31% | 12% | Speed check |
| 5 | show | ocelot | 33% | 12% | S&T fatty deployment |
| 6 | reanimator | ocelot | 36% | 12% | Combo vs interaction |
| 7 | ur_aggro | ocelot | 37% | 12% | Aggro sizing |
| 8 | boros | ur_delver | 25% | 6% | Aggro mirror |
| 9 | doomsday | dimir | 25% | 6% | Combo vs tempo |
| 10 | cloudpost | doomsday | 26% | 6% | Ramp vs combo |
| 11 | prison | oops | 26% | 6% | Lock speed vs T1 combo |
| 12 | goblins | oops | 27% | 6% | Tribal vs combo |
| 13 | painter | doomsday | 27% | 6% | Combo mirror |
| 14 | painter | oops | 28% | 6% | Combo race |
| 15 | goblins | dimir_b | 25% | 5% | Tribal vs tempo |
| 16 | belcher | dimir | 30% | 6% | All-in vs interaction |
| 17 | belcher | ur_delver | 30% | 6% | All-in vs counters |
| 18 | reanimator | oops | 30% | 6% | Combo race |
| 19 | reanimator | ur_delver | 30% | 6% | Combo vs tempo |
| 20 | storm | ocelot | 40% | 12% | Combo vs tempo |
| 21 | lands | doomsday | 31% | 6% | Land-combo vs spell-combo |
| 22 | storm | ur_delver | 31% | 6% | Combo vs counters |
| 23 | prison | ocelot | 41% | 12% | Lock vs tempo |
| 24 | eight_cast | dimir | 33% | 6% | Artifact vs tempo |
| 25 | eight_cast | oops | 33% | 6% | Artifact vs combo |
| 26 | elves | oops | 33% | 6% | Tribal-combo vs combo |
| 27 | mardu | oops | 33% | 6% | Aggro vs combo |
| 28 | painter | dimir | 32% | 6% | Combo vs tempo |
| 29 | doomsday | ocelot | 42% | 12% | Combo vs tempo |
| 30 | ocelot | oops | 34% | 6% | Tempo vs combo |
| 31 | storm | dnt | 45% | n/a | PLANNING.md P0 outlier |
| 32 | mono_black | oops | 31% | 6% | Aggro vs combo |
| 33 | cloudpost | oops | 32% | 6% | Ramp vs combo |
| 34 | boros | oops | 32% | 6% | Aggro vs combo |

---

## Iteration Loop (target: ~10 min per iteration = ~36-40 iterations in 6h)

### Step 1: Diagnose with 5 verbose games
```python
import random
from sim import run_game

for seed in [42, 99, 7, 123, 256]:
    random.seed(seed)
    r = run_game('DECK', 'OPPONENT', verbose=True)
    print(f"\n{'='*60}")
    print(f"Seed {seed}: {r.winner} T{r.kill_turn} — {r.win_reason}")
    print(f"P1 hand: {r.p1_opening_hand}")
    print(f"{'='*60}")
    # Print key lines: plays, combat, life changes
    for line in r.log_lines:
        if any(kw in line.lower() for kw in ['cast', 'play', 'attack', 'damage', 'life', 'counter', 'discard', 'tutor', 'combo', 'win', 'lock']):
            print(line)
```

**Scan for these fixable patterns (check ALL 5 games):**

A. **Card never cast despite mana available** — the strategy function has no branch
   to deploy this card. Fix: add a cast branch using `card.cmc` for the cost check.

B. **Win condition assembled but not fired** — e.g., has both combo pieces but
   strategy doesn't check for the combination. Fix: add a combo-check branch.

C. **Removal in hand, opponent has creatures, no removal cast** — strategy doesn't
   have a removal-on-threat branch. Fix: add removal using `card.cmc` for cost and
   `opponent.battlefield` for target selection via `.power`.

D. **Cantrips not cast under tax** — Thalia/Trinisphere present, strategy skips
   cantrips because it checks `card.cmc` instead of `card.cmc + tax`. Fix: add
   tax-aware cost calculation.

E. **Fast mana cracked with no follow-up** — Petal/Ritual used but no spell follows.
   This is the combo gate pattern. Fix: check for follow-up spell before cracking.

F. **Creature deployed but never attacks** — board clock wasted. Usually a flag or
   sickness issue.

**If no clear pattern across 5 games → SKIP to next target.** Don't force a fix.
Log: "Skipped: no clear tactical gap in 5 games."

### Step 2: Identify the file and function
```bash
head -5 decks/DECK.py
# wrapper → engine.py _strategy_DECK
# self-contained → decks/DECK.py, find the strategy function
```

Read the relevant strategy function. Understand the existing logic before changing it.

### Step 3: Write the fix (ZERO hardcoded numbers)
- Add ONE branch addressing the diagnosed pattern.
- Max 20 lines.
- All cost checks use `card.cmc`, `card.mana_cost`, game state.
- All targeting uses card/permanent properties (`.power`, `.toughness`, `.is_creature()`).
- All comparisons are against game-state derived values (`opponent.life`, `mana`, `len(hand)`).

### Step 4: Hardcoding audit (MANDATORY before testing)
```bash
# Show the diff
git diff

# Scan new lines for bare numbers (excluding 0, 1, and card.cmc references)
git diff | grep '^+' | grep -v '^+++' | grep -v '#' | grep -E '\b[2-9][0-9]*\b|\b0\.[0-9]+\b' || echo "CLEAN: no suspicious numbers"
```

**If the grep finds bare numbers in new code → check each one:**
- Is it a card CMC referenced via `card.cmc`? → OK
- Is it derived from `len(something)` or `sum(something)`? → OK
- Is it the number 3 in `max(cmc, 3)` for Trinisphere? → OK (CR 601.2f, documented)
- Otherwise → **REVERT. Do not commit hardcoded numbers.**

### Step 5: Test
```bash
python3 -c "from sim import run_rules_tests; run_rules_tests()" 2>&1 | tail -3
```
Must say `147 passed, 0 failed`. If not → `git checkout engine.py decks/` → log → next target.

### Step 6: Measure
```python
from sim import run_sweep

# Primary
s = run_sweep('DECK', 'OPPONENT', n_games=300)
print(f"Primary: {s['p1_wr']:.1%} (n=300)")

# Regression checks: 2 other T1/T2 opponents
for opp in ['dimir', 'ocelot']:
    if opp != 'OPPONENT' and opp != 'DECK':
        s2 = run_sweep('DECK', opp, n_games=200)
        print(f"Check vs {opp}: {s2['p1_wr']:.1%} (n=200)")
```

**Accept if:** primary improved ≥2pp AND no regression check dropped >5pp.
**Reject if:** no improvement or regression detected.

### Step 7: Commit or revert
```bash
# Accept:
git add -A
git commit -m "overnight: DECK — DESCRIPTION [+Xpp vs OPPONENT]"

# Reject:
git checkout engine.py decks/
```

### Step 8: Log to overnight_log.md
```
## Iteration N — DECK vs OPPONENT (COMMITTED/REVERTED/SKIPPED)
- **File**: engine.py _strategy_X / decks/X.py
- **Pattern**: [A-F from checklist, or "none found"]
- **Fix**: [description of branch added]
- **Hardcode audit**: CLEAN / found X (reverted)
- **Lines changed**: N
- **Before**: X.X% (n=300)
- **After**: Y.Y% (n=300)
- **Regression checks**: vs A: X%, vs B: Y%
- **Delta**: +Zpp / no change
- **Commit**: [hash] / reverted / skipped
```

---

## Pacing and Stop Conditions

**Target pace:** ~10 min per iteration (diagnosis 4min + fix 2min + test+measure 4min).
34 targets × 10 min = ~5.5 hours + baseline + final = ~6-7 hours.

**Stop conditions:**
1. All 34 targets attempted → final summary → stop
2. Test count deviates from 147 → revert last change → stop
3. 5 consecutive skips with pattern "no clear tactical gap" → the remaining targets
   are likely structural, not tactical → stop

**Do NOT stop for:** a single revert, a single skip, or slow progress. Keep working
through the list.

---

## Final Steps (always, even after early stop)

```bash
# 1. Verify clean
python3 -c "from sim import run_rules_tests; run_rules_tests()"

# 2. Final sweep of all committed decks
# (run sweep for each deck that got a committed fix, vs its target opponent)

# 3. Scan ALL committed code for hardcoded numbers one final time
git diff HEAD~N -- engine.py decks/ | grep '^+' | grep -v '^+++' | grep -v '#' | \
  grep -E '\b[2-9][0-9]*\b|\b0\.[0-9]+\b'
# If anything found → revert that specific commit

# 4. Summary in overnight_log.md
```

Append to overnight_log.md:
```
## === OVERNIGHT RUN v3 COMPLETE ===
- Total iterations: N
- Committed fixes: N
- Reverted: N (reason for each)
- Skipped: N
- Net WR impact: list each committed fix with before/after
- Hardcode violations caught: N
- Test count: 147/0 confirmed
- Runtime: ~Xh Ym
```

---

## Anti-Patterns (NEVER)
- Never write `if X <= 12` or `score = 50` or `threshold = 0.4` — derive from game state
- Never invent a constant and name it to disguise hardcoding (e.g., `AGGRO_THRESHOLD = 8`)
- Never add cards to decklists
- Never change mana calculation mechanics
- Never nerf an opponent's strategy to improve a matchup
- Never chain multiple fixes before testing
- Never spend >12 minutes on one target — skip and move on
- Never edit sim.py, game.py, rules.py, cards.py, config.py, deck_registry.py
- Never create new files
- Never change mulligan/keep functions
- Never touch Burn strategy
- Never re-run the matrix
