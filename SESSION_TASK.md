# SESSION_TASK.md — Full Architecture Session: Turn Unification + Cast Pipeline + Re-sim

## Overview

Three phases, in order. Each builds on the previous.

| Phase | Task | Estimated Time | Risk |
|-------|------|---------------|------|
| A | Unify response functions | 30-45 min | Low |
| B | Route all spells through cast_spell() | 3-5 hours | Medium |
| C | Re-sim matrix at n=500 + rebuild all outputs | 20-30 min | None |

**Total: ~5-7 hours.**

---

## Required Reading (before any work)
```bash
cat CLAUDE.md
cat PLANNING.md
```

## Constraints (ALL phases)
- Test baseline: `147 passed, 0 failed` — maintain throughout
- Run tests after EVERY file save: `python3 -c "from sim import run_rules_tests; run_rules_tests()"`
- Commit after each successfully completed sub-task
- **No hardcoded numbers** in any new or changed code (see CLAUDE.md §4)
- Never change game rules logic (`rules.py`, `game.py`) unless a bug is discovered
- Never change decklists (`cards.py`, deck constructors in `decks/*.py`)
- Git commit format: `refactor: [phase] [what] [impact if measurable]`

---

# PHASE A — Unify Response Functions (~30-45 min)

## Problem

Two separate functions handle instant-speed responses:
- `_p1_respond_on_opp_turn(gs, log_fn, log_entries)` — engine.py:1919 (67 lines)
- `_p2_respond_on_pro_turn(gs, log_fn, log_entries)` — engine.py:1986 (~80 lines)

P1's version handles: STP, Flash Bowmasters, Force of Vigor, Wasteland.
P2's version handles: STP, Fatal Push, Snuff Out, Lightning Bolt, Maze of Ith.

This asymmetry means P1 never uses Push/Bolt/Snuff even if its deck has them,
and P2 never uses Bowmasters flash / Force of Vigor / Wasteland.

## Fix

Create one unified function:
```python
def _respond_on_opponent_turn(responder, active, gs, log_fn, log_entries):
    """
    Instant-speed responses during the opponent's turn.
    responder = the player responding (has priority)
    active = the player whose turn it is
    """
```

This function checks what `responder` actually has in hand and uses it,
regardless of whether responder is P1 or P2.

### Steps

1. **Read both functions carefully.** Note every interaction they handle.

2. **Create `_respond_on_opponent_turn`** that handles ALL interactions from BOTH functions:
   - STP on biggest creature (power >= responder's STP threshold — use `c.power` comparison)
   - Fatal Push on valid targets (CMC check via `MTGRules.fatal_push_valid_target`)
   - Snuff Out (free with Swamp, pay 4 life — use `CT.SNUFF_LIFE_FLOOR_AGGRO`)
   - Lightning Bolt / Heat on creatures (3 damage vs toughness)
   - Flash Bowmasters (deploy on opponent's end step)
   - Force of Vigor (free, destroy lock pieces)
   - Wasteland (destroy nonbasic land)
   - Maze of Ith (if present in the old code, include it)

3. **Use card properties for ALL targeting decisions.** Never hardcode "if P1 then X":
   - `responder.find_tag('stp')` — not `gs.p1.find_tag('stp')`
   - `active.creatures` — not `gs.p2.creatures`
   - `responder.available_mana_count()` for cost checks

4. **Replace the call site in `sim.py`** (around line 720-726):
   ```python
   # OLD:
   if who == 'p1':
       from engine import _p2_respond_on_pro_turn
       _p2_respond_on_pro_turn(gs, log, log_entries)
   else:
       from engine import _p1_respond_on_opp_turn
       _p1_respond_on_opp_turn(gs, log, log_entries)

   # NEW:
   from engine import _respond_on_opponent_turn
   # responder = the player who is NOT the active player
   responder = gs.p2 if who == 'p1' else gs.p1
   active_player = gs.p1 if who == 'p1' else gs.p2
   _respond_on_opponent_turn(responder, active_player, gs, log, log_entries)
   ```

5. **Keep old functions as deprecated wrappers** (for safety, remove in a later PR):
   ```python
   def _p1_respond_on_opp_turn(gs, log_fn, log_entries):
       _respond_on_opponent_turn(gs.p1, gs.p2, gs, log_fn, log_entries)

   def _p2_respond_on_pro_turn(gs, log_fn, log_entries):
       _respond_on_opponent_turn(gs.p2, gs.p1, gs, log_fn, log_entries)
   ```

6. **Test:** 147/0. Then run symmetry spot-checks:
   ```python
   from sim import run_sweep
   # These should now be more symmetric
   for d1, d2 in [('dimir', 'dimir_b'), ('ur_delver', 'burn'), ('bug', 'storm')]:
       s1 = run_sweep(d1, d2, n_games=200)
       s2 = run_sweep(d2, d1, n_games=200)
       total = s1['p1_wr'] + s2['p1_wr']
       print(f"{d1} vs {d2}: {s1['p1_wr']:.1%} + {s2['p1_wr']:.1%} = {total:.0%} (ideal: ~100%)")
   ```

7. **Commit:** `git commit -am "refactor: A — unified _respond_on_opponent_turn [symmetry fix]"`

---

# PHASE B — Route All Spells Through cast_spell() (~3-5 hours)

## Problem

157 direct spell casts in engine.py strategies + ~200 in decks/*.py bypass `cast_spell()`.
This means Eidolon triggers on ~50% of opponent spells instead of 100%.

## The cast_spell() API

```python
def cast_spell(player, opponent, gs, card, mana_budget, log_fn, log_entries,
               on_resolve=None, on_counter=None, cost_override=None) -> bool:
```

- `mana_budget`: **mutable list** `[int]` — `mana_budget[0]` is deducted on resolve.
  Pass `None` for free spells (FoW, FoN, Daze returning land).
- `on_resolve`: callback when spell resolves. Examples:
  - Creature: `on_resolve=lambda c: player.put_creature_in_play(c)`
  - Artifact: `on_resolve=lambda c: player.put_artifact_in_play(c)`
  - Instant/sorcery: `on_resolve=None` (default: goes to GY)
  - Cantrip: `on_resolve=lambda c: (player.add_to_grave(c), resolve_cantrip(player, c, gs, log_fn, log_entries))`
- `on_counter`: callback when countered. Default: card goes to GY.
- Returns `True` if resolved, `False` if countered.

## Conversion Pattern

**BEFORE (direct cast):**
```python
bolt = player.find_tag('bolt')
if bolt and mana >= bolt.cmc:
    player.remove_from_hand(bolt)
    if not _try_counter_any(player, opponent, gs, bolt, log_entries):
        opponent.life -= 3
        mana -= bolt.cmc
        player.add_to_grave(bolt)
        log_fn("Lightning Bolt → 3 damage", True)
    else:
        player.add_to_grave(bolt)
```

**AFTER (through cast_spell):**
```python
bolt = player.find_tag('bolt')
if bolt and budget[0] >= bolt.cmc:
    def _resolve_bolt(c):
        opponent.life -= 3
        player.add_to_grave(c)
        log_fn("Lightning Bolt → 3 damage", True)
    cast_spell(player, opponent, gs, bolt, budget, log_fn, log_entries,
               on_resolve=_resolve_bolt)
```

**Key differences:**
1. `cast_spell` calls `player.remove_from_hand(card)` internally — DON'T do it before calling
2. Use `budget = [mana]` (mutable list) instead of bare `mana` int
3. Eidolon and counter window happen automatically
4. Check return value if you need to know if it resolved

## Important: What NOT to convert

Not every `remove_from_hand` is a spell cast. **DO NOT** route these through cast_spell():
- **Land plays**: `player.remove_from_hand(land); player.lands.append(LandPermanent(land))`
- **Free exiles**: FoW/FoN pitch cards (the pitched card, not the spell itself)
- **Dredge/discard**: cards moved to GY without being cast
- **Artifact activation**: Petal crack, LED crack (activation, not cast)
- **Suspend exile**: Rift Bolt going to exile
- **Cascade/free cast from exile**: cards already removed from hand elsewhere

**RULE: If the card is being CAST (paying mana, going on the stack), route through cast_spell().
If the card is being moved for any other reason, leave it as-is.**

## Work Order (one strategy at a time, test between each)

Process strategies from smallest to largest to build confidence:

### Batch 1 — engine.py strategies (157 casts)
```
_strategy_lands           2 casts
_strategy_ur_aggro        4 casts
_strategy_eldrazi         5 casts
_strategy_dimir_flash     5 casts
_strategy_dnt             6 casts
_strategy_dimir           7 casts
_strategy_uwx             7 casts
_strategy_painter         7 casts  (JUST COMMITTED — be careful)
_strategy_storm           7 casts
_strategy_reanimator      7 casts
_strategy_ocelot          7 casts
_strategy_mono_black      8 casts
_strategy_boros           8 casts
_strategy_mardu           9 casts
_strategy_doomsday        9 casts
_strategy_prison         11 casts
_strategy_oops           12 casts
_strategy_show           13 casts
_strategy_bug            23 casts
```

### Batch 2 — decks/*.py strategies (~200 casts)
```
burn                1 cast   (SKIP — hand-tuned, only convert if trivial)
dimir_flash         5 casts
eldrazi             6 casts
ur_delver           7 casts
ur_tempo            7 casts
uwx                 7 casts
wan_shi_tong         8 casts
sneak_a             8 casts
eight_cast          8 casts
cephalid           10 casts
sneak_b            10 casts
dimir_c            10 casts
dimir_d            11 casts
depths             12 casts
cloudpost          12 casts
goblins            12 casts
infect             12 casts
affinity           13 casts
belcher            16 casts
tes                33 casts
```

### Per-strategy workflow

For EACH strategy function:

1. **Read the function.** Identify every `remove_from_hand` call.
2. **Classify each one:** spell cast (convert) vs land/discard/activation (skip).
3. **Convert spell casts** to `cast_spell()` pattern. Key decisions:
   - Does the strategy use a bare `mana` int? → Wrap in `budget = [mana]` at top,
     and read back `mana = budget[0]` when needed for subsequent checks.
   - Does the function already have a `budget` variable? → Use it directly.
   - Is `cast_spell` already imported in the file? If not, add import at function top.
4. **Test:** `python3 -c "from sim import run_rules_tests; run_rules_tests()"`
   Must stay at 147/0.
5. **Quick WR check** (only if test passes):
   ```python
   from sim import run_sweep
   s = run_sweep('DECK', 'burn', n_games=100)
   print(f"vs burn: {s['p1_wr']:.1%}")
   ```
   WR should stay within ±5pp of baseline. Eidolon-sensitive matchups (vs burn) may DECREASE
   because spells now correctly trigger Eidolon — that's expected and correct.
6. **Commit:** `git commit -am "refactor: B — DECKNAME cast_spell() pipeline [N casts converted]"`

### Budget variable management

Many strategies use a bare `mana` integer. The cleanest conversion:

```python
def _strategy_example(player, opponent, gs, total_mana, log_fn, log_entries):
    budget = [total_mana]  # ← ADD THIS at the top
    # ... all existing code, but replace:
    #   mana >= card.cmc          →  budget[0] >= card.cmc
    #   mana -= card.cmc          →  (handled by cast_spell)
    #   player.remove_from_hand() →  (handled by cast_spell)
    # ... at end, if strategy returns mana:
    # total_mana = budget[0]  # ← sync back if needed
```

If the strategy already uses `budget = [total_mana]` (e.g. _strategy_bug), just use it.

### Handling complex patterns

**Ritual chains (Storm, TES, Doomsday):**
```python
# Ritual produces mana — on_resolve adds net mana to budget
def _resolve_ritual(c):
    player.add_to_grave(c)
    budget[0] += 3  # BBB from Dark Ritual (net = +3 - 1 cmc = +2, but cast_spell deducts cmc)
    # Actually: cast_spell deducts c.cmc (1), so budget goes down 1 then up 3 = net +2
    # Simpler: use cost_override or just add the ritual's produce amount
```

Wait — `cast_spell` deducts `card.cmc` from `budget[0]`. For Dark Ritual (cmc=1, produces BBB=3):
- cast_spell deducts 1 from budget
- on_resolve adds 3 to budget
- Net: +2 to budget ✓

**Creatures/artifacts to play:**
```python
cast_spell(player, opponent, gs, creature_card, budget, log_fn, log_entries,
           on_resolve=lambda c: player.put_creature_in_play(c))
```

**Cantrips (Brainstorm, Ponder):**
```python
from engine import resolve_cantrip
cast_spell(player, opponent, gs, cantrip, budget, log_fn, log_entries,
           on_resolve=lambda c: (player.add_to_grave(c),
                                  resolve_cantrip(player, c, gs, log_fn, log_entries)))
```

**Free spells (FoW cast, not the pitch):**
```python
# FoW: alternative cost = exile blue card + pay 1 life
# The FoW card itself is the spell being cast. Pass mana_budget=None (free).
cast_spell(player, opponent, gs, fow_card, None, log_fn, log_entries,
           on_resolve=lambda c: player.add_to_grave(c))
# The pitched card is NOT a spell — just exile it directly (no cast_spell)
```

### Verification after all conversions

After ALL strategies are converted:

```python
# Full Eidolon verification
from sim import run_sweep
# Burn should now trigger Eidolon on ~100% of opponent spells
for opp in ['storm', 'doomsday', 'oops', 'dimir', 'elves']:
    s = run_sweep('burn', opp, n_games=200)
    print(f"burn vs {opp}: {s['p1_wr']:.1%}")
```

Run full test suite one more time, then commit:
`git commit -am "refactor: B — cast_spell() pipeline complete [357 casts converted]"`

---

# PHASE C — High-N Matrix Re-sim + Full Rebuild (~20-30 min)

## Steps

After A and B are committed and tested:

```bash
# 1. Full re-sim at n=500
python3 refresh_all.py --resim 500
# This takes ~15-20 min. Generates:
#   - results/matrix_*.json (new matrix)
#   - results/meta_matrix_*.html (dashboard)
#   - guides/*.html (all 36 guides)
#   - Runs verify.py

# 2. Verify
python3 -c "from sim import run_rules_tests; run_rules_tests()"

# 3. Commit results
git add -A
git commit -m "refactor: C — n=500 matrix re-sim, all outputs rebuilt"
```

## Expected Changes

- Tighter confidence intervals: ±3.9% → ±2.5%
- Burn matchups may shift because Eidolon now fires on all opponent spells
- Symmetry should improve from Phase A (response function unification)
- Some WRs will shift slightly from n=200 due to better statistical resolution

---

# Session Log

Log progress to `session_log.md`:

```
# Architecture Session — A + B + C (date)

## Phase A: Response Function Unification
- Start: [time]
- Functions unified: _p1_respond_on_opp_turn + _p2_respond_on_pro_turn → _respond_on_opponent_turn
- Interactions covered: [list]
- Tests: 147/0
- Symmetry before: [dimir vs dimir_b sum]
- Symmetry after: [dimir vs dimir_b sum]
- Commit: [hash]
- End: [time]

## Phase B: cast_spell() Pipeline
- Start: [time]
- Strategies converted: [count]/[total]
- Total casts routed: [count]
- Tests maintained: 147/0 throughout
- Eidolon verification: burn vs storm [before]% → [after]%
- Commits: [list of hashes]
- End: [time]

## Phase C: n=500 Re-sim
- Start: [time]
- Matrix file: results/matrix_*.json
- Tests: 147/0
- Commit: [hash]
- End: [time]

## Summary
- Total commits: N
- Total time: Xh Ym
- Key WR changes: [list significant shifts]
```

---

# Stop Conditions

- **Test failure:** Revert last change, debug, fix, continue. If >3 test failures in a row, stop and log.
- **Phase A breaks symmetry worse:** Revert, log, skip to Phase B.
- **Phase B conversion breaks a strategy:** Revert that one strategy, log, continue with next.
- **Clock:** If running >7 hours, commit whatever is done and stop cleanly.

# Anti-Patterns
- Never hardcode P1/P2 in the unified response function — use responder/active
- Never call remove_from_hand before cast_spell — it does it internally
- Never route land plays through cast_spell
- Never route activation costs (Petal crack, LED crack) through cast_spell
- Never change the cast_spell() function signature itself
- Never skip testing between strategy conversions
- Never batch multiple strategy conversions into one untested commit
