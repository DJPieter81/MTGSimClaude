# MTG Sim Refactoring Playbook

Reusable patterns and checklists extracted from the Legacy format refactoring. Apply these to any format (Modern, Pioneer, etc.) when building or auditing a simulator.

---

## 1. Symmetric Engine Checklist

- [ ] **No deck-specific routing** in the turn dispatcher. ALL decks go through the same `play_turn → strategy dispatch` path.
- [ ] **P1 and P2 use identical infrastructure** — untap, draw, land, mana calc, combat, EOT are shared. Only the strategy function differs.
- [ ] **Fallback combat for both players** — if a strategy doesn't explicitly declare combat, the turn function attacks with eligible creatures automatically. Use a `gs.combat_this_turn` flag (set by `combat_declare`), not log-string scanning.
- [ ] **Cross-turn interaction hooks** — non-active player gets instant-speed responses (STP, Push, Bolt, flash creatures, Wasteland) after the active player's main phase.
- [ ] **Counter checks on all spell casts** — every creature/spell deployment must call `_try_counter_any()` so the opponent can respond. Audit for strategies with 0 counter checks.

---

## 2. Nine Bug Patterns (Systematic Audit)

Run these checks across ALL decks after any major change:

| # | Pattern | How to Check |
|---|---------|-------------|
| 1 | **Card in deck, never cast by strategy** | Compare deck builder tags vs strategy `find_tag()` calls. Every nonland card should be referenced. |
| 2 | **Creature in wrong permanent list** | Search for `put_artifact_in_play` on creatures or vice versa. Painter's Servant is a creature, not an artifact. |
| 3 | **Strategy references tag not in deck** | Search for `find_tag('X')` where tag X doesn't exist in the deck builder. |
| 4 | **Mana sources not counted** | Mana dorks, Mox, Petals, Treasures must be added to the mana budget. Use `available_mana_count(include_dorks=True)`. |
| 5 | **Double combat** | The `combat_this_turn` flag must be set by `combat_declare`. Verify strategies don't bypass it. |
| 6 | **Missing counter checks** | Count `_try_counter_any` calls per strategy. 0 calls = opponent can't interact. |
| 7 | **Deck size ≠ 60** | `assert len(deck()) == 60` for every deck. |
| 8 | **No win condition path** | Run 10 games vs a weak opponent. If 0 wins, the strategy can't close games. |
| 9 | **No keep function** | Every deck in the registry needs a custom mulligan keep function. |

---

## 3. Constants & Hardcoding Rules

**Move to config.py if:**
- Used in 2+ files, OR
- Is a tunable calibration knob (life threshold, probability, turn cap)

**Keep local if:**
- Single-use inside one strategy function
- Is a card mechanic (e.g., Thespian's Stage costs 2 mana to activate)

**Config class pattern:**
```python
class GameRules:
    MAX_TURNS = 15
    STARTING_LIFE = 20

class CombatThresholds:
    DESPERATE_LIFE = 8
    HOLD_ATTACK_TAGS = frozenset({'bowm', 'tamiyo'})

GR = GameRules   # short alias
CT = CombatThresholds
```

---

## 4. Dead Code Detection

After refactoring, check for orphaned code:

```bash
# Find all function defs
grep -n "^def " engine.py | while read line; do
  fname=$(echo "$line" | sed 's/.*def //' | sed 's/(.*//') 
  calls=$(grep -c "$fname" engine.py)
  if [ "$calls" -le 1 ]; then
    echo "DEAD: $fname (only the def, no callers)"
  fi
done
```

Common dead code sources:
- `_opp_*` wrapper functions replaced by registry dispatch
- Legacy `STRATEGIES` dicts superseded by deck_registry
- Helper functions that lost their only caller during refactoring

---

## 5. Combo Deck Win Condition Checklist

Every combo deck needs ALL of these:

- [ ] **Combo pieces in the decklist** (sounds obvious, but TES was missing Empty the Warrens)
- [ ] **Strategy assembles the combo** (tutors, draws, deploys pieces in order)
- [ ] **Win condition resolves** (set `gs.game_over = True`, `gs.winner`, `gs.win_reason`, `gs.kill_turn`)
- [ ] **Post-combo cleanup** (Narcomoeba from GY, Oracle ETB, Storm copies, Belcher activation)
- [ ] **Opponent gets to interact** (FoW on the combo spell, Surgical on GY pieces, Endurance on Reanimate target)

---

## 6. Balance Audit Flow

```
1. Run full matrix (100 games/matchup)
2. Flag decks > 65% or < 35% meta-EV
3. For each outlier, launch trace audit:
   - Trace 5 games vs a representative opponent
   - Check: kill turn, damage per turn, creatures answered/unanswered
   - Compare to real tournament data (mtgtop8.com)
4. Root cause categories:
   - DECKLIST: missing key card → add it
   - STRATEGY BUG: code error (wrong variable, missing check) → fix
   - MISSING MECHANIC: card in deck but ability unimplemented → implement
   - TUNING: strategy works but thresholds are off → adjust config constant
5. Fix, re-run sweep for affected matchups, verify improvement
6. Re-run full matrix to check for ripple effects
```

---

## 7. Test Expansion Template

For any new mechanic, add a test in `run_rules_tests()`:

```python
# ── [Mechanic Name]: [what it does] ──
gs_test = GameState(
    p1=PS_(name='b', hand=[], library=[], life=20),
    p2=PS_(name='o', hand=[], library=[], life=20))
# Set up the specific board state
gs_test.some_flag = True
# Execute the mechanic
result = some_function(gs_test, ...)
# Assert
test("[Mechanic]: [specific behavior]", result, expected_value)
```

Always test both the positive AND negative case (mechanic triggers vs doesn't trigger).

---

## 8. Parallel Agent Workflow

For large audits, launch 10-20 focused agents simultaneously:

```
Agent per deck (haiku model for speed):
- Read deck builder + strategy
- Run trace games
- Report: missing cards, broken mechanics, strategy gaps
- Under 200 words each

Then compile findings into categories:
- CRITICAL BUGS (code errors)
- MISSING CARDS (decklist gaps)  
- UNIMPLEMENTED MECHANICS
- STRATEGY TUNING
```

Fix in parallel using worktree isolation for independent files, sequential for shared files (engine.py).
