# Cowork Brief C: Response function unification (follow-up to PR #84)

## One-sentence task
Extract shared `_respond_on_active_turn(gs, us, them, ...)` from `_p1_respond_on_opp_turn` + `_p2_respond_on_pro_turn` to close the residual ~3pp tempo-mirror asymmetry.

## Why this matters
PR #84 unified `protagonist_turn` and `opp_turn` via `_execute_turn`. Avg asymmetry dropped 12.5pp → 7.8pp. But the response functions (instant-speed interaction windows during the opponent's turn) are still divergent — see `results/tempo_mirror_root_cause.md` §"Remaining Asymmetry":

> The `_p1_respond_on_opp_turn` and `_p2_respond_on_pro_turn` response functions still offer different instant-speed options per slot (P1 gets Flash Bowmasters + Force of Vigor; P2 gets Snuff Out + Lightning Bolt). Unifying these is a follow-up task.

This is the residual ~3pp. Closing it should push avg asymmetry to ~5pp — close to the theoretical floor from genuine first-player advantage.

## Scope

### Part 1 — Audit the divergence

```bash
grep -nE "^def _p[12]_respond" engine.py
# _p1_respond_on_opp_turn at ~2046
# _p2_respond_on_pro_turn at ~2113
diff -u <(sed -n '2046,2112p' engine.py) <(sed -n '2113,2200p' engine.py)
```

Expected categories of difference:
- P1-only: Flash Bowmasters ETB, Force of Vigor reactive
- P2-only: Snuff Out (pitch), Lightning Bolt at EOT
- Shared: FoW/Daze/Flusterstorm counter attempts, Flickerwisp ETB blink

Everything that's "P1-only" or "P2-only" but is actually about CARD AVAILABILITY (not slot) needs to move to the shared function with a card-presence check.

### Part 2 — Extract shared core

```python
def _respond_on_active_turn(gs, us, them, log_fn, log_entries):
    """Single code path for instant-speed responses during opponent's turn.

    us   = player responding (us.hand, us.creatures, etc.)
    them = player whose turn it is (them.spells_cast_this_turn, etc.)

    Reachable from BOTH:
      _execute_turn(..., active=gs.p1) via gs.p2 responding
      _execute_turn(..., active=gs.p2) via gs.p1 responding
    """
    # All response logic here, keyed off us.find_tag(...) not gs.p1/p2
    ...
```

Then:
```python
def _p1_respond_on_opp_turn(gs, log_fn, log_entries):
    return _respond_on_active_turn(gs, us=gs.p1, them=gs.p2, ...)

def _p2_respond_on_pro_turn(gs, log_fn, log_entries):
    return _respond_on_active_turn(gs, us=gs.p2, them=gs.p1, ...)
```

Both become thin wrappers, like `protagonist_turn`/`opp_turn` are now.

### Part 3 — Audit for "P1-flavoured" responses that should be universal

For each instant-speed response in the code:
- If the reason it's "P1-only" is "because P1 runs that card" → move to shared, `us.find_tag()` handles availability
- If the reason is genuine slot-specific state (e.g. `gs.p1_poison` counter) → keep wrapper-specific, inject through parameter

Likely real cases where unification matters:
- Flash Bowmasters: triggers on opp's DRAWS. If Bowmasters is on either side's board, the draw-pings should match. Currently `bowmasters_triggers(n, gs, ctr)` takes controller — should be correct. Verify.
- Force of Vigor: targets 2 artifacts/enchantments. No slot-specific logic. Move to shared.
- Snuff Out: -4/-4 on a creature, pitch black card. No slot-specific logic. Move to shared.
- Lightning Bolt face at EOT: no slot-specific logic. Move to shared.

### Part 4 — Verification

```bash
python3 -c "from sim import run_rules_tests; run_rules_tests()"   # 147/147
python3 -c "from sim import run_sweep; import random
for s in (42,1,100,2026):
    random.seed(s)
    a = run_sweep('dimir','dimir_flash',200)
    random.seed(s)
    b = run_sweep('dimir_flash','dimir',200)
    sm = a['p1_wr']+b['p1_wr']
    print(f'seed={s}: sum={sm:.1%}')"
# Expected: sum drops to ~110-115% (was 126% post PR #84, 145% pre)
```

## Constraints
- Preserve all 5 EXPECTED_RANGES spot-checks.
- No new hardcoded numbers.
- Don't widen or narrow what each card does — just unify where the decision is made.

## Branch / PR
- Branch: `claude/mtgsim-response-unification-<suffix>` off main.
- Title: "Unify _p1/p2_respond_on_*_turn — closes residual tempo-mirror asymmetry"
- 2-3 commits: extract shared fn, rewire wrappers, matrix re-run spot-check.

## Expected impact
- Avg pairwise asymmetry 7.8pp → ~5pp (residual = genuine first-player advantage)
- Dimir-vs-dimir_flash sum 126% → ~115%
- No material WR change in non-mirror matchups
