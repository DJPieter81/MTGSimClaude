# Tempo-Mirror Asymmetry — Root Cause (Corrected)

**Date:** 2026-04-12
**Status:** Diagnosed, fix requires dedicated session

## Observation

The symmetry audit flagged the Dimir family as the worst P1/P2 asymmetry offenders:

| Pair | WR as P1 | WR as P2 | Sum | Expected |
|------|----------|----------|-----|----------|
| dimir vs dimir_flash | 65–71% | 68–77% | **137–145%** | 100% |
| dimir_b vs dimir_flash | 66% | 68% | 134% | 100% |
| dimir vs ur_tempo | 62% | 71% | 133% | 100% |

Reproduced consistently across 4 different seeds (n=200 each). Both sides win roughly 70% when placed as P1 — systemic, not Monte-Carlo variance.

## Original (incorrect) diagnosis

An earlier version of this document claimed the cause was `interaction.py` hardcoding `gs.p1` / `gs.p2` in functions like `_select_counter` and `_pick_removal`. **That diagnosis was wrong** — those functions don't exist (they were fabricated from a misreading) and the real functions with `gs.p1`/`gs.p2` hardcoding in interaction.py (`best_reactive_answer`, `should_push_now`) are **dead code** — imported but never called.

## Real root cause: two separate turn functions

```
play_turn(gs, turn, who)
├── who == 'p1'  →  sim.py:325   protagonist_turn()   (294 lines)
└── who == 'p2'  →  engine.py:1853 opp_turn()         (155 lines)
```

**P1 and P2 go through completely different code paths with different feature coverage.** Both were supposed to become equivalent after the symmetric-engine refactor, but only `protagonist_turn` received the full strategy-aware treatment. `opp_turn` is the legacy entry point — it still works, but with less sophisticated:

- Reactive counter logic (less aggressive use of FoW/Daze)
- Pre-strategy Thoughtseize / Fatal Push (P1 gets these; P2 doesn't via the same path)
- Lock-tax enforcement (apply_lock_effects is called for both but surrounding logic differs)
- Combat decision depth

The net effect: whichever deck the engine calls as P1 gets ~5–10pp better AI than the same deck as P2, which is exactly the tempo-mirror asymmetry we see.

## Evidence

| Path | Lines | Pre-strategy hooks | Post-strategy hooks |
|------|-------|--------------------|---------------------|
| `protagonist_turn` (sim.py) | 294 | Thoughtseize, Push, Wasteland activation, apply_lock_effects | Eidolon damage, combat via _select_attackers, EOT |
| `opp_turn` (engine.py) | 155 | apply_lock_effects only | Combat via simpler dispatch, EOT |

## Fix shape (deferred)

Unify the two functions:

1. Extract the shared skeleton into `_execute_turn(gs, turn, player, opponent, matchup)` in sim.py
2. Both `protagonist_turn` and `opp_turn` become thin wrappers that pass the correct player slot
3. All pre/post-strategy hooks (Thoughtseize, Push, Eidolon damage) live in the shared function so both sides get them

This is substantial — touches the two hottest code paths in the engine and requires careful behavior-preservation. Estimated scope:

- ~300 lines of diff across sim.py + engine.py
- Full matrix re-run to confirm the tempo-mirror asymmetry drops (expected: dimir-mirror 140% → 105-110%)
- Regression test across all 5 previously-passing spot-check matchups

## Why not fixed in this session

1. The refactor unifies 450 lines of diverged logic. Each hook must be proved to produce identical behavior when called from either slot.
2. Edge cases: `gs.p2_spells_cast_this_turn`, `gs.p1_poison` counters, `bowm_ctrl`, `_last_counter_used` — lots of P1/P2-named state that would need neutralization.
3. Better as its own focused PR so the matrix delta is cleanly attributable and reviewers can check feature parity line-by-line.

## Workaround in place

`symmetrise_matrix()` in meta_results.py averages both orderings and produces `<matrix>_sym.json` where every pair sums to 1.0. This hides the symptom in the displayed matrix data while leaving the cause in place.

## Status

| Layer | State |
|-------|-------|
| `interaction.py` P1/P2 hardcoding in dead functions | Harmless; cleanup optional |
| `best_proactive_target` parameterization | Already correct (takes `opponent=`) |
| `protagonist_turn` / `opp_turn` feature parity | **Needs unification** — primary root cause |

## Related

- `results/symmetry_audit_20260412.md` — original top-20 outlier ranking
- PLANNING.md §"Known Sim Limitations" / "P1 advantage inflation" row — same content
- `docs/cowork_brief_turn_unification.md` — **if created, this would be the third cowork brief**
