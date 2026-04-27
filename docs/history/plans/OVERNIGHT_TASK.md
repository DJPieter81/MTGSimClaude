# OVERNIGHT_TASK.md — Autonomous Small-Fix Iteration Loop

## Goal
Improve strategy accuracy for underperforming decks by making **one small fix per iteration**, testing, measuring, and committing if positive.

## Required Reading (before any work)
```bash
cat CLAUDE.md    # API, architecture, "Never" list
cat PLANNING.md  # known bugs, priorities, session log
```

## Constraints (HARD)
- **Max 15 lines changed per iteration** (check with `git diff --stat`)
- **Only edit strategy functions** in `engine.py` (lines 1156–5500), never `sim.py` core loop, `game.py`, `rules.py`, or `cards.py`
- **Tests must pass** after every change: `python3 -c "from sim import run_rules_tests; run_rules_tests()"` → 147 passed, 0 failed
- **No hardcoded magic numbers** — use card properties, game state, or `config.py` constants (see CLAUDE.md §4)
- **No new imports** except `random` (already used everywhere)
- **Never touch Burn strategy** — it's hand-tuned and correct
- **Never change the matrix or re-run it** — only sweep individual matchups
- **Git commit each successful fix** with message format: `overnight: [deck] [what] [±Xpp vs opponent]`
- **Stop after 20 iterations OR first test failure OR 3 consecutive no-improvement iterations**

## Target List (priority order)

Work through these deck/matchup pairs in order. Skip to next if no clear fix found within 10 minutes of tracing.

| # | Deck | Target Matchup | Current WR | Expected | Gap |
|---|------|---------------|------------|----------|-----|
| 1 | storm | dnt | 45% | 55-80% | -10pp+ |
| 2 | doomsday | dimir | 33% flat | 40-50% | low |
| 3 | painter | dimir | 35% flat | 45-55% | low |
| 4 | mardu | burn | 36% flat | 42-50% | low |
| 5 | reanimator | dimir | see matrix | 35-65% | borderline |
| 6 | show | dnt | ~40% | 50-60% | low |
| 7 | goblins | dimir | ~40% | 45-55% | low |
| 8 | eight_cast | burn | ~44% | 48-55% | low |

After exhausting this list, scan for any matchup where a deck loses >70% and the loss pattern in verbose output shows a clearly unmodeled interaction.

## Iteration Loop

For each target:

### Step 1: Diagnose (read-only)
```python
# Run 3 verbose games with different seeds to find patterns
import random
from sim import run_game
for seed in [42, 99, 7]:
    random.seed(seed)
    r = run_game('TARGET_DECK', 'OPPONENT', verbose=True)
    print(f"Seed {seed}: {r.winner} T{r.kill_turn} — {r.win_reason}")
    # Scan log_lines for:
    # - Cards in hand that were never cast
    # - Mana left unspent on key turns
    # - Win conditions not deployed
    # - Interaction not used (removal, counters sitting in hand)
    # - Incorrect sequencing (land before cantrip, etc.)
```

**What to look for:**
- Card in hand 3+ turns but never played → missing cast logic
- Mana >= card.cmc but card not cast → missing branch in strategy
- Creature/artifact not deployed despite mana → deploy logic gap
- Removal not used when opponent has threat → missing removal branch
- Cantrip not cast when looking for combo piece → missing cantrip-under-tax logic
- Win condition available but not attempted → combo execution gap

### Step 2: Fix (one branch)
Open `engine.py`, find `_strategy_DECKNAME`, add ONE if/elif branch that addresses the diagnosed issue.

**Pattern examples:**
```python
# Deploy a card that was sitting in hand
if mana >= card.cmc and card_name in [c.name for c in hand]:
    # cast it
    
# Use removal on biggest threat
if removal_in_hand and opponent.battlefield:
    # remove biggest threat

# Cast cantrip under tax (Storm vs Thalia)
effective_cost = max(card.cmc, card.cmc + tax)
if mana >= effective_cost and card.tag == 'cantrip':
    # cast it even under tax
```

### Step 3: Test
```bash
python3 -c "from sim import run_rules_tests; run_rules_tests()"
# MUST print: 147 passed, 0 failed
# If ANY test fails → revert immediately: git checkout engine.py
```

### Step 4: Measure
```python
from sim import run_sweep
s = run_sweep('TARGET_DECK', 'OPPONENT', n_games=200)
print(f"WR: {s['p1_wr']:.1%} (n=200)")
```

Compare to baseline (run sweep BEFORE the fix too). Accept if:
- WR improved by ≥2pp AND
- No other key matchup regressed (spot-check 2 other opponents)

### Step 5: Commit or Revert
```bash
# If improvement:
git add engine.py
git commit -m "overnight: [deck] [what changed] [+Xpp vs opponent]"

# If no improvement or regression:
git checkout engine.py
```

### Step 6: Log
Append to `overnight_log.md` (create if doesn't exist):
```
## Iteration N — DECK vs OPPONENT
- **Diagnosis**: [what was wrong in verbose output]
- **Fix**: [what branch was added, line number]
- **Before**: X.X% (n=200)
- **After**: Y.Y% (n=200)  
- **Delta**: +/-Zpp
- **Result**: COMMITTED / REVERTED / SKIPPED
- **Commit**: [hash or N/A]
```

## Stop Conditions
1. **20 iterations completed** → stop, push, summarize
2. **Test failure** → revert last change, stop, push, summarize
3. **3 consecutive no-improvement iterations** → stop, push, summarize
4. **All 8 targets attempted** → stop, push, summarize

## Final Steps (always)
```bash
# Push all commits
git push origin main

# Run full verification
python3 -c "from sim import run_rules_tests; run_rules_tests()"

# Generate summary
echo "=== OVERNIGHT RUN COMPLETE ===" >> overnight_log.md
echo "Total iterations: N" >> overnight_log.md
echo "Committed fixes: N" >> overnight_log.md
echo "Total WR impact: +Xpp across N matchups" >> overnight_log.md
```

## Anti-Patterns (NEVER do these)
- Don't add a card to a decklist — only fix strategy logic
- Don't change how mana is calculated — only how it's spent
- Don't add new game mechanics — only use existing ones
- Don't "fix" a matchup by nerfing the opponent's strategy
- Don't chain multiple fixes before testing — one fix, one test, one commit
- Don't spend >10 minutes diagnosing one matchup — move to next target
- Don't re-run the matrix — use run_sweep for targeted measurement
