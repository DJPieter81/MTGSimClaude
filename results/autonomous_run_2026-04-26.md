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

## Iter 4 — Infect Chalice-bypass fix (SHIPPED, +11.6pp on prison vs infect)

While auditing prison (T1, sim 0.439, real share 6 %, gap -6.1pp), discovered the actual root cause was in **infect's strategy**, not prison's. Infect's pump spells (Mutagenic Growth, Invigorate, Berserk, Vines of Vastwood, Blossoming Defense) all bypass `opp_can_cast()` — they do `player.remove_from_hand(spell)` directly without checking Chalice/Trinisphere/Thalia. Chalice on 1 should hard-counter all of these (all CMC 1) but the simulator silently let them through.

Fix: gated all 7 pump deployment sites behind `opp_can_cast(spell, mana, gs, caster=player)`. Imports updated.

**Impact at n=300**:
- prison vs infect: 0.235 → 0.351 (**+11.6pp**) — biggest single matchup move of the entire session
- prison vs ur_tempo: 0.310 → 0.392 (+8.2pp)
- prison 5-opp avg: 0.294 → 0.323 (+2.9pp)

**Aggregate matrix re-sim (iter 4 at n=200)**:
- infect weighted EV: 0.619 → **0.560 (-5.84pp)** — over-tuning was partly bypass-dependent
- prison weighted EV: 0.439 → 0.439 (0.0pp) — the +11.6pp prison-vs-infect cell doesn't aggregate to weighted EV because infect's meta share is only 2 %
- Cross-deck stability: 0.16pp ≤ 3pp ✅

Commits: `f71b09c` (infect.py fix), `a779b8b` (matrix re-sim).

## Iter 5 — Affinity Chalice-bypass fix (SHIPPED, code-correctness)

Same bypass pattern found in **affinity**: 5 sites bypassed `opp_can_cast` — Lotus Petal, Mishra's Bauble, Urza's Bauble, Mox Opal (all CMC 0 → Chalice X=0), Lavaspur Boots, Shadowspear (both CMC 1). Trinisphere also wasn't enforced — affinity's "free" artifacts should be taxed to 3 mana under Trinisphere.

Fix: 5 gates added.

**Impact at n=200**:
- affinity 5-opp avg: 0.507 → 0.476 (**-3.1pp toward 50 %**)
- vs prison: 0.541, vs painter: 0.500, vs eldrazi: 0.561 — all calibrated near mid-tier post-fix

Commit: `ee7877d`. Did not run a full matrix re-sim for this one (would have given a 4th matrix; cumulative impact is small relative to iter 1-2 affinity work).

## Iter 8 — Glacial Chasm attempt (REVERTED — deck-composition tradeoff lesson)

After iter 7 shipped Exploration+Loam, attempted to close Lands' remaining bottom matchups (vs dnt 0.215, uwx 0.260, oops 0.310) with **Glacial Chasm** — a defensive land that prevents all damage to controller, with cumulative upkeep cost.

### What was implemented (then reverted)
- `cards.py`: added 1× Glacial Chasm to lands deck (dropped 1× Yavimaya for slot)
- `game.py`: `PlayerState.has_chasm_protection()` helper checking lands for tag='chasm'
- `engine.py`: combat_declare unblocked-damage section now checks `defender_player.has_chasm_protection()`; lands strategy added cumulative-upkeep tracking via `chasm_age` attribute on the perm (sac when can't pay)
- `decks/burn.py`: `deal_face_damage` checks chasm
- `sim.py`: land-priority function deploys Chasm at life ≤ N when opp pressure threshold met

### What went wrong
**Two attempts, both regressed:**

1. **First attempt** (life ≤ 12 + opp_creature_power ≥ 4): Burn -4.6pp, Infect -8.5pp. Cumulative upkeep eats life faster than Chasm prevents in matchups where the damage path isn't life-based (Infect = poison) or where the prevented damage is comparable to upkeep cost.

2. **Second attempt** (life ≤ 5 + opp_power ≥ life — emergency-only): Goblins -8.2pp, Infect -7.1pp. Even at emergency thresholds, the **deck-composition tradeoff** of dropping 1× Yavimaya for Glacial Chasm hurts. ~30% of games see Chasm in hand by T5; if not deployed, it's a dead card. Removing 1 green source also occasionally costs Crop Rotation activations.

### Lesson — engine fix is correct, deck slot is wrong
The damage-prevention engine work is sound (verified by DNT +5.9pp on first attempt — exactly the matchup Chasm targets). But:

- Adding Chasm at the cost of a Yavimaya is net-negative because Yavimaya was a more reliable contributor (every game) than Chasm (rare deployment + sometimes dead in hand)
- The deployment heuristic in `_pick_land()` competes with other utility lands (Tabernacle especially vs Goblins), causing trade-off losses
- Cumulative upkeep makes Chasm net-neutral or net-negative in many matchups

**Future approach for Manu / next session**:
1. Add Chasm WITHOUT removing Yavimaya — i.e., expand the deck to 61 cards or drop a different non-utility slot (Disruptor Flute is 3× and rarely used — could drop 1 to make room).
2. Or implement Chasm as a **Crop-Rotation-tutorable** target only — keep it in deck but don't draw into it naturally; only fetch via Crop Rotation when life is critical.
3. Or implement **Punishing Fire + Grove of the Burnwillows** instead — different defensive layer (kills creatures, doesn't lock combat) that doesn't consume life via upkeep.

All of these are larger commitments than fit in this iteration. **Reverted entirely**; iter 7 (Exploration+Loam) work is preserved and remains shipped.

## Iter 7 — Lands Exploration + Loam (SHIPPED, +9.5pp weighted, first T1 ρ move)

After iter 6's TES revert, attacked the next-highest-leverage T1 calibration outlier — **lands** (sim 0.416 weighted, real meta share 6 %, gap -8.4pp). Per the lessons #24 (missing real cards) and #28 (bypass pattern), the right move was structural mechanic implementation, not bypass auditing.

### What was missing
1. **Exploration ×4** in deck — never cast, no engine support (`game.py:play_land` had a hard `land_played_this_turn` limit)
2. **Life from the Loam ×4** in deck — never cast, no dredge mechanism, no recursion of Wasteland from GY

### Implementation (3 files)

**`game.py PlayerState`**: new field `extra_land_drops_used: int`, new methods `_exploration_count()` and `can_play_extra_land()`. `play_land()` now allows extra drops when an Exploration permanent is in play. `untap_all()` resets the counter.

**`sim.py` protagonist land-drop block** (~L549-580): replaced single-shot `if not land_played_this_turn` with a loop `for _ in range(1 + b._exploration_count())`. Prefers Wasteland > Saga > combo lands when picking extras. Logs `[Exploration]` marker on bonus drops.

**`engine.py _strategy_lands`**: Cast Exploration via `cast_spell()` as soon as available. After cast, attempt extra land drops inline. Cast Loam (1G) when 2+ mana available — returns up to 3 land cards from GY to hand (priority Wasteland > Saga > Tabernacle > Maze > Ghost Quarter > Tomb > combo). **Simulated dredge**: if Loam in GY and 3+ cards in library, mill 3 and return Loam to hand.

### Per-matchup impact (n=500)

| Opponent | Before | After | Δ |
|---|---|---|---|
| dnt | 0.190 | 0.208 | +1.8pp |
| uwx | 0.290 | 0.284 | -0.6pp |
| dimir_d | 0.415 | 0.460 | +4.5pp |
| oops | 0.265 | 0.331 | +6.6pp |
| ocelot | 0.330 | 0.417 | **+8.7pp** |
| **5-opp avg** | 0.298 | 0.340 | **+4.2pp** |

Tempo/midrange matchups (ocelot, dimir_d) gained most from the Exploration tempo boost. DNT/UWX still tough — lands needs Glacial Chasm (life-prevention lock vs aggro) for those, deferred to a future iteration.

### Aggregate matrix re-sim (iter 7)

**Lands weighted EV: 0.416 → 0.511 (+9.5pp)** — out of the bottom cluster, now nearly mid-tier. New top/bottom 5 lists no longer include lands.

**T1 Spearman ρ moved for the first time this session**:
| Filter | orig (Apr 20) | iter 4 | iter 7 |
|---|---|---|---|
| T1 only (n=8) | -0.452 | -0.452 | **-0.429** |
| T1+T2 (n=14) | -0.152 | -0.178 | -0.169 |
| All meta (n=36) | -0.011 | +0.045 | +0.061 |

The T1 ρ improvement is small but it's the first signal that calibration is moving. To flip T1 ρ positive, the remaining work is on doomsday (still 0.335, gap -16.5pp) and prison (0.439, gap -6.1pp). Each is a structural project of similar scope.

**Cross-deck stability**: mean |Δ| weighted EV vs iter 4 = 0.94pp ≤ 3pp gate.

Top 10 most-moved decks vs iter 4: only lands (+9.5pp) is significant; the others (-1 to -2pp on dimir variants, ocelot, ur_tempo) reflect those decks' previously-easy matchup vs lands now becoming closer to fair.

Commits: `4b64f7c` (lands fix), `f9bee1c` (matrix re-sim).

### What's left for lands

Worst remaining matchups:
- vs dnt 0.215 — Thalia tax + Stoneforge clock outraces lands
- vs uwx 0.260 — control wins long game
- vs oops 0.310 — fast combo
- vs sneak_a 0.390 — T2-T3 Show & Tell into Emrakul

All four would benefit from **Glacial Chasm** (life-gain on ETB + skip combat damage = lock vs aggro/tempo). Real Lands runs 1-2 copies. Adding it to the deck + implementing the "skip combat damage to controller" effect is ~50 lines and should close another 5-10pp on these matchups. Deferred to next session.

## Iter 6 — TES bypass attempt (REVERTED — important timing lesson)

Targeted `decks/tes.py` for the same bypass treatment — 33 raw sites, 14 confirmed TRUE BYPASS via Explore audit (Probe, cantrips, Dark Ritual, Veil, Burning Wish, Infernal Tutor ×2, Tendrils, Empty, FoW, Ad Nauseam).

**Two-step learning**:

1. **First attempt** used `opp_can_cast()` directly (same pattern as infect/affinity fixes). 5-opp avg crashed from 0.480 → 0.110 (-37pp), with Burn matchup dropping -45pp. **Root cause**: `opp_can_cast()` calls `can_afford()` which checks untapped lands. TES tracks mana via a local int counter (Petals/Rituals/LED produce floating mana, not from untapped lands). By the time TES reaches Step 6 (Wish/Tendrils), all lands are tapped, so `can_afford()` falsely blocks the cast even when the local counter has plenty of mana.

2. **Second attempt** used a tax-only helper that skips `can_afford` and only checks Chalice/Trini/Thalia. 5-opp avg moved **only +1.2pp at n=500** (per-matchup: prison +6.2pp, painter +5.5pp, eldrazi -6.9pp, burn -3.1pp, dimir +4.4pp). **The expected direction (TES drops vs Chalice decks) materialised only on eldrazi** — because Eldrazi reliably deploys T1 Chalice via Eldrazi Temple's extra mana. Prison/painter/uwx Chalice typically arrives T2-T4, by which point TES has often already won via T1-T2 storm chain.

Per the plan's regression policy ("Keep if (a) TES vs Chalice decks drops AND (b) cross-deck mean |Δ| ≤ 3pp AND (c) tests pass"), gate (a) failed at the aggregate. **Reverted**.

### Lesson (added to `CROSS_PROJECT_SYNC.md` lesson 28)

For storm-class combo decks, the bypass fix is correct in code but rarely moves WR because:
- Opponent Chalice typically lands T2+, after Storm has T1-T2 kill window
- Storm's local `mana` counter (from rituals/petals) doesn't pair with `opp_can_cast()` — must use a tax-only helper that skips `can_afford`
- Only opponents with reliable T1 Chalice (Eldrazi) see meaningful WR shifts

**For Manu's storm port**: the fix is a correctness-only commit; don't expect calibration improvement. **Drop-in tax-only helper template is in lesson 28**.

### What didn't get attempted

- Opportunistic batch on belcher / sneak_a / sneak_b / depths — dropped after the TES result confirmed combo decks generally show minimal aggregate WR move from this fix. The same timing argument applies to all storm-class combo decks.
- Worth a future audit of NON-storm decks with bypass patterns (e.g. eldrazi's own bypasses, if any) since those would be operating against opponents who actually have time to land Chalice.

## Cross-project lesson 28 (Modern alert)

The bypass pattern is **systematic** — found in infect (7 sites), affinity (5 sites). Raw site counts of `player.remove_from_hand` calls in unaudited deck files:

| File | `remove_from_hand` count | Notes |
|---|---|---|
| `decks/tes.py` | **33** | Storm combo — highest exposure; would ignore Chalice on 1 vs prison/painter/uwx |
| `decks/belcher.py` | 7 | Storm-class combo |
| `decks/sneak_b.py` | 7 | |
| `decks/affinity.py` | 1 (post-fix) | Sink into Stupor manual cast |
| `decks/depths.py` | 5 | |
| `decks/sneak_a.py` | 5 | |
| `decks/goblins.py` | 6 | Activated abilities — verify each site |
| `decks/eldrazi.py` | 3 | |
| `decks/cloudpost.py` | 2 | |
| `decks/eight_cast.py` | 2 | |

The user reported affinity is also too high in Manu (Modern). The same bypass pattern is the likely culprit. **Lesson 28 added to `CROSS_PROJECT_SYNC.md` with detection one-liner + fix template** — recommend Manu run the audit immediately.

Commit: `b107530`.

## Iter 3 — Lands audit (REVERTED, useful findings)

After iter 2, attempted to attack the calibration-health #1 priority — **lands** (T1, sim 0.416, real meta share 6 %, gap -8.4pp). 5-opp baseline at n=200 against worst matchups: dnt 0.190, uwx 0.290, dimir_d 0.415, oops 0.265, ocelot 0.330 — avg **0.298**.

### Findings
1. **`_strategy_lands` deploys ZERO of these cards** despite them being in the deck:
   - **Exploration** ×4 (1G enchantment, "play extra land per turn") — `game.py:play_land` has hard `land_played_this_turn` limit, no engine support for Exploration's bypass
   - **Life from the Loam** ×4 (1G sorcery, "return 3 lands from GY + dredge 3") — no dredge mechanism, no Loam recursion logic
   - **Once Upon a Time** ×3 (free first spell, dig 5 take creature/land) — no cast logic
   - **Malevolent Rumble** ×4 (1G sorcery, dig 4 with experience-counter discount)
2. **Decklist is also missing real-list staples**: Glacial Chasm (life-prevention lock vs aggro), Punishing Fire + Grove of the Burnwillows engine. Real Lands grinds via these; the simulator's deck has no equivalent grind plan.
3. **Dead Mardu/UWx combat code copied into `_strategy_lands` (engine.py:3733-3756)** — references `bug_max_blocker_toughness`, `mardu_desperate`, special-cases `bowm` (Bowmasters) and `tamiyo` tags that do not exist in the lands decklist. The code accidentally still works (Marit Lage is neither tag, so always attacks) but it's dead weight. **Same code is also copy-pasted into `_strategy_dimir` (L4396) and `_strategy_dimir_flash` (L4525)** — there the Bowmasters/Tamiyo special-cases ARE relevant since those decks run them, so the logic is right but variable names (`bug_max_blocker_*`, `mardu_desperate`) are stale leftovers from an earlier copy. Refactor target.

### Attempted fix (reverted)
Added Once Upon a Time deployment (free first spell, dig top 5 of library, take a land prioritising depths > stage > saga > yavimaya). Cleaned up the dead Mardu/UWx combat block in `_strategy_lands` to a simple "attack with all non-summoning-sick creatures".

5-opp results (n=200): avg 0.298 → 0.311 (+1.3pp). Re-ran at **n=500** to filter noise: avg → **0.316 (+1.8pp toward 50%)**. Mixed per-matchup:
- dnt 0.190 → 0.246 (+5.6pp) ✅
- oops 0.265 → 0.310 (+4.5pp) ✅
- uwx, dimir_d, ocelot — within noise (±1pp at n=500)

**Net: +1.8pp combined — below the 3pp threshold per protocol; reverted.** OUaT alone is too marginal — Lands genuinely needs the engine cards (Loam dredge, Exploration's extra-land-drop, Glacial Chasm life prevention). That's 200-400 lines of careful work, not a single-iteration fix.

### Lessons
1. **Lands is the second-clearest example of `CROSS_PROJECT_SYNC.md` lesson #24** — a deck whose simulator is missing real-world cards (Glacial Chasm) AND missing core mechanic support (dredge for Loam, Exploration's extra-land-drop). Heuristic improvements alone can't recover it.
2. **The dead Mardu/UWx combat block in 3+ strategies** is a code-hygiene refactor target. Lands' is genuinely dead; dimir/dimir_flash have stale variable names but live logic. Worth a focused "extract `_default_combat_with_held_value_engines()` helper" pass in a future session.
3. **OUaT alone is +5.6pp vs DNT and +4.5pp vs Oops** — these specific matchups DID respond. If the user wants to ship just the OUaT addition + dead-code cleanup as a code-correctness commit (without claiming WR improvement), it would benefit those two matchups; trade-off is matrix noise on the 3 noisy ones. Defer to user judgement.

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
