# Cowork Brief: Unify `protagonist_turn` + `opp_turn`

## One-sentence task
Eliminate the P1/P2 turn-function divergence that causes tempo-mirror WRs to sum to ~140% instead of 100%, by extracting both into a shared `_execute_turn()`.

## Why this matters
This is the **root cause of every P1-advantage-inflation outlier** in the symmetry audit. 106 pairs currently have >10% asymmetry; we expect ~60 of those to drop below 10% once the two turn paths are unified. Most immediately:

- `dimir vs dimir_flash`: 145% sum → expected ~110% (the 45% "extra" goes away)
- `dimir_b vs dimir_flash`: 134% → ~108%
- `dimir vs ur_tempo`: 133% → ~110%

## What's already in place
- **Diagnosis doc:** `results/tempo_mirror_root_cause.md` — full analysis with before/after expectations
- `sim.py:325` `protagonist_turn(gs, turn, matchup)` — 294 lines, the "full-featured" path
- `engine.py:1853` `opp_turn(gs, turn, matchup)` — 155 lines, the "legacy" path
- `engine.py:1088` `play_turn(gs, turn, who)` — dispatcher; calls `protagonist_turn` when `who=='p1'`, `opp_turn` when `who=='p2'`
- Symmetry audit baseline: `results/symmetry_audit_20260412.md`
- Both `clock.py` and `bhi.py` available as composable helpers during the refactor

## Scope

### Part 1 — Extract the shared skeleton

Create `sim.py:_execute_turn(gs, turn, player, opponent, matchup)` that contains the full 294-line flow currently in `protagonist_turn`, parameterized by which slot is the active player:

```python
def _execute_turn(gs, turn, player, opponent, matchup):
    """Single code path both P1 and P2 use. All decks, all features."""
    # cleanup → untap → upkeep → draw → land → mana →
    # apply_lock_effects → pre-strategy hooks → strategy dispatch →
    # post-strategy hooks → combat → EOT
    ...
```

Then:
```python
def protagonist_turn(gs, turn, matchup):
    return _execute_turn(gs, turn, gs.p1, gs.p2, matchup)

def opp_turn(gs, turn, matchup):
    return _execute_turn(gs, turn, gs.p2, gs.p1, matchup)
```

### Part 2 — Thread `player` and `opponent` through every hook

The following currently reference `gs.p1` / `gs.p2` directly in ways that assume "p1 is us":

- `bowm_ctrl` logic — needs to derive from which player controls Bowmasters, not slot identity
- `gs.p2_spells_cast_this_turn` — rename to `gs.active_spells_cast_this_turn` or derive from `player`
- `gs.p1_poison` / `gs.p2_poison` — already slot-scoped, keep as-is
- `update_goyf(gs)` — reads both graveyards, already symmetric
- Pre-strategy Thoughtseize / Push / Wasteland activation in `protagonist_turn:484-510` — needs to run for both slots
- Post-strategy Eidolon damage (already centralized in `apply_eidolon_damage`) — verify it works when `player is gs.p2`

### Part 3 — Regression tests

Add unit tests that verify symmetric behavior:
- Run `run_game('dimir', 'dimir_flash', trace=True)` and `run_game('dimir_flash', 'dimir', trace=True)` with the same seed; the number of pre-strategy Thoughtseize casts should match (currently one side gets more).
- Run 100-game sweeps both ways; assert `a + (1-b) < 0.10` for the dimir-mirror pair.

### Part 4 — Full matrix re-run
```bash
python3 refresh_all.py --resim 200 --decks 36
python3 -c "
from meta_results import load_matrix, symmetrise_matrix
out = symmetrise_matrix(load_matrix(), asymmetry_threshold=0.10)
print(f'outliers >10%: {len(out[\"symmetry_warnings\"])}  (was 106)')"
# Expected: <50
```

## Performance budget
- No performance impact expected — same code, different organization
- Matrix re-run at n=200 takes ~5 min
- Full pipeline (refresh_all.py): ~90s excluding matrix re-run

## Branch / PR shape
- Branch: `claude/mtgsim-turn-unification-<suffix>`
- Commits:
  1. Extract `_execute_turn()` in sim.py with BOTH existing paths' logic merged (line-by-line audit)
  2. Replace `protagonist_turn` / `opp_turn` bodies with thin wrappers
  3. Regression tests
  4. Matrix re-run + symmetry audit update
  5. Update `results/tempo_mirror_root_cause.md` with "FIXED" status + before/after WR table

## Validation checklist
- All 144 rules tests pass
- All 5 known spot-checks (burn vs storm, burn vs dimir, infect vs burn, reanimator vs dimir, eldrazi vs storm) stay within their EXPECTED_RANGES
- Dimir-mirror symmetry sum drops from 145% to ≤115%
- Total >10% outlier count drops from 106 to ≤60
- `verify.py all` exits 0
- `run_game('any_deck', 'any_deck')` still completes for all 36 decks (smoke loop)

## Files the cowork session will touch
- MODIFY: `sim.py` (add `_execute_turn`, shrink `protagonist_turn`)
- MODIFY: `engine.py` (shrink `opp_turn` to thin wrapper)
- MAYBE MODIFY: `game.py` — rename `p2_spells_cast_this_turn` → `active_spells_cast_this_turn` with backcompat alias
- MODIFY: `results/tempo_mirror_root_cause.md` — add "FIXED" section
- MODIFY: `PLANNING.md` — close the P1 #1 item

## Starting point
```bash
git fetch origin && git checkout -b claude/mtgsim-turn-unification-<suffix> origin/main

# Read both paths back-to-back
sed -n '325,619p' sim.py > /tmp/prot.py
sed -n '1853,2008p' engine.py > /tmp/opp.py
diff -y /tmp/prot.py /tmp/opp.py | less

# Focus on the differences — each is either:
#   (a) a bug in opp_turn that wasn't backported from the refactor
#   (b) a legitimate P1/P2 difference (e.g. combat phase order on play)
# The refactor's job is to lift (a) into the shared function and keep (b) at the wrapper level.
```

## Risk / escalation
- **High blast radius:** these are the two hottest code paths. Get the diff review right.
- If any spot-check regresses >5pp during the refactor, pause and investigate before continuing.
- Feature flag `gs._unified_turn = True` could gate the new path during development.

## Expected impact
| Metric | Before | Target |
|--------|--------|--------|
| Outlier pairs >10% asymmetric | 106 | ≤60 |
| Dimir vs dimir_flash sum | 145% | ≤115% |
| Average pairwise asymmetry | 12.5pp | ≤8pp |
| Match-weighted mean WR | 49.1% | unchanged (still near-symmetric by construction) |
| Rules tests | 144/144 | 144/144 |
