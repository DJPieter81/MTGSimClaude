# Tempo-Mirror Asymmetry — Root Cause Found

**Date:** 2026-04-12
**Status:** Diagnosed, fix deferred (large refactor required)

## Observation

The symmetry audit flagged the Dimir family as the worst P1/P2 asymmetry offenders:

| Pair | WR as P1 | WR as P2 | Sum | Expected |
|------|----------|----------|-----|----------|
| dimir vs dimir_flash | 65–71% | 68–77% | **137–145%** | 100% |
| dimir_b vs dimir_flash | 66% | 68% | 134% | 100% |
| dimir vs ur_tempo | 62% | 71% | 133% | 100% |

Reproduced consistently across 4 different seeds (n=200 each). Both sides win roughly 70% when placed as P1, regardless of which side is called "P1" in the run. This is not Monte-Carlo variance — it's systemic.

## Root cause

`interaction.py` hard-codes `gs.p1` as "us" and `gs.p2` as "them" in several helper functions:

```
interaction.py:131   b = gs.p1                    # _select_counter: "our" bench
interaction.py:137   opp_untapped = gs.p2...      # always looks at P2's mana
interaction.py:199   o = opponent if opponent is not None else gs.p2
interaction.py:247   b = gs.p1                    # _pick_removal
interaction.py:267   opp_has_spells = any(... gs.p2.hand)
```

When the strategy runs as the engine's `p2` slot, these helpers still read P1 as "our" hand and P2 as "the opponent's" — the roles are inverted, so every counter/removal decision is looking at the wrong player's board.

This inflates both sides' apparent win rate because:
1. When you're P1, the helpers correctly read your hand — you play tight
2. When you're P2, the helpers read P1's hand as yours — you "use" counters from the wrong pool but (coincidentally) those counters often DO exist on P2's side too for tempo mirrors, so you still win, just less optimally

The net effect is that both halves of the matchup report ~70% because each side's decision-making, while miscalibrated, still works well enough to win 70% of its games against a self-sabotaging mirror.

## Fix shape (deferred)

Refactor `interaction.py` to take explicit `us` / `them` parameters instead of assuming p1/p2:

```python
# Before
def _select_counter(spell_card, gs, is_opponents_turn):
    b = gs.p1
    opp_untapped = gs.p2.available_mana_count()
    ...

# After
def _select_counter(spell_card, gs, us, them, is_opponents_turn):
    b = us
    opp_untapped = them.available_mana_count()
    ...
```

Then update all call sites. Approximately 8 functions in `interaction.py`, ~20 call sites in `engine.py`.

This is straightforward but touches load-bearing code. Should land as its own PR with:
- Before/after matrix run (expect Dimir-mirror asymmetry to drop from ~140% to ~110% — still inflated by legitimate P1 advantage but no longer by the bug)
- Regression spot checks across all passing matchups
- New rules tests verifying `_select_counter(..., us=gs.p2, them=gs.p1)` produces the correct pool

## Why not fixed in this session

1. The refactor is 30+ edits across interaction.py + engine.py
2. Each call site needs careful review — some strategies may rely on the P1-bias behaviour in subtle ways that manifest as "we shipped these WRs so the broken calibration is baked in"
3. Better as its own focused PR so the matrix delta is cleanly attributable

## Workaround in place

`symmetrise_matrix()` in meta_results.py averages both orderings, which reduces the apparent asymmetry in displayed matrix data. This hides the symptom while leaving the cause in place.

## Related

- `results/symmetry_audit_20260412.md` — original top-20 outlier ranking
- PLANNING.md §"Known Sim Limitations" / "P1 advantage inflation" — this is the real content behind that row
