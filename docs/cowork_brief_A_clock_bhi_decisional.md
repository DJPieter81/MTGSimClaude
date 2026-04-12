# Cowork Brief A: clock + BHI decisional adoption

## One-sentence task
Replace hardcoded go-face / combo-fire thresholds with `clock.board_clock()` and `bhi.HandBelief` reads, so the two helpers that were ported earlier actually drive decisions instead of just logging.

## Why this matters
Current state: `clock.py` and `bhi.py` exist and are instrumented into trace output, but no strategy actually *uses* them to change behaviour. Every existing decision still uses hardcoded numbers that violate CLAUDE.md §"Key Design Principles" #4.

Offending call sites (grep-verified before the brief):

```python
# engine.py:3191 — Burn go-face threshold
go_face = lethal_with_bolts or opponent.life <= 12 or not any(...)

# engine.py:5294 — UR Aggro bolt face threshold
go_face = (target is None and opponent.life <= 15 and len(player.creatures) > 0)

# engine.py:~4494 — Storm opp_has_free_counter threshold inside BHI wrap
opp_has_free_counter = belief.p_free_counter > 0.4   # 0.4 is a magic constant
```

The `0.4` and `<= 12` / `<= 15` numbers are invented — they should be derived from game state (clock-delta math) or lifted to `config.InteractionParams` as named constants.

## Scope

### Part 1 — Clock-based go-face for Burn + UR Aggro + UR Delver

For each of the three aggro decks, replace the `opponent.life <= N` check with:

```python
from clock import board_clock
# How many turns until current board kills them?
current_clock = board_clock(player.creatures, opponent.creatures, opponent.life)
# How many turns after a 3-damage burn spell?
bolt_clock = board_clock(player.creatures, opponent.creatures, opponent.life - 3)
# Go face if the bolt shortens the clock by at least 1 turn AND no high-value creature target exists
go_face = (target is None) and (bolt_clock < current_clock)
```

This eliminates the magic number and makes the decision deck-state-aware.

### Part 2 — BHI threshold → config constant

Add to `config.py:InteractionParams`:
```python
BHI_FREE_COUNTER_THRESHOLD: float = 0.4   # HandBelief.p_free_counter above
                                          #  which strategies treat opponent
                                          #  as "probably has FoW/FoN+pitch"
BHI_COUNTER_THRESHOLD: float     = 0.55   # likewise for any counter
```

Replace every `p_free_counter > 0.4` call site with `p_free_counter > IP.BHI_FREE_COUNTER_THRESHOLD`. Grep: `bhi` in `engine.py` shows 3 current adoption sites (Storm, Oops, Doomsday); update all.

### Part 3 — Actually gate combo firing on BHI

Storm and Oops currently *log* the BHI reading but don't gate on it. Add:

```python
# _strategy_storm near the combo cast
if p_free_counter > IP.BHI_FREE_COUNTER_THRESHOLD and not veil_protecting:
    if not storm_desperate:
        # Opp probably has a free counter and we're not desperate — wait
        gs.strat_log.log_decision(...)
        return   # skip combo this turn
```

Mirror the pattern in `_strategy_oops` for the Spy/Informer gate.

## Constraints

- **No new magic constants.** Every number must be a Card property, a `config.py` constant, or derived from `board_clock()`.
- Touch only `engine.py`, `config.py`, possibly `clock.py` (to add a helper if needed).
- Run before committing:
  ```
  python3 -c "from sim import run_rules_tests; run_rules_tests()"  # 147/147
  python3 -c "from sim import run_sweep; import random; random.seed(42); print(run_sweep('burn','dimir',200))"
  python3 -c "from sim import run_sweep; import random; random.seed(42); print(run_sweep('storm','dnt',200))"
  python3 -c "from sim import run_sweep; import random; random.seed(42); print(run_sweep('ur_delver','burn',200))"
  ```
- Regression check: no spot-check from `EXPECTED_RANGES` (meta_audit.py Control 9) should drop out of range.

## Expected impact
- Burn go-face decisions become board-state-aware — expect ±3pp shifts in matchups where the board composition was blunted by the hardcoded `<=12` threshold.
- Storm combo timing improves vs dimir / ur_delver (holds back with high p_counter).
- Oops same.

## Branch / PR
- Branch: `claude/mtgsim-clock-bhi-decisional-<suffix>` off main.
- Title: "clock + BHI decisional adoption (no more magic numbers)"
- Commits: split by layer (config, Burn, UR decks, Storm/Oops gates).

## Validation
- `grep -nE 'opponent.life <= [0-9]|p_free_counter > 0\.' engine.py` → zero matches after this PR.
- Traces show `go_face=True reason=bolt_clock=3<current_clock=4`.
- Rules tests 147/147.
