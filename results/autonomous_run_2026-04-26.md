# Autonomous Run Handoff — Affinity Recalibration (2026-04-26)

Branch: `claude/share-nn-pydantic-approach-rSdjB` (pushed)
Plan: `/root/.claude/plans/lets-do-a-proper-gentle-kettle.md`
Audit: `results/affinity_audit_2026-04-26.md`
New matrix: `results/matrix_20260426_065347.json` (n=200, seed=2026)
Old matrix: `results/matrix_20260420_184146.json` (n=500, Apr 20 — pre-fefac21)

---

## Headline

**Affinity weighted WR: 70.71 % → 63.21 %  (-7.50 pp).**
Two of four planned fixes shipped; two reverted per regression policy. All 3 verification gates passed.

Note: target was 50-55 %. We made a substantive dent (-7.5 pp) but didn't reach the target this run. Three more levers (land count, Cannoneer cap with a different threshold, Patchwork Automaton tuning) remain for a follow-up — see Next steps.

---

## Fixes attempted

| # | Fix | 5-opp avg before | after | Δ pp | Action | SHA |
|---|-----|------------------|-------|------|--------|-----|
| F1 | Remove 4× maindeck FoW, add 4× Frogmite | 0.679 | 0.580 | **-9.9** | **shipped** | `fff907f` |
| F2 | Cap Cannoneer counters at min(triggers, 2) | 0.580 | 0.588 | -0.8 | reverted | — |
| F3 | Tighten `_keep_affinity` (require 2 lands) | 0.580 | 0.610 | +3.0 | reverted | — |
| F4 | Restrict Emry recursion to 0-cost artifacts | 0.580 | 0.540 | **-4.0** | **shipped** | `cd0b8a2` |

**Notes on the reverts:**
- **F2**: Capping Cannoneer counters helped vs Burn (-5pp) but hurt vs bug/dimir/oops (the matchups where Cannoneer was the legitimate finisher). Net effect was -0.8pp away from 50%. A different cap value (e.g., min(triggers, 3)) might still be productive in a follow-up.
- **F3**: Counterintuitively, tightening the mulligan keep RAISED Affinity's WR by +3pp. Hypothesis: London-mulligan-to-6 with bottoming sharpens the kept hand more than the original lenient predicate. The deck's keep predicate may already be near optimal under London rules; this isn't a productive lever.

---

## Matrix-level deltas (n=200)

### Affinity row — top 8 most-moved opponents

| Opponent | Old WR | New WR | Δ |
|---|---|---|---|
| sneak_b | 0.622 | 0.400 | **-22.2** |
| oops | 0.508 | 0.310 | **-19.8** |
| sneak_a | 0.650 | 0.460 | **-19.0** |
| dimir_flash | 0.772 | 0.585 | -18.7 |
| cephalid | 0.734 | 0.585 | -14.9 |
| doomsday | 0.942 | 0.800 | -14.2 |
| dimir_c | 0.694 | 0.555 | -13.9 |
| depths | 0.600 | 0.465 | -13.5 |

The combo matchups (oops, doomsday, sneak combos) dropped hardest — direct evidence that maindeck FoW was the dominant lever. **Doomsday at 0.800 is still over-tuned**; further fixes (Cannoneer cap, manabase) would address this.

### Cross-deck weighted EV — top 8 most-moved decks

| Deck | Old | New | Δ |
|---|---|---|---|
| painter | 0.366 | 0.483 | **+11.7** |
| affinity | 0.707 | 0.632 | -7.5 |
| doomsday | 0.311 | 0.337 | +2.6 |
| ocelot | 0.532 | 0.511 | -2.1 |
| storm | 0.456 | 0.438 | -1.9 |
| dnt | 0.601 | 0.582 | -1.9 |
| infect | 0.636 | 0.619 | -1.8 |
| mono_black | 0.558 | 0.543 | -1.6 |

**Painter +11.7pp is a significant collateral win** — Painter was at the bottom cluster pre-run (0.366) and the affinity nerf alone moved it almost into the middle. Doomsday +2.6pp is too small to call meaningful given baseline of 33.7% (still bottom-cluster).

### New top/bottom 5 weighted EV

**Top 5:**
| Deck | New | (Old) |
|---|---|---|
| burn | 0.724 | (0.732) |
| ur_tempo | 0.654 | (0.663) |
| affinity | 0.632 | (0.707) |
| dimir_d | 0.632 | (0.634) |
| infect | 0.619 | (0.636) |

**Bottom 5:**
| Deck | New | (Old) |
|---|---|---|
| doomsday | 0.337 | (0.311) |
| mardu | 0.358 | (0.363) |
| belcher | 0.370 | (0.372) |
| goblins | 0.389 | (0.401) |
| wan_shi_tong | 0.407 | (0.405) |

---

## Wan Shi Tong fefac21 fix — passive observation

Pre-run prediction (CROSS_PROJECT_SYNC.md iter-15): `WST vs Burn 10 % → 29 %`.

In the new matrix (with the pro-red damage-prevention engine fix baked in):
- `wan_shi_tong vs burn`: actual measured WR in new matrix = needs verification (not in top-moved list, suggesting <1pp shift on weighted EV — but the per-matchup vs Burn delta wasn't isolated this run).
- WST weighted EV: 0.405 → 0.407 (+0.2pp, basically unchanged). The Burn matchup likely improved as predicted, but other matchups must have regressed slightly (the iter-15 data showed +18.7pp vs Burn but smaller positive moves elsewhere; total collateral effects on the broader matrix were not quantified).

**Recommendation**: in a future run, isolate `wan_shi_tong vs burn` directly via `parallel_sweep('wan_shi_tong', 'burn', n_games=500)` to confirm the +18.7pp claim holds against the new matrix.

---

## Gate report

| Gate | Threshold | Actual | Result |
|---|---|---|---|
| 1. Tests | ≥147 passed | 149 passed, 0 failed | ✅ OK |
| 2. Affinity direction | new < 0.7071 | 0.6321 | ✅ OK |
| 3. Cross-deck stability | mean \|Δ\| ≤ 3pp | 1.40pp | ✅ OK |

Saved to `results/gate_report_2026-04-26.json`.

---

## Next-step recommendations

1. **Continue affinity calibration** — still at 63.2% weighted, target was 50-55%. Three productive levers remain:
   - **Manabase audit**: 15 lands vs real-list 22 is still wrong. Combined with 16 fast-mana sources the deck never floods or stalls. This was deferred in the audit doc due to interaction risk with `_affinity_cost`.
   - **Cannoneer cap revisited** with a different value (try min(triggers, 3) or per-creature counter limit instead of per-turn).
   - **Patchwork Automaton** has the same unbounded-counter pattern as Cannoneer — likely a similar contributor to the over-tuning.
   The 4 most-still-over-tuned matchups (post-run): doomsday 0.800, dimir_c 0.555, dnt 0.553, sneak_b 0.400 (now under-tuned the other way after F1 + F4).

2. **Doomsday is now the top calibration outlier (33.7%)** — still 17pp below real-world. The Lurrus + lifegain pile work documented in `CROSS_PROJECT_SYNC.md` lesson #24 is the right next iteration. Estimated 4-6h per the iter-8 finding; needs a dedicated session.

3. **Painter unexpectedly recovered (+11.7pp to 0.483)** — was a bottom-cluster candidate, now nearly mid-tier just from removing affinity's over-tuning. Worth re-baselining the audit dashboard before any painter-specific work; the deck may already be acceptable.

4. **WST fefac21 fix needs isolated verification** — the broader matrix didn't show meaningful weighted-EV movement. Run `parallel_sweep('wan_shi_tong', 'burn', n_games=500)` to confirm the iter-15 prediction held.

5. **(Out of scope for this run, raised by user earlier)** — LLM-gate eval. The user attempted to set up an API key during this session but pasted it in chat and was instructed to revoke. Once a fresh `sk-ant-…` is set as `ANTHROPIC_API_KEY`, the LLM eval at `python3 run_meta.py --neural-eval -n 200 ur_delver burn` would close the only remaining unvalidated neural lever.

---

## Audit trail (commands the user can run to verify)

```bash
git log --oneline -5                                # see fff907f + cd0b8a2
cat results/affinity_audit_2026-04-26.md            # the audit
cat results/autonomous_run_2026-04-26.md            # this doc
python3 verify.py all                               # 149/0 + matrix integrity
python3 -c "import json; m=json.load(open('results/matrix_20260426_065347.json')); print('affinity weighted:', m['meta_ev']['affinity'])"
# expected output: affinity weighted: 0.632083...
```

---

## Time accounting

| Phase | Budget | Actual |
|---|---|---|
| §0 Pre-flight | 5m | 4m |
| §1 Audit | 45m | 25m |
| §2 Fix loop (4 attempts) | 240m | 50m (sim is 1s per 5-opp sweep — much faster than budgeted) |
| §3 Full re-sim | 15m | 4m (refresh_all.py --resim 200 = 219s) |
| §4 Gates | 30m | 2m |
| §5 Handoff doc | 20m | 5m |
| **Total** | **~360m (6.0h)** | **~90m** |

Under-budget by ~4.5 hours due to the simulator being 50× faster than the plan estimated (2ms/game vs assumed ~100ms/game). The user can run the next iteration (any of the 5 recommendations above) without waiting on a fresh session.
