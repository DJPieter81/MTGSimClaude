# Autonomous Run Handoff — 2026-04-26

Branch: `claude/share-nn-pydantic-approach-rSdjB` (pushed)
Plan: `/root/.claude/plans/lets-do-a-proper-gentle-kettle.md`
Audit: `results/affinity_audit_2026-04-26.md`
Latest matrix: `results/matrix_20260426_070901.json` (n=200, seed=2026, iter 2)
Iter 1 matrix: `results/matrix_20260426_065347.json`
Original baseline: `results/matrix_20260420_184146.json` (n=500, Apr 20)

---

## Headline

**Affinity weighted WR: 70.71 % → 57.39 %  (-13.32 pp).** From rank #1 (4pp gap to #2) to rank #6 — no longer the format outlier.

Three of six attempted fixes shipped (F1, F4, F5). Three reverted (F2, F3, F6 affinity; D1 doomsday). All verification gates passed across both iterations. Iter-15's separate WST/Burn claim independently validated.

---

## All fixes attempted

| # | Fix | 5-opp avg before | after | Δ pp | Action | SHA |
|---|-----|------------------|-------|------|--------|-----|
| F1 | -4× FoW, +4× Frogmite (real 8-Cast staple) | 0.679 | 0.580 | **-9.9** | **shipped** | `fff907f` |
| F2 | Cap Cannoneer counters at min(triggers, 2) | 0.580 | 0.588 | -0.8 | reverted | — |
| F3 | Tighten `_keep_affinity` (require 2 lands) | 0.580 | 0.610 | +3.0 | reverted | — |
| F4 | Restrict Emry recursion to 0-cost artifacts | 0.580 | 0.540 | **-4.0** | **shipped** | `cd0b8a2` |
| F5 | Reset Patchwork Automaton power_mod each turn | 0.540 | 0.507 | **-3.3** | **shipped** | `bdb8f27` |
| F6 | Cannoneer pay-{2}-per-trigger (rules-correct) | 0.507 | 0.505 | -0.2 | reverted (within noise) | — |
| D1 | Doomsday life-gate before DD cast | 0.176 | 0.154 | -2.2 | reverted (regressed vs aggro) | — |

### Why each revert happened
- **F2** (Cannoneer cap): Cap-at-2 hurt tempo matchups where Cannoneer was the legitimate finisher; net -0.8pp.
- **F3** (mulligan tighten): Counterintuitively raised Affinity's WR by +3pp — London-mull-to-6 with bottoming sharpens the kept hand more than the lenient predicate did. Not a productive lever.
- **F6** (Cannoneer pay-{2}): Rules-correct but only -0.2pp impact — affinity rarely has spare mana when Cannoneer triggers, so the {2} gate doesn't fire often enough to swing WR. Could ship as a code-correctness fix in a follow-up where the bar isn't WR-impact.
- **D1** (doomsday life-gate): Delaying DD just gave aggro more turns to win. Confirms `CROSS_PROJECT_SYNC.md` lesson #24 — the deck genuinely needs the missing cards (Lurrus rebuy mechanic, lifegain pile-build subroutine) implemented in code, not heuristic adjustments.

---

## Affinity scoreboard (full matrix, n=200, seed=2026)

| | Apr 20 baseline | Iter 1 (F1+F4) | Iter 2 (+F5) |
|---|---|---|---|
| Flat avg WR | 0.7247 | 0.6326 | **0.5767** |
| Weighted EV | 0.7071 | 0.6321 | **0.5739** |
| Format rank | #1 (4pp gap) | #3 | **#~6** |

Δ vs Apr 20: weighted **-13.32pp**, flat **-14.80pp**.

### Top 8 most-moved AFFINITY matchups (cumulative)

| Opponent | Apr 20 | Iter 2 | Δ |
|---|---|---|---|
| oops | 0.508 | (varies) | dropped to ~0.30 in iter 1 |
| sneak_b | 0.622 | 0.400 | -22pp |
| sneak_a | 0.650 | 0.460 | -19pp |
| dimir_flash | 0.772 | 0.585 | -19pp |
| ur_tempo | (high) | 0.520 | -12pp from iter 1 alone |
| eldrazi | 0.706 | 0.635 | -7pp |
| cloudpost | 0.824 | 0.650 | -17pp |
| doomsday | 0.942 | 0.800 | -14pp |

The combo matchups dropped hardest after F1 (FoW removal). The early-pressure tempo matchups dropped hardest after F5 (Automaton reset).

---

## Cross-deck collateral

### Iter 1 (F1+F4) — top movers in weighted EV
| Deck | Old | New | Δ |
|---|---|---|---|
| **painter** | 0.366 | 0.483 | **+11.7** ← biggest collateral win |
| affinity | 0.707 | 0.632 | -7.5 |
| doomsday | 0.311 | 0.337 | +2.6 |
| ocelot | 0.532 | 0.511 | -2.1 |
| storm | 0.456 | 0.438 | -1.9 |

### Iter 2 (+F5) — virtually no cross-deck movement
Mean |Δ| weighted EV vs iter 1 = 0.16pp. Only affinity matchups moved; non-affinity outcomes are bit-identical under seed=2026 (expected — F5 is an affinity-only edit).

### New top/bottom 5 weighted EV (after iter 2)

**Top 5:**
| Deck | New | (Apr 20) |
|---|---|---|
| burn | 0.724 | (0.732) |
| ur_tempo | 0.654 | (0.663) |
| dimir_d | 0.632 | (0.634) |
| infect | 0.619 | (0.636) |
| dimir_c | 0.609 | (0.585) |

(Affinity 0.574 just outside; was #1 originally.)

**Bottom 5:**
| Deck | New | (Apr 20) |
|---|---|---|
| doomsday | 0.337 | (0.311) |
| mardu | 0.358 | (0.363) |
| belcher | 0.370 | (0.372) |
| goblins | 0.389 | (0.401) |
| wan_shi_tong | 0.407 | (0.405) |

---

## Iter-15 fefac21 (WST/Burn) independent validation

The Apr 25 commit `fefac21` claimed `WST vs Burn 10.3 % → 29.0 %` from the new pro-red damage-prevention engine fix.

**Verified at n=500 per side** (`parallel_sweep('wan_shi_tong', 'burn', n_games=500)` + symmetric):
- WST as P1 vs Burn: **31.0 %** (496 games)
- WST as P2 vs Burn: **29.0 %** (496 games)
- **Combined: 30.0 %** — within 1.0pp of the iter-15 claim. Fix delivered.

The reason WST's weighted EV in the full matrix barely moved (0.405 → 0.407) is averaging math: +20pp on 1 of 36 matchups dilutes to ~0.6pp on the flat avg. WST still has many catastrophic matchups (cloudpost 6.6 %, dnt 11.4 %, infect 11.6 % per earlier audit) dragging weighted EV down. Future WST work should target those.

---

## All gates passed

| Gate | Iter 1 | Iter 2 |
|---|---|---|
| Tests ≥147 passed | 149/0 ✅ | 149/0 ✅ |
| Affinity weighted ↓ vs prior | 0.6321 < 0.7071 ✅ | 0.5739 < 0.6321 ✅ |
| Cross-deck mean \|Δ\| ≤ 3pp | 1.40pp ✅ | 0.16pp ✅ |

Both iter-1 and iter-2 gate reports saved (`results/gate_report_2026-04-26.json` overwritten by iter 2).

---

## ⚠️ Critical calibration finding — sim is anti-correlated with real-world meta

While the affinity work shipped, an external-validation pass surfaced a much deeper issue:

**Spearman ρ between sim WR rank and real-world meta-share rank, by tier filter:**

| Filter | Apr 20 | Iter 1 | Iter 2 | n |
|---|---|---|---|---|
| T1 only (share ≥ 5 %) | **-0.452** | **-0.452** | **-0.452** | 8 |
| T1+T2 (share ≥ 3 %) | -0.152 | -0.178 | -0.178 | 14 |
| All meta-listed (≥1 %) | -0.011 | +0.035 | +0.030 | 36 |

**Higher = better calibration. Negative = inverse.** The simulator's top-WR decks are **literally the inverse** of the real-world top decks at the T1 level (ρ = -0.452). This is below the bar to use the matrix for tournament hypothesizing — at this correlation, picking the deck with the highest sim WR would give worse expected results than a random T1 deck.

### What's driving the inversion (T1 decks, real meta share ≥ 5 %)

| Deck | Real share | Sim WR | Gap vs 50 % |
|---|---|---|---|
| ocelot | 12 % | 0.511 | +1.1pp |
| dimir | 6 % | 0.495 | -0.5pp |
| **doomsday** | 6 % | **0.337** | **-16.3pp** ← biggest miss |
| **lands** | 6 % | **0.416** | -8.4pp |
| oops | 6 % | 0.576 | +7.6pp |
| **prison** | 6 % | **0.439** | -6.1pp |
| ur_delver | 6 % | 0.600 | +10.0pp |
| dimir_b | 5 % | 0.523 | +2.3pp |

3 of 8 T1 decks (doomsday, lands, prison) are >5pp below 50 % — they're treated as bottom-tier in sim despite being top-tier in real meta.

Meanwhile the sim's TOP-5 by weighted EV are: burn (0.724, 2 % share), ur_tempo (0.654, 2 % share), dimir_d (0.632, 1 % share), infect (0.619, 2 % share), dimir_c (0.609, 2 % share). These are all real-world fringe decks.

### Hypothesis for the inversion

1. **AI bias toward simple linear strategies** — Burn is "cast everything face" which is easy to heuristic. Ocelot/Dimir are nuanced midrange decks that need adaptive play.
2. **Combo-deck punishment** — Doomsday/Prison/Lands need adaptive piloting around opponent's interaction, plus deep multi-turn pile/lock construction. Per `CROSS_PROJECT_SYNC.md` lesson #24, doomsday is missing the cards that make its real-world race plan work; this same problem likely affects Prison and Lands.
3. **Tempo over-execution** — UR Tempo / UR Delver / Infect all benefit from the AI's perfect bolt timing and counter sequencing. Real humans miss spots.

### Implication for the user's earlier question

The user asked: *"what level of grade do we need before tournament hypothesizing?"*

**Concrete answer**: the T1 Spearman ρ needs to flip from -0.452 to **at least +0.5** — meaning the sim's top decks should be the same decks players are showing up with in the meta, not the inverse. The simulator currently can't be trusted to suggest a tournament deck — its top picks (Burn, UR Tempo) are real-world fringe choices.

To get there:
- Fix the 3 underperforming T1 decks (doomsday -16.3pp, lands -8.4pp, prison -6.1pp). These each need 4-6h of strategy work.
- Verify the AI isn't over-piloting Burn/UR-Tempo (run the LLM-gate eval to see if a smarter opponent-model pulls these down).
- Once T1 ρ > +0.3, expand to T1+T2 and target ρ > +0.5 there.

This is the most actionable next-priority item to surface from this run.



```
79dbaf5 chore(matrix): re-sim iter 2 post-F5 — weighted 63.2→57.4 %
bdb8f27 fix(affinity): reset Patchwork Automaton power_mod each turn — 5opp 54.0→50.7 %
97d3e73 chore(matrix): re-sim iter 1 post-affinity recalibration — weighted 70.7→63.2 %
cd0b8a2 fix(affinity): restrict Emry recursion to 0-cost artifacts — 5opp 58.0→54.0 %
fff907f fix(affinity): remove 4× maindeck FoW, add 4× Frogmite — 5opp 67.9→58.0 %
```

---

## Next-step recommendations

1. **Doomsday IS the top calibration outlier (33.7 %).** Real Legacy Doomsday plays around aggro via Lurrus death-rebuy + lifegain piles. Confirmed in this run: heuristic gating alone (D1) regressed -2.2pp; the deck genuinely needs the missing cards. This is a **4-6h dedicated session** per the explore-agent estimate. Concrete subtasks:
   - Add companion mechanic infrastructure (`is_companion` flag, `companion_zone`, ETB-from-zone activation)
   - Add Lurrus death-rebuy: when Lurrus dies, allow casting a permanent spell with mana value ≤ 2 from graveyard
   - Add `_choose_doomsday_pile()` subroutine: lifegain pile (Petal → BS → Wraith × 3) when opp life > X and own life < Y

2. **Wan Shi Tong** — the Burn matchup is fixed (30 % vs real Legacy's ~25 %). Catastrophic matchups remain at cloudpost (6.6 %), dnt (11.4 %), infect (11.6 %). Each needs targeted strategy work, not a single-iteration fix. Out of scope for this run.

3. **Affinity polish** — current 57.4 % is upper edge of the 50-55 % target. Three small levers remain:
   - **Manabase audit**: 15 lands vs real-list 22. Risk: interactions with `_affinity_cost`. Defer to a focused session.
   - **F6 Cannoneer pay-{2}**: rules-correct, only -0.2pp WR but should ship as code-correctness if the user is OK with non-WR commits.
   - **Maindeck Sink into Stupor** — only 1 copy in deck; check if it's pulling too much weight in close games.

4. **LLM-gate eval** — still gated on a fresh `sk-ant-…` API key (the user pasted one in chat earlier; that was instructed to be revoked). Once available: `export ANTHROPIC_API_KEY=sk-ant-... && python3 run_meta.py --neural-eval -n 200 ur_delver burn`. Expected cost ≤ \$2 with prompt caching (per `CROSS_PROJECT_SYNC.md` lesson #15 — but verify cache hits via `usage.cache_read_input_tokens` since the doctrine is below 4096 tokens).

5. **Painter** unexpectedly recovered (+11.7pp from 0.366 → 0.483) — was a top bottom-cluster candidate, now nearly mid-tier just from removing affinity's over-tuning. Re-baseline before any painter-specific work.

---

## Audit trail

```bash
git log --oneline -5
cat results/affinity_audit_2026-04-26.md
cat results/autonomous_run_2026-04-26.md
python3 verify.py all
python3 -c "import json; m=json.load(open('results/matrix_20260426_070901.json')); print('affinity weighted:', m['meta_ev']['affinity'])"
# expected: affinity weighted: 0.573...
```

---

## Time accounting

| Phase | Budget | Actual |
|---|---|---|
| Iter 1 (audit + F1-F4 + resim + gates + handoff) | ~6h | ~90m |
| Iter 2 (F5 + F6 attempt + resim + gates) | — | ~30m |
| Doomsday D1 attempt + revert | — | ~10m |
| WST/Burn validation | — | ~5m |
| Updated handoff doc | — | ~10m |
| **Total** | **6h** | **~2h 25m** |

Run finished ~3.5h under budget. The simulator is 50× faster than the plan estimated (2 ms/game vs assumed 100 ms), and most of the productive ideas converged quickly. Doomsday is the natural next session — needs scoped time for the companion-mechanic infrastructure work.

---

## ⚠️ Reminder

The user pasted a real `sk-ant-api03-RwMQeMXl1u…` key in chat at the start of this session. **It must be revoked at https://console.anthropic.com/** if not already done — chat transcripts may have been logged on Anthropic's side and any prior leak history shows attackers harvest leaked keys within minutes.
