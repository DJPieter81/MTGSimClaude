# MTGSimClaude — Planning Reference

> **Purpose:** Claude Code planning-mode context file. Read this before any session to understand system state, architecture, performance baselines, and known issues.
> **Last benchmarked:** 2026-04-12 | **Repo:** `https://github.com/DJPieter81/MTGSimClaude.git`

---

## 1. System overview

MTGSimClaude is a Legacy Magic: The Gathering Monte Carlo simulator. It models 38 tournament decks with AI-driven strategy, runs matchup sweeps, and produces three output products: a metagame matrix heatmap, per-deck guides, and interactive Bo3 replayers.

**Core loop:** Decklist import → deck module generation → Monte Carlo simulation → results JSON → HTML/JSX visualisation.

**Deliverables:** Meta matrix (HTML), deck guides (HTML), Bo3 replayers (HTML), marketing showcase (`mtgsimclaude_showcase.html`), planning reference (`PLANNING_REFERENCE.md`).

---

## 2. Architecture map

```
┌─────────────────────────────────────────────────────────────────┐
│                      OUTPUT PRODUCTS                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Meta Matrix   │  │ Deck Guide   │  │ Bo3 Replayer         │   │
│  │ HTML+JSX      │  │ HTML         │  │ HTML                 │   │
│  │ 5 data layers │  │ 7 visual     │  │ 17 play categories   │   │
│  │ D,DA,C,I,ARCH │  │ components   │  │ 6 board zones        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
└─────────┼─────────────────┼─────────────────────┼───────────────┘
          │                 │                     │
┌─────────┴─────────────────┴─────────────────────┴───────────────┐
│                      DATA PIPELINE                              │
│  meta_results.py    verbose_table.py    meta_audit.py           │
│  results/*.json     card extraction     outlier detection       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      SIMULATION CORE                            │
│                                                                 │
│  sim.py (91K)         — run_game, run_sweep, run_meta_matrix    │
│  engine.py (249K)     — play_turn, 19 strategy fns, counters    │
│  game.py (49K)        — GameState, PlayerState, mulligan, EV    │
│  rules.py (29K)       — Card, Permanent, ManaPool, MTGRules     │
│  interaction.py (11K) — classify_threat, best_proactive_target  │
│  interaction_model.py — FoW priority, save rates                │
│                                                                 │
│  Key: symmetric p1/p2 engine. Rules enforced at infra level.    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      DECK LAYER (38 decks)                      │
│                                                                 │
│  cards.py (119K)      — make_*_deck(), DECKS, MATCHUP_META      │
│  decks/*.py           — 22 full strategy + 17 proxy modules     │
│  deck_registry.py     — auto-discovery, no engine edits needed  │
│  import_deck.py       — paste-to-play decklist importer         │
│                                                                 │
│  Meta shares: T1 (≥5%): ocelot 12%, dimir 6%, dimir_b 5%,      │
│  lands 6%, oops 6%, doomsday 6%, prison 6%, ur_delver 6%       │
│  T2 (3-4%): sneak_a, sneak_b, show, painter, eight_cast, uwx   │
└─────────────────────────────────────────────────────────────────┘
```

**Total codebase:** 25,842 LoC across core + deck modules.

---

## 3. Performance baselines (benchmarked 2026-04-12)

### Speed
| Metric | Value |
|--------|-------|
| Single game | 2.5ms avg (91× faster per game vs Modern's 227ms; 367× per Bo3 vs Modern's 680ms) |
| 200-game sweep | 0.50s |
| Full 36×36 matrix (n=30) | ~94s (1.6 min) |
| Full 36×36 matrix (n=200) | ~10.5 min (estimated) |
| Parallelised (3× speedup) | ~3.5 min at n=200 |

### Statistical properties
| Metric | Value |
|--------|-------|
| σ at n=200 | ±3.9% (5-run test, burn vs dimir) |
| σ at n=30 (current matrix) | ±7% noise floor |
| Convergence point | ~n=500 for ±2% stability |
| Mean WR across all matchups | 49.1% (near-symmetric) |
| WR range | 2%–95% |
| Avg game length | 5.7 turns |
| Avg kill turn | 5.3 |

### Test suite
| Metric | Value |
|--------|-------|
| Rules tests | 137/137 pass |
| Deck modules | 39 files (22 full, 17 proxy) |
| Strategy functions (engine.py) | 19 |

---

## 4. Accuracy validation

### Known matchup spot-checks (sim vs Legacy consensus)

| Matchup | Sim WR | Expected range | Status |
|---------|--------|---------------|--------|
| Burn vs Storm | 65% | 55–75% | ✓ Pass |
| Burn vs Dimir | 71% | 55–80% | ✓ Pass |
| Infect vs Burn | 40% | 35–55% | ✓ Pass |
| Reanimator vs Dimir | 50% | 35–65% | ✓ Pass |
| Eldrazi vs Storm | 79% | 55–80% | ✓ Pass |
| Storm vs D&T | 32% | 55–80% | ✗ FAIL |
| Oops vs Burn | 31% | 55–80% | ✗ FAIL |

**Pass rate: 5/7 (71%).**

Root causes for failures:
- **Storm vs D&T:** D&T's Thalia tax is over-penalising Storm. Strategy may not correctly model Storm's ability to generate enough mana to overcome the +1 tax.
- **Oops vs Burn:** Oops All Spells should win pre-board via T1 kills faster than Burn can race, but the strategy isn't deploying the combo reliably enough.

### Symmetry (d1_vs_d2 + d2_vs_d1 ≈ 100%)

| Metric | Value |
|--------|-------|
| Pairs within ±5% | 532/1260 (42%) |
| Pairs within ±1% | 68/1260 (5%) |
| Outliers >15% | 60 pairs |
| Worst deviation | 41% (mardu vs ocelot) |

**Main offenders:** Mono Black (appears in 5 of top 8 outliers), Mardu, Ocelot. All are proxy-strategy decks where p1/p2 dispatch is asymmetric.

---

## 5. Known limitations

### Critical
1. **No static lock persistence.** Trinisphere CMC override works (pre-dispatch adjustment), but Karn's artifact lockout, Chalice on specific CMCs, and other lock states don't persist across turns correctly. Lock-based decks (Trini Tron Karn, Prison) simulate below real-world performance.
2. **17 proxy decks.** Decks with ≤5K strategy modules use simplified AI. These have lower fidelity and cause most symmetry outliers.
3. **G1-only matrix.** `run_meta_matrix` runs game-1 only. Bo3 with sideboarding exists in `run_any_bo3()` and the replayer but isn't used for batch matrix runs.

### Moderate
4. **n=30 noise floor.** Current matrix uses 30 games per matchup → ±7% Monte Carlo noise. Minimum n=200 recommended for stable data.
5. **60 symmetry outliers.** Proxy decks with asymmetric strategy dispatch cause d1+d2 ≠ 100%. Fix requires either making all strategies symmetric or running both orderings and averaging.

### Minor
6. **No planeswalker loyalty tracking.** Planeswalkers are modelled as static permanents, not tick-up/tick-down engines.
7. **No stack interaction.** Spells resolve immediately; no response windows for split-second or priority passing.

---

## 6. Development rules

### Never do
- Re-run matrix if `results/*.json` files exist (unless user explicitly asks)
- Use MTGSimManu imports (this is Legacy, not Modern)
- Rebuild matrix HTML from scratch — use `templates/reference_meta_matrix.html` + swap data constants
- Forget `pills()` function in matrix HTML (verify with grep after rebuild)
- Produce text-wall metagame sections — use 7 visual components
- Show AI reasoning by default in replayer — use toggle
- Skip the provenance footer

### Always do
- `git pull` before starting work
- Re-read `CLAUDE.md` to catch changes
- Spot-check 3–5 matchups with `run_sweep(d1, d2, n_games=200)` against matrix JSON to detect stale data
- Use `run_symmetric_game()` to verify key matchups before building dashboards
- After any matrix HTML rebuild: `grep 'function pills' output.html`

### Card/deck API signatures (common bugs)
```python
artifact(name, cmc, mana_cost, tag='')           # NO colors param
creature(name, cmc, mana_cost, colors, power, toughness, tag='', ...)
basic_land()                                       # NO tag param
utility_land(name, mana_list, tag)                 # for Karakas, Wasteland
utility_land('Ancient Tomb', ['C','C'], 'tomb', life_loss=2)  # sol land
```

### Results API
```python
# run_sweep returns:
{'p1_wr': float, 'p1_wins': int, 'p2_wins': int, 'avg_length': float, 'avg_kill': float}

# Matrix JSON keys:
'deck1_vs_deck2' → float (0–1)

# load_matrix() with no args → latest file
# load_matrix('specific_file') → that file
```

---

## 7. Output product specs

### Meta matrix (HTML)
- Template: `templates/reference_meta_matrix.html`
- 5 data constants: `D` (WRs), `DA` (deck profiles), `C` (card stats), `I` (interactions), `ARCH` (archetype map)
- 9 required JS functions: `pills`, `wc`, `tc`, `muc`, `getCT`, `tierOf`, `tierTag`, `getWR`, `closeDet`
- Weighted WR: T1+T2 opponents only (flat ≥50%). Thresholds: 58/48/33 weighted, 65/50/35 flat
- Tier chips: S/A/B/C

### Deck guide (HTML)
- Light theme, max-width 960px, system sans-serif
- Hero stat grid (4-col), card role badges, Scryfall hovers, phase timeline
- Kill turn chart, hand archetype WR bars (2,000 games), real sim hands
- Metagame strategy: 7 visual components (archetype bars, tournament histogram, triptych, arc bar, delta chart, danger cards, timeline)

### Bo3 replayer (HTML)
- API: `generate_html(opponent, seeds=[42,99,7], protagonist='deck')`
- Light theme, max-width 920px
- 17 play categories, 6 board zones, combat detail boxes
- Reasoning hidden by default (· toggle), response badges (⚡), life chart SVG
- CLI: `python3 game_replay.py opponent --pro deck --bo3 42 99 7`

---

## 8. AI architecture analysis

### Current approach: rule-tree dispatch

Legacy uses hard-coded strategy functions — 19 functions in `engine.py` with 787 if/elif branches total (avg 41 per strategy). Decisions are binary: "can I do X? then do X." No comparison between alternative plays.

**Quantified complexity:**
- 73 unique card tags checked via `.tag ==` in engine.py
- 76 property-based checks (`.is_creature()`, `.lock_piece`, etc.)
- 184 tag-based checks (the brittle kind)
- 3,228 lines of strategy code in engine.py alone

**How it works (Storm example):**
```
_strategy_storm() →
  1. Check for cantrips → cast if affordable
  2. Simulate ritual chain mana (respects Trinisphere, Chalice)
  3. Test 6 kill conditions (kill_A..kill_F) — first match wins
  4. If can_kill AND safe_to_combo → execute
  5. No evaluation of "is this the right turn to go off?"
```

### Sister project comparison: MTGSimManu (Modern)

Modern uses EV-based scoring — every legal play gets a float, pick highest. GoalEngine adjusts weights per game phase.

| Dimension | Legacy (rule tree) | Modern (EV scoring) |
|-----------|-------------------|---------------------|
| Decision model | Binary if/elif | Continuous float scoring |
| Scaling | O(decks) — new function per deck | O(1) — same engine, new weights |
| Speed | 2.5ms/game (91× faster) | 227ms/game |
| Calibration risk | None — logic is right or wrong | High — one bad coefficient breaks a deck |
| Combo modeling | Excellent (6 explicit kill lines) | Weak (20× ritual penalty bug) |
| Fair Magic | Weak (first match wins) | Strong (all options compete) |
| Debugging | Read the if-chain | Trace through EV pipeline |

### Hybrid path (recommended evolution)

Keep hand-written kill conditions for combo decks. Replace creature/removal/land deployment with EV scoring. Adopt GoalEngine for game-phase awareness.

**Phase 1 — GoalEngine (no EV):** Add game phase tracking to strategy functions. Storm should know it's in "survive Thalia" phase before "go off" phase. This fixes Storm-vs-D&T without changing the decision model.

**Phase 2 — EV for fair plays:** Score creature deployment, removal targeting, and land drops numerically. Keep combo kill logic as-is. ~60% of if/elif branches are "which creature to deploy" decisions that EV handles better.

**Phase 3 — Full EV (future):** Replace remaining strategy functions. Requires solving the calibration problem first — Modern's Wrenn=-0.1 and ritual×20 bugs show this isn't free.

---

## 9. Cross-pollination: merged proposal (Legacy ↔ Modern)

Two proposals were produced independently — one from each project. This section merges both into a single prioritised plan. Source marked as [L] (our analysis) or [M] (Modern's proposal).

### New modules to port from Modern

**1. Strategic logger + `--trace` mode [M]** (LOW effort, HIGH impact)
Port `strategic_logger.py` pattern (279 lines). Add `log_decision(candidates, chosen, reason)` to each `_strategy_*` function. This is the **prerequisite** for the LLM judge audit — without traces, there's nothing to audit. Add `--trace` flag to `sim.py`.

**2. Clock-based evaluation [M]** (MEDIUM effort, HIGH impact)
Port `clock.py` (328 lines, zero deps). `combat_clock() = ceil(opp_life / effective_power)`. Every creature, removal, and burn spell scored by clock-delta. This is better than "adopt EV scoring" because it's a specific composable unit, not arbitrary floats. Refactor `classify_threat()` to return clock-delta values instead of categories (MUST/HIGH/MED/LOW → +3.5/+1.2/+0.3/-0.1). **Keep per-deck strategy functions** — clock is the shared language, not a replacement.

**3. Bayesian Hand Inference [M]** (HIGH effort, HIGH impact)
Port `bhi.py` (275 lines). Track `P(counter)`, `P(removal)`, `P(burn)` for opponent's hand. Updates on priority passes (didn't counter → lower P(counter)), spells cast, mana availability.
**Key insight:** Legacy's `interaction_model.py` already has hypergeometric priors — `_prob_at_least_one(copies, cards_seen)`. Seed BHI with these. Modern's BHI is generic; ours would start with "this deck runs 4 FoW, 2 Daze → initial P(free_counter) = 0.68 after seeing 7 cards". **Depends on:** clock eval (#2).

**4. Declarative gameplans [M]** (MEDIUM effort, MEDIUM impact)
Create `gameplans/*.json` for each deck: goal sequences, mulligan keys, card roles, combo steps. Build lightweight `GoalEngine` that reads these. Pass `current_goal` into strategy functions. For 17 proxy decks: auto-generate basic gameplans from deck composition — a generated gameplan is better than a proxy strategy function.

### Infrastructure fixes (both proposals agree)

**5. Symmetry averaging [L+M]** (LOW effort, HIGH value)
Run both orderings for every matchup. Average: `final_wr = (wr_as_p1 + (1 - wr_as_p2)) / 2`. Flag any pair where `|d1 + d2 - 100| > 10%`. Automate as post-matrix step. Eliminates 60 outlier pairs without fixing proxy strategies.

**6. Bo3 in matrix [L+M]** (MEDIUM effort, HIGH impact)
Wire `run_any_bo3()` into `run_meta_matrix()`. Build sideboard plans for all 22 full-strategy decks. Runtime: ~3× but Legacy is 367× faster per game, so still <5 min for full matrix. Report G1, post-board, and overall WR separately.

**7. Post-action verification [M]** (LOW effort, HIGH value)
```bash
# After matrix rebuild
grep 'function pills' output.html
grep 'D\[' output.html | wc -l
python3 -c "import json; d=json.load(open('results/latest.json')); print(len(d))"
# After deck import
python3 -c "from cards import DECKS; print(len(DECKS))"
python3 -c "from sim import run_sweep; print(run_sweep('new_deck','burn',10))"
# After strategy edit — symmetry smoke test
python3 -c "from sim import run_sweep; a=run_sweep('edited','dimir',200); b=run_sweep('dimir','edited',200); print(f'{a[\"p1_wr\"]:.0%} + {b[\"p1_wr\"]:.0%} = {a[\"p1_wr\"]+b[\"p1_wr\"]:.0%}')"
```

**8. LLM judge audit [L]** (MEDIUM effort, HIGH impact)
Adapt Modern's 6-expert methodology. Run 200+ games with `--trace`, grade by domain. **Depends on:** strategic logger (#1).

### Preserve (DO NOT change)

- **Per-deck strategy functions** — Modern's generic `_score_spell()` can't express "Wrenn is one of the best cards in Modern" (scores all planeswalkers at -0.1 EV). Keep deck-specific knowledge, use clock as shared value unit.
- **Card-level interaction knowledge** — `interaction_model.py` priors are better starting points than Modern's generic BHI. Preserve and use as Bayesian seeds.
- **Speed** — 2.5ms/game enables rapid iteration. Profile any adopted module before integration. Target: <5ms/game after all adoptions.
- **In-code card builders** — No MTGJSON (6.5s load, 400MB memory). Our 119K `cards.py` is faster and needs no singleton.

### Implementation order

| # | Task | Effort | Impact | Source | Dependency |
|---|------|--------|--------|--------|------------|
| 1 | Strategic logger + `--trace` | LOW | HIGH | [M] | None |
| 2 | Post-action verification | LOW | HIGH | [M] | None |
| 3 | Symmetry averaging | LOW | HIGH | [L+M] | None |
| 4 | Clock-based evaluation | MEDIUM | HIGH | [M] | None |
| 5 | Bo3 in matrix | MEDIUM | HIGH | [L+M] | SB plans |
| 6 | Declarative gameplans | MEDIUM | MEDIUM | [M] | None |
| 7 | LLM judge audit | MEDIUM | HIGH | [L] | #1 |
| 8 | BHI with Legacy priors | HIGH | HIGH | [M] | #4 |

Items 1-3: one session. Items 4-5: one session. Items 6-8: incremental.

### Metrics after adoption

| Metric | Current | Target |
|--------|---------|--------|
| Spot-check pass rate | 71% (5/7) | 85%+ (add 5 more matchups) |
| Symmetry outliers >15% | 60 pairs | <10 |
| Per-game speed | 2.5ms | <5ms |
| Proxy deck count | 17 | <5 |
| LLM judge grade | None | C+ |
| Strategy trace coverage | 0% | 100% of full-strategy decks |

---

## 10. Priority backlog (severity-classified)

### P0 — Accuracy blockers

1. **Fix Storm vs D&T** (32% sim, expected 55-80%) — `_strategy_storm` doesn't model ritual chain under Thalia +1 tax correctly. The `_ritual_cost()` function respects Trinisphere but may not account for Thalia. Check `opp_can_cast()` for Thalia interaction with ritual CMC.
2. **Fix Oops vs Burn** (31% sim, expected 55-80%) — `_strategy_oops` combo deployment rate too low. T1 kill rate should be ~40%. Trace with `run_meta.py --verbose oops burn -s 42` to identify where combo fizzles.

### P1 — Symmetry & coverage

3. **Upgrade proxy decks** — Mono Black, Mardu, Boros, Elves, Ocelot are worst symmetry offenders (5 of top 8 outlier pairs). Priority: Ocelot (12% meta share), Mono Black (worst offender), Mardu.
4. **Increase matrix N** — n=30 → n=200. ~10 min with parallelisation.
5. **Add G2/G3 to matrix** — Wire `run_any_bo3()` into matrix pipeline.

### P2 — Architecture evolution

6. **Port strategic logger** — prerequisite for all debugging improvements.
7. **Port clock.py** — shared value unit for all strategy functions.
8. **Add GoalEngine / gameplans** — JSON-driven phase tracking.
9. **Static lock persistence** — Turn-over-turn state for Karn, Chalice, Prison.
10. **BHI with Legacy priors** — Bayesian counter/removal inference.
11. **LLM judge audit** — 6-expert panel after trace infrastructure exists.
12. **Meta audit expected ranges** — `EXPECTED_RANGES` dict for automated outlier detection.

---

## 11. File size reference

| File | Size | Role |
|------|------|------|
| engine.py | 249K | Turn execution, all AI |
| cards.py | 119K | Card database, deck builders |
| sim.py | 91K | Game loop, sweeps, matrix |
| game.py | 49K | State management |
| game_replay.py | 45K | HTML replayer generator |
| decks/ (total) | 594K | 39 deck strategy modules |
| rules.py | 29K | MTG rules engine |
| verbose_table.py | 26K | Card data extraction |
| config.py | 22K | Constants, categories |
| meta_audit.py | 20K | Outlier detection |
| hypothesis_testing.py | 36K | Statistical analysis |
