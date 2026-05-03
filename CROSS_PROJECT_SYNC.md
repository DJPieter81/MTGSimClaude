# Cross-Project Sync — MTGSimManu (Modern) ↔ MTGSimClaude (Legacy)

> **Last updated:** 2026-04-25 (iter 12 — diminishing-returns finding on decklist audits; the last 4 audit candidates need deeper strategy work, not single-card edits)
> **Read by:** Both CLAUDE.md files, Cowork, Claude Code
> **Rule:** Check this file before starting cross-project work

---

## Shared Modules (Modern maintains, both use)

| Module | Lines | Purpose | Legacy status |
|--------|-------|---------|---------------|
| `clock.py` | 328 | Turns-to-kill calculator | ✅ Adopted |
| `bhi.py` | 275 | Bayesian hand inference | ✅ Adopted |
| `strategic_logger.py` | 279 | AI reasoning traces | ✅ Adopted |
| `gameplan.py` | 545 | Declarative goal sequences | ✅ Adopted |

Keep these portable — no project-specific imports.

---

## Legacy → Modern (infrastructure adoption)

| # | Feature | Legacy file | Lines | Modern status | Priority |
|---|---------|-------------|-------|---------------|----------|
| 1 | Plugin deck architecture | `deck_registry.py` | 161 | ❌ Uses monolithic `modern_meta.py` | HIGH |
| 2 | Parallel sim execution | `parallel.py` | 111 | ❌ Serial only (2hrs for full matrix) | HIGH |
| 3 | Statistical significance | `hypothesis_testing.py` | 935 | ❌ No stat testing on WR diffs | HIGH |
| 4 | Metagame audit | `meta_audit.py` | 547 | ⚠️ Partial (`scan_results.py`) | MED |
| 5 | LLM game judge | `llm_judge.py` | 237 | ❌ Proposed but not implemented | MED |
| 5b | Neural-pivot prototype: state encoder + value scorer + LLM gate + 1-ply lookahead + BHI ensemble + multi-step rollout + per-decision Q-net (mid-game + mulligan) | `state_encoder.py`, `neural_scorer.py`, `neural_gates.py`, `lookahead.py`, `determinization.py`, `gamestate_clone.py`, `rollout.py`, `rollout_policy.py`, `q_scorer.py`, `train_q_scorer.py`, `mulligan_features.py`, `mulligan_q.py`, `train_mulligan_q.py`, `scripts/collect_q_data.py`, `scripts/collect_mulligan_q.py`, `neural_eval.py`, `train_neural_scorer.py`, `scripts/collect_tes_traces.py` | ~2 100 | ❌ Not started | MED |
| 6 | Post-sim verification | `verify.py` | 174 | ❌ Has tests but no post-sim checks | MED |
| 7 | Card validation | `card_validation.py` | 548 | ⚠️ Partial (oracle_parser) | LOW |
| 8 | Rich terminal tables | `verbose_table.py` | 666 | ❌ Raw text output | LOW |
| 9 | One-command refresh | `refresh_all.py` | 70 | ⚠️ Cowork task, no script | LOW |

### Adoption notes
- **#1 Plugin arch:** Would let users add decks by dropping a file. Currently requires edits to `modern_meta.py` + `gameplans/*.json` + `strategy_profile.py`. Legacy's `deck_registry.py` auto-discovers on import.
- **#2 Parallel:** Modern's 0.68s/Bo3 × 12,000 pairs = 2.3hrs serial. Legacy does 38 decks in minutes via multiprocessing. Would cut Cowork pipeline from 95min to ~20min.
- **#3 Hypothesis testing:** Modern reports 60% WR but can't say if it's significantly different from 50%. Legacy's `hypothesis_testing.py` adds p-values and confidence intervals. Critical for validating that sim WR differences are real.
- **#5b Neural-pivot prototype.** Hybrid LLM-gate + small-NN-scorer + 1-ply lookahead + BHI-jittered ensemble + multi-step rollout. All opt-in via four independent flags (`use_neural_gates`, `use_neural_scorer`, `use_ensemble`, `use_rollout`) threaded through `run_game` → `gs` → strategy. Default off → byte-identical to heuristic path. Per-deck checkpoints at `models/<deck>_scorer.pt` + `models/<deck>_scorer_norm.json`. Honest result on Legacy at n=200/side, NN-only: best config Δ = **+0.3 pp** on `ur_delver_vs_burn` (1-ply NN scorer); rollout K=5 is WR-neutral with the heuristic gate restored, regresses without it. Infrastructure is sound; the elective decision space inside one turn is too narrow for the chosen hooks to swing combined WR meaningfully. Read the **Lessons learned** section below before adopting in Modern — several non-obvious traps documented there.

### Lessons learned (read before adopting in Modern)

These are honest findings from two iterations of building / measuring the prototype on Legacy. Most are negative-result lessons that save time on the Modern port.

1. **State-value scorer alone is not enough.** Training on `state → P(win at game end)` gives near-identical scores for slightly-different post-states (e.g. "Bolt face" vs "Bolt creature"). Per-decision discrimination needs either (a) multi-step rollout (`rollout.py` + `rollout_policy.py` here) or (b) `(state, action) → won?` Q-style training. (a) is sound but loses the rest-of-current-turn semantics; (b) needs counterfactual data we don't yet trace.

2. **Multi-step rollout requires a heuristic gate, not full override.** First Lever-4 run let rollout fire whenever a creature target existed; it voted face mid-game in spots where keeping creature targets mattered for clock and regressed combined WR by 0.7pp. With the heuristic's life-threshold gate restored (rollout only fires when face is at least life-plausible), rollout is WR-neutral. Translation for Modern: don't replace the heuristic with rollout — **gate rollout to fire only at the same decision boundary the heuristic already considers**, then let it pick between the candidates.

3. **The trace-record context-manager pattern is the right shape.** `state_encoder.record(...)` is a no-op when no collector is active. Strategies sprinkle `record()` calls at every decision; collection happens out-of-band via `with collect() as rows:`. Costs nothing in production. Modern should adopt this verbatim.

4. **Opt-in flags must default to False AND must produce byte-identical behaviour when off.** Verified by re-running the same seed before/after wiring and comparing `winner` / `kill_turn` / `log_lines`. This is non-negotiable for Modern's matrix path which is on the critical path of the Cowork pipeline.

5. **Use `claude-api` skill conventions for the LLM advisor.** Specifically: model = `claude-opus-4-7`, `thinking={"type": "adaptive"}` (no `budget_tokens`, no `temperature` — both 400 on Opus 4.7), `output_config={"effort": "low"}` for sparse strategic gates, `client.messages.parse()` with Pydantic schemas for structured outputs, top-level `cache_control={"type": "ephemeral"}` on the system prefix. Static doctrine + per-gate instruction prefix are cacheable; the volatile per-call game-state JSON sits in the user message after the cached prefix.

6. **Fail-soft is mandatory for any LLM call.** Every gate is wrapped in `try/except` → returns `None` on any error → strategy falls back to heuristic. Verified when the sandbox lacked an API key: the eval still ran, the gate decisions silently fell through to heuristic, no game forfeited.

7. **Per-deck scorers, not one big multi-deck scorer.** Cross-deck transfer was untested but expected to be poor without conditioning. Per-deck val acc was 78–80 %; a single shared model would average toward the mean. Modern's modular deck registry naturally supports `models/{deck_slug}_scorer.pt`.

8. **The state encoder is deck-agnostic.** All 41 features come from `gs`/`player`/`opponent` and are populated for any deck pair. The encoder doesn't need to know which deck is playing — that's encoded in the `mc_*` matchup-category one-hots and the `bhi_*` HandBelief features. Same encoder works for TES and UR Delver.

9. **BHI is the right anchor for hidden-info reasoning.** Both ensemble determinization (`determinization.hypothetical_bhi`) and the LLM prompt construction read from `bhi.HandBelief`. Modern's BHI is already adopted (`✅` in shared modules table) — the neural pivot rides on top of it.

10. **GameState is `copy.deepcopy`-safe** — verified by `gamestate_clone.test_clone_roundtrip()`. No closures or non-pickleable refs hiding in the dataclass. Modern's `GameState` uses the same dataclass shape; should clone cleanly with the same approach.

11. **Rollout RNG hygiene is critical.** Rollouts call `random.*` from inside strategies; `random` is a global module. Always: capture state with `random.getstate()`, seed with a per-rollout deterministic seed (e.g. `gs.turn * 1000 + ci * 100 + k`), then `random.setstate(saved)` in a `finally`. Otherwise the production game's RNG state is corrupted by the rollouts and downstream determinism breaks.

12. **Defuse neural toggles inside the rollout body.** When the rollout-policy plays the heuristic forward on a clone, the clone inherits `gs.use_neural_*` from the original. Inside `rollout_to_end` we explicitly `gs.use_neural_gates = False; gs.use_neural_scorer = False; gs.use_ensemble = False; gs.use_rollout = False` so the rollout policy IS the heuristic (no nested neural calls, no infinite loops). This is mandatory.

13. **K (rollouts per candidate) can be small.** K=5 / K=10 / K=15 produced identical WR at n=100 in our K-sensitivity sweep. The eval cost grows linearly in K but the marginal information after K=5 is small for a 5-turn horizon. Default K=5 is fine; bump only if the candidate distinction is on a knife-edge.

14. **Don't paste API keys in chat.** During this work the user pasted a `ghp_…` GitHub PAT (rejected by the Anthropic SDK) and later a real `sk-ant-…` key (had to be revoked). The right pattern is `ANTHROPIC_API_KEY=sk-ant-... python3 run_meta.py ...` or a gitignored `.env`. Surface this in any onboarding doc.

15. **Cost containment for live evals.** With prompt caching, a 200-game ablation with 5 LLM-gate calls per game lands at ≤ \$2 at Opus 4.7 prices. Without caching it would be ~10× more. The static prefix MUST be ≥ 4 096 tokens for Opus-tier caching to engage; verify via `usage.cache_read_input_tokens` on every response.

16. **Q-style discriminator beats value-scorer at per-decision discrimination.** Trained on `(state ⊕ action_one_hot) → rollout_won` triples generated by `scripts/collect_q_data.py`. On UR Delver's `ur_bolt_mode` decision: **94.2 % val acc vs 68.3 % majority baseline (+25.8 pp lift)** — vs the value-scorer's +10.6 pp on the same data. The architectural change (action conditioning) is doing real work. Architecture is `(41 + |actions|) → 32 → 16 → 1` sigmoid; one model per `decision_type` so the action-vocabulary stays small. Counterfactual data generation is cheap: 1 000 games × 5 opponents × K=3 rollouts per candidate produced 600 rows in **4.6 s**.

17. **THE BOTTLENECK IS DECISION SELECTION, NOT DECISION QUALITY.** This is the single most important finding from iteration 4 and the one that changes how we should sequence neural work going forward. Empirical evidence: a Q-net at 94 % val acc on `ur_bolt_mode` produces **+0.0 pp combined WR** at n=200/side on `ur_delver_vs_burn`. Diagnostic: Q-scorer fires 22 times across 50 games vs dimir; 4 of those are real face-overrides; 18 agree with the heuristic. The 4 overrides don't add up to a measurable WR shift because the Bolt-mode decision is genuinely low-leverage on UR Delver — the heuristic was already right most of the time, and the few disagreements happen in ambiguous mid-game spots that the rest of the game can recover from. **Translation for Manu**: do not adopt the neural pipeline for any decision until you've identified one with high game-leverage (mulligan, deploy-threat order, "cast cantrip vs hold mana for counter", attack/hold). Hooking 5 such decisions is worth more than perfecting any single one. Picking the right *decisions to hook* is the open research direction; the *modelling toolkit* (value-scorer, rollout, Q-net, LLM gate) is in place and works.

18. **Recursion trap: defuse `collect_q_data` inside the rollout body.** The first build of `record_q` ran rollouts that themselves triggered `record_q` on the cloned state, since `gs.collect_q_data` was True on the clone — infinite recursion, processes pegging CPU at 99 %. Fix: in `rollout.py` set `gs.collect_q_data = False` (along with `use_q_scorer`, `use_rollout`, etc.) before stepping the clone forward. The same defensive pattern applies to ANY new flag that triggers fork-style rollouts. Auditing rule: every new neural toggle that recurses through `play_turn` MUST be added to the `rollout.py` defuse list.

19. **Mulligan Q-net (Lever 6) — feasible but caps at 0pp combined WR.** Built a counterfactual mulligan trainer: for each opening hand, run K=5 full-game rollouts of "keep" and K=5 rollouts of "mull-to-6", label each rollout, train `(hand_features ⊕ {keep,mull}) → P(win)`. Pipeline: `mulligan_features.py` (27-feature hand encoder) + `scripts/collect_mulligan_q.py` (10 000 rows in 16 s for 200 hands × 5 opps × 2 actions × K=5) + `mulligan_q.py` + `train_mulligan_q.py`. Val acc: **62.7 % vs 56.6 % baseline (+6.1 pp lift)** — solid signal. Combined WR delta at n=3 000 per cell: **−0.1 pp** across 5 matchups (mixed per-matchup: +1.7pp oops, +1.2pp dimir, −0.7pp burn, −0.2pp show, −2.3pp storm). Even with a confidence threshold (τ=0.10) so the Q-net only overrides when it's clearly more informative than the heuristic, the net combined WR is flat.

20. **Mulligan policy is role-dependent (going first vs going second).** Without a `goes_first` feature, the mulligan Q-net at K=5 trained on UR-Delver-as-P1 only and added a +1.5 pp P1-only WR lift but a -1.5 pp P2 lift, netting to 0 pp combined. With `goes_first` baked into the hand-feature vector, val acc rose from +3.2 pp to +6.1 pp lift, and per-side regressions reduced. Translation for Manu: any hand-only model needs an explicit `on_play / on_draw` feature, or it'll silently average away half the signal.

21. **Coin-flip-before-mulligan matches real Magic CR 103.1.** The original Legacy simulator did mulligans *first*, then coin-flipped — wrong order. Fixing this (one-line edit in `sim.run_game`: hoist `p1_goes_first = random.random() < 0.5` above the mulligan block) is required for any mulligan policy that wants to know the role at decision time. Verify Manu's `run_game` does coin-flip-first; if not, port the same fix.

22. **THE strengthened ceiling lesson — well-tuned heuristics absorb most neural lift.** Iteration 4 found "94 % val acc Q-scorer (Bolt mode) → 0 pp WR". Iteration 6 found "62.7 % val acc Q-net (Mulligan, the highest-leverage decision in the game) → −0.1 pp WR". Two different decisions, two different model accuracies, same null result. The mid-game heuristics in `decks/ur_delver.py` and the deck-specific `_keep_*` mulligan logic are well-tuned enough that incremental Q-net overrides at any single decision point net out neutral. **For Manu**: do not expect Q-nets alone to lift WR on a deck whose strategy + mulligan logic is mature. The neural toolkit is needed for (a) brand-new strategies where heuristics aren't tuned yet, OR (b) qualitatively-different reasoning the heuristic can't do (LLM advisor — still untested live in either repo). Don't burn weeks chasing per-decision Q-net accuracy gains on already-tuned decisions.

23. **Honest test rigor — measure both P1 (on the play) and P2 (on the draw).** The earliest mulligan Q-net result showed +1.5 pp on a P1-only sample, which looked like a win until P2 was added: combined dropped to −0.2 pp. The lift was an artifact of training the model on P1 data and inadvertently optimising one role at the expense of the other. The eval harness (`neural_eval.run_config`) already runs both sides; never report P1-only WR for a policy change.

24. **Mulligan tightening alone cannot recover a deck whose *simulator* is missing real-world cards.** Iteration 8 attacked `doomsday` (4.3 % vs Burn baseline, real Legacy ~50 %) by tightening `_keep_doomsday`: the original kept *80 %* of opening 7s vs Burn (`1 ≤ lc ≤ 4 AND (combo OR cantrip)`); the tightened version kept *40 %*, matching real-world Doomsday discipline (snap-mull hands without Doomsday-in-hand or fast mana). The keep-rate change was confirmed by direct measurement (200 → 402 keeps over 500 trials), but **WR was bit-identical to baseline**. The reason: the deck is missing real-world Doomsday's vs-aggro game (Lurrus of the Dream-Den as a 1/1 attacker + recursion engine, lifegain piles like `Lotus Petal → BS → Wraith × 3` that gain ~6 life via Lurrus). Without those cards in the decklist, the deck has no path to win the race regardless of opener — so mulling doesn't help. **Translation for Manu:** before training Q-nets / building neural advisors for any deck, verify the *decklist and strategy itself* model the deck's real-world game plan. Heuristic improvements on top of an incomplete deck definition produce null results (or worse, mask the real problem). Audit checklist:
    1. Does the decklist match a current-format real list?
    2. Does the strategy deploy every nonland in the decklist? (echoes lesson "Strategy Must Model Win Conditions" in `CLAUDE.md`)
    3. Does the strategy have at least one realistic win path against each archetype tier (aggro / midrange / combo)?
    4. If any of (1)-(3) fail, fix THAT first — neural overlays on broken foundations don't help.

---

## Modern → Legacy (AI + output adoption)

| # | Feature | Modern file | Lines | Legacy status | Priority |
|---|---------|-------------|-------|---------------|----------|
| 1 | Pro-insights function | `proInsights()` in build_dashboard.py | ~60 | ❌ Dashboard has card data + events but no auto-derived findings | HIGH |
| 2 | G1/G3/sweep/comeback stats | matchup_cards fields | — | ❌ Dashboard lacks G1 WR, went_to_3, sweeps, comebacks | HIGH |
| 3 | Sideboard guide section | `sbLines()` in dashboard | — | ❌ No SB swap display in matchup detail | MED |
| 4 | Bool-flag sideboard | `sideboard_manager.py` | 158 | ❌ Different SB approach | MED |
| 5 | Full combat sim | `combat_manager.py` | 334 | ❌ Simplified combat | LOW |
| 6 | 5-ordering turn planner | `turn_planner.py` | 1113 | ❌ Single ordering | LOW |
| 7 | Combo assessment | `combo_calc.py` | 652 | ❌ No combo scoring | LOW |
| 8 | Continuous effects | `continuous_effects.py` | 379 | ❌ No layer system | LOW |

### Adoption notes
- **Legacy dashboard is already interactive (767K)** — has clickable heatmap, card-level data (finishers, casts, attackers, damage), "What Happens" events (Lock/Hate, Removal, Counters, Pivotal), game plans, deck profiles, and tier system. What it lacks is the `proInsights()` auto-derived findings and Bo3-specific stats (G1 WR, G3 rate, sweeps, comebacks).
- **Legacy already has HTML replays** — `replay_oops_vs_dimir_flash.html` has dark theme, game tabs, life tracking. Same v2 replayer format as Modern.
- **#1 proInsights():** Port the 60-line JS function and inject via post-processing in `build_matrix_html.py`. Needs matchup_cards fields (G1 wins, sweeps, comebacks) extracted during sim.
- **#3 Deck guides:** Legacy's `gen_guides.py` (397 lines) already produces 7-feature guides. Compare with Modern's `build_guide.py` (270 lines) — merge Stars of Sim section and 6 pro-level findings.

---

## Common Standards

### File naming
- Canonical data: `metagame_data.jsx` (not `metagame_14deck.jsx` or `meta_fresh.json`)
- Dashboard: `modern_meta_matrix_full.html` / `legacy_meta_matrix.html`
- Deck guides: `guide_{deck_slug}.html`
- Replays: `replay_{d1}_vs_{d2}_s{SEED}.html`

### GitHub Pages
- Modern: `https://djpieter81.github.io/MTGSimManu/`
- Legacy: `https://djpieter81.github.io/MTGSimClaude/`
- All links in templates MUST be absolute (not relative)
- HTML for Pages must be committed to repo, not just `/mnt/user-data/outputs/`

### Skills
- Stored in `skills/` folder in each repo
- Format: `{skill-name}.md` with frontmatter
- Shared skills: `/mtg-meta-matrix`, `/mtg-deck-guide`, `/mtg-bo3-replayer-v2`

### Provenance footer (all HTML outputs)
```
Simulated: {date} · {N} decks · {games}/pair · Engine: {repo}
Source: {data_file} · Shell: ManusAI · Strategy: Claude · Owner: DJPieter81
```

### Neural artefacts (Legacy; same paths if Modern adopts)
- Trace data: `traces/{deck1}_{deck2}.jsonl` (single matchup) or `traces/{deck}_meta.jsonl` (multi-matchup concat). One row per decision: `{decision_type, decision_value, state, candidates, eventual_winner, tes_won, kill_turn, game_length, matchup, seed}`. The field is named `tes_won` for back-compat — it's actually `1 if winner == 'p1'`, regardless of which deck is in P1.
- Model checkpoints: `models/{deck}_scorer.pt` (PyTorch state_dict) + `models/{deck}_scorer_norm.json` (per-feature mean/std). Both required to load.
- Ablation reports: `results/neural_eval_{p1}_vs_{p2}_{ts}.html`.
- LLM call logs: `results/neural_logs/{date}.jsonl` — **gitignored**. One row per Claude call with model id, token counts (incl. `cache_read` / `cache_write`), parsed response, `stop_reason`.

### Required `.gitignore` additions
```
results/neural_logs/
```

---

## Next Actions

1. **Modern:** Adopt `parallel.py` + `hypothesis_testing.py` (cuts matrix time 5×, adds stat rigor)
2. **Modern:** Adopt `deck_registry.py` (enables user deck additions without code edits)
3. **Legacy:** Port `proInsights()` into `build_matrix_html.py` (5 auto-derived findings per cell)
4. **Legacy:** Extract G1 WR, G3%, sweeps, comebacks during sim — feed into dashboard
5. **Legacy:** Add sideboard guide section to matchup detail panel
6. **Both:** Keep shared modules (`clock.py`, `bhi.py`, `strategic_logger.py`, `gameplan.py`) portable
7. **Both:** Merge deck guide pipelines — Legacy's 7-feature `gen_guides.py` + Modern's Stars/findings `build_guide.py`
8. **Modern:** Adopt the trace-record context-manager pattern from `state_encoder.py`. Smallest possible adoption — pure Python, no torch dep, no Anthropic dep. Foundation for everything else.
9. **Modern:** Adopt `lookahead.py`'s context-manager mutator pattern. The mutators (`hypothetical_life_delta`, etc.) are deck-agnostic; only the per-strategy `argmax_action` call sites need wiring.
10. **Both:** Hook MORE elective decisions per turn — *was* the highest-leverage open work item; Lever 6 (mulligan, the highest-leverage decision in the game) shipped in Legacy and STILL netted 0 pp combined. New highest-leverage open item: **the LLM advisor** (#11), since the in-codebase NN ceiling appears to be flat against well-tuned heuristics. Don't burn time on more Q-nets for already-tuned decisions until the LLM path has been validated.
11. **Both:** Run the live LLM-gate eval (`sk-ant-…` key in env var, never in chat). Cost ≤ \$2 per 200-game eval at Opus 4.7 prices. The LLM brings *qualitatively different reasoning* the Q-net can't (matchup-aware sideboard logic, novel mulligan reasoning ("this hand has no early plays vs Burn"), strategic gates). This is the unvalidated lever and the most likely path to a non-zero WR delta on already-mature decks.
12. **Done in Legacy (commit history will reflect):** `(state, action) → won?` Q-style discriminator (Lever 5) and counterfactual-rollout mulligan Q-net (Lever 6). Trained models at `models/q_ur_bolt_mode.pt` (94.2 % val acc) and `models/q_mulligan.pt` (62.7 % val acc). Modern can adopt the trainers + scorers + collectors verbatim. **But before porting** — read lessons #17, #19, #22 above. Q-nets at high val acc do not move WR on tuned heuristics; use the toolkit on (a) untuned strategies, or (b) for trace data + audit, not as a WR lever.
13. **Modern (HIGH):** Audit combo decks against tier-1 lists.  Legacy's
    2026-05-03 audit (PR #111, see `docs/lessons/2026-05-03_combo_deck_audit.md`)
    found seven independent bugs in three decks — single-line fixes moved
    matchup WRs by 12-27pp.  Modern decks were imported from MTGGoldfish
    at some point and may have drifted; same audit workflow + same bug
    classes very likely apply.  See lessons #26-#30 below for the bug
    taxonomy and diagnostic workflow that found them.

## Lessons learned (continued)

25. **Decklist audits hit diminishing returns after the obvious wins.** Iters 9-11 produced large WR lifts from single-edit fixes on three decks — Lurrus + Petal for doomsday (+4 pp combined), Grindstone 1→4 for painter (+10.8 pp). Iter 12 audited the next four candidates from the iter-7 low-WR list (oops, wan_shi_tong, belcher, mardu) and found:
    * **oops 36.2 % audit number was Bo3 sideboard hate.** Bo1 measurement at n=200/side is **56.3 %** combined — out of scope for "decklist audit" because the gap is post-board, not pre-board.
    * **wan_shi_tong 37.4 %.** Sanctifier en-Vec is in the deck but its protection-from-red effect isn't modelled (just a 2/2 stat-block). Approximating via ETB lifegain (+8 vs Burn / +4 vs other red aggro) lifted the worst matchups by 1-3 pp but the AVG didn't move meaningfully and the hack felt wrong. Reverted. Real fix is implementing damage-prevention in the engine — substantial work, out of scope for a single-iteration audit.
    * **belcher 35.8 %.** Strategy fires Burning Wish for Empty the Warrens unconditionally — even when an Empty is already in hand, AND without checking that we have ≥ 6 mana to actually cast it. Tightened the gate (`not has_empty_in_hand and budget ≥ 6`); WR moved -1.2 pp combined (within noise). The deeper bug is "all-in T1 or fail" — Belcher has no plan B. Reverted.
    * **mardu 34.7 %.** Uniformly low across many matchups (vs burn 10 %, vs ur_delver 11 %, vs ur_tempo 13 %, vs bug 15 %) — not a single decklist gap, deeper strategy issue. Out of scope.

    **Updated rule of thumb:** decklist audits work when there's an obvious quantitative gap (1 of a 4-of, missing companion, missing fast mana). For decks with broader weakness, the real fix is in the strategy code — typically 50-200 lines of careful logic, not a 1-line edit. **For Manu**: the audit pattern transfers, but expect 2-3 obvious wins out of every 5-10 candidates. Don't burn cycles on candidates with uniform weakness — those signal strategy gaps that need their own iteration.

26. **Affinity over-tuning recipe (2026-04-26 iter 13/14) — applies to Manu's affinity if it sits >65 % flat WR.** Legacy's affinity was at 72.5 % flat / 70.7 % weighted (rank #1, +4pp gap to #2). Three sequential fixes dropped it to 57.7 % flat / 57.4 % weighted (rank #6) — a -13.3pp recalibration. **For Manu's affinity port, check these three things in order — F1 is the heaviest hitter:**

    **F1 — Maindeck Force of Will is unrealistic** *(top driver, single biggest single-edit win in the session)*. Real Legacy 8-Cast does NOT run main FoW — the deck has no blue critical mass beyond 3 Monitor + 2 Cannoneer. With 4 Seat-of-the-Synod + 4 FoW the deck plays like a control deck, pre-emptively countering opponent T1-T2 combo turns. Swap: 4× FoW → 4× Frogmite (real 8-Cast staple, affinity 2/2 for {4}). Legacy result: 5-opp avg 67.9 % → 58.0 % (-9.9pp). Combo matchups dropped hardest: oops 60→31 % (-29pp), lands 71→54 %, doomsday 94→80 %.

    **F2 — Patchwork Automaton accumulates power_mod across turns** *(Oracle text bug, not just a balance issue)*. The card text is "+1/+1 for each artifact spell you've cast THIS TURN" — a per-turn buff that recalculates each turn. The simulator was accumulating: a T3 Automaton became 8/8 from T2's 4 artifacts plus T3's 3 more. Fix: at start of each turn, reset Automaton's `power_mod`/`toughness_mod` to 0 (matching the existing Cannoneer `cant_be_blocked` reset pattern), then SET (not +=) to `artifacts_cast_this_turn`. Legacy result: 5-opp avg 54.0 % → 50.7 % (-3.3pp). Burn dropped -16pp (a turn-2 8/8 trampler was killing Burn by T3); ur_tempo dropped -12pp; eldrazi -11.5pp; cloudpost -11pp. **This is a clean rules-correctness fix — port it directly if Manu's affinity has the same code shape.**

    **F3 — Emry recursion ignores the "Emry dies to removal" reality** *(strategy fix)*. Real Emry is a 1/2 that gets bolted on sight; the simulator never modeled removal targeting her. This let her recur 4/4 Cannoneers and 7-cmc Monitors at affinity-reduced cost every turn — a recurring 2-mana 4/4 trampler is unrealistic in any tempo or aggro matchup. Restrict Emry to recurring true 0-cost artifacts only (Petal, Bauble, Urza's Bauble, Mox Opal). These are the only targets that survive the "Emry dies" reality test — they enter and sacrifice/cantrip immediately, so the value is captured before she can be killed. Legacy result: 5-opp avg 58.0 % → 54.0 % (-4.0pp). Dimir dropped -9.5pp (biggest move; Emry-recurring-Cannoneer was the dimir kill).

    **F4 — Cap Cannoneer counters at +2/+2 per turn (cap variant)** *(reverted — DON'T port the cap-at-2 form)*. Capping the per-artifact-ETB +1/+1 counters at min(triggers, 2) hurt the matchups where Cannoneer was the legitimate finisher (bug, dimir, oops moved up); net -0.8pp. The cap-at-2 form is wrong because the *real* card has a {2} payment cost per trigger that the simulator was skipping — see F4-alt below.

    **F4-alt — Cannoneer pay-{2}-per-trigger (rules-correct)** *(reverted at -0.2pp WR; ship as code-correctness regardless if Manu cares about rules fidelity)*. Real Cannoneer Oracle: "Whenever an artifact you control enters the battlefield, you may pay {2}. When you do, put a +1/+1 counter on Kappa Cannoneer and it can't be blocked this turn." The simulator was applying every trigger for free. Implementation: cap by `min(cannoneer_triggers, mana // 2)`, deduct `affordable * 2` from mana. Legacy result: -0.2pp WR (within noise) — affinity rarely has spare mana when Cannoneer triggers, so the {2} gate doesn't fire often enough to swing combined WR. **Ship as a code-correctness commit even though it's WR-neutral.**

    **F5 — Tighten `_keep_affinity` mulligan** *(reverted; counterintuitive failure mode)*. Tightening the keep predicate from `fast_mana ≥ 1 AND (threats OR engine)` to `(2+ lands OR 1 land + 2 fast mana) AND (threats OR engine)` *raised* WR by +3pp. Hypothesis: London-mull-to-6 with bottoming sharpens the kept hand more than the original lenient predicate did. **Translation for Manu: don't expect mulligan tightening alone to lower a deck's WR under London mull.** Mulligan tightening is the right tool when the deck is keeping objectively bad hands — for affinity at 16 fast-mana sources, the keep predicate isn't the bottleneck.

    **Manabase deferred** — both Legacy's affinity and presumably Manu's ran 15 lands vs real-list ~22. Combined with 16 fast-mana sources (4 Petal + 4 Opal + 8 baubles), the deck never floods or stalls. Skipped this pass due to interaction risk with `_affinity_cost`. If Manu's affinity is still over-tuned after F1+F2+F3, this is the next lever — but careful because adding lands changes affinity-cost arithmetic.

27. **Calibration-health metric — use Spearman ρ between sim WR rank and real-world meta-share rank as the headline grade for the simulator.** Discovered while looking for an external-validation pass on 2026-04-26. Result on Legacy after iter-2 affinity recalibration:

    | Filter | Spearman ρ | n | Reading |
    |---|---|---|---|
    | T1 only (real share ≥ 5 %) | **-0.452** | 8 | sim's top decks are *literally the inverse* of real-world top decks |
    | T1+T2 (≥ 3 %) | -0.178 | 14 | weak inverse |
    | All meta-listed (≥ 1 %) | +0.030 | 36 | basically uncorrelated |

    **What this number means**: a simulator with ρ = +1.0 perfectly predicts which decks win tournaments. ρ = 0 is uncorrelated. ρ = -1.0 says picking the highest-sim-WR deck *guarantees* the worst real-world result. Legacy is at -0.45 on T1, meaning the matrix at this stage cannot be trusted to suggest a tournament deck — its top picks (Burn 0.724, UR Tempo 0.654, Dimir D 0.632, Infect, Dimir C) are all real-world fringe (1-2 % share). The T1 decks the meta is actually built around (Doomsday 0.337, Lands 0.416, Prison 0.439) sit in the bottom cluster.

    **Why the inversion**: AI bias toward simple linear strategies (Burn = "cast everything face") + combo-deck punishment (Doomsday/Prison/Lands need adaptive piloting around interaction + multi-turn pile/lock construction) + tempo over-execution (Delver/Murktide benefit from perfect bolt timing real humans miss).

    **Bar to "tournament-grade" simulator**: T1 ρ ≥ +0.5. Currently -0.45. The gap closes by (a) fixing the 3 underperforming T1 decks (each 4-6h dedicated work; doomsday needs the missing-cards work documented in lesson #24, lands and prison are unaudited at the time of writing), (b) verifying Burn/UR-Tempo aren't being over-piloted by the heuristic AI (LLM-gate eval — single matchup at $2 with prompt caching once a `sk-ant-…` key is set in env). **For Manu**: run the same Spearman computation on Manu's matrix vs Modern's meta-share table. If you also see ρ < 0 on T1, the same prioritisation applies (top combo/control decks need strategy work; tempo/aggro need over-piloting checks).

    **The one-liner for Manu's CLI** (drop-in, modulo `meta_ev` JSON path + `MATCHUP_META` import):
    ```python
    pairs = [(d, ev[d], MATCHUP_META[d]['share']) for d in ev
             if MATCHUP_META.get(d, {}).get('share', 0) >= 0.05]
    wr_rank = {d: i for i, (d,_,_) in enumerate(sorted(pairs, key=lambda x:-x[1]))}
    sh_rank = {d: i for i, (d,_,_) in enumerate(sorted(pairs, key=lambda x:-x[2]))}
    n = len(pairs)
    rho = 1 - 6*sum((wr_rank[d]-sh_rank[d])**2 for d in wr_rank)/(n*(n*n-1))
    ```

28. **Systematic `opp_can_cast` bypass pattern affects multiple decks** *(found 2026-04-26 iter 4-5)*. There's a class of bug where deck strategies directly do `player.remove_from_hand(c)` + `player.put_artifact_in_play(c)` (or equivalent) without routing through `cast_spell()`. This bypasses `opp_can_cast()` — the **only place** in the engine where Chalice (`gs.chalice_x`), Trinisphere (`gs.trinisphere_active`), and Thalia tax (`gs.thalia_on_board`) are enforced. **For Manu**: scan all your deck strategies for the same pattern and apply the same fix.

    **Confirmed bug sites in Legacy** (2 fixes shipped, 9+ decks unaudited):
    * **`decks/infect.py` (FIXED commit f71b09c)** — 7 sites: Mutagenic Growth, Invigorate, Berserk, Vines of Vastwood ×2, Blossoming Defense ×2. All CMC 1, all silently bypassed Chalice on 1. Impact: prison vs infect 23.5 % → 35.1 % (+11.6pp at n=300). Aggregate matrix: infect weighted EV 0.619 → 0.560 (-5.8pp). The over-tuning was sustained by this bypass.
    * **`decks/affinity.py` (FIXED commit ee7877d)** — 5 sites: Lotus Petal, Mishra's Bauble, Urza's Bauble, Mox Opal (all CMC 0 → Chalice X=0), Lavaspur Boots, Shadowspear (both CMC 1 → Chalice X=1). Trinisphere also now enforced. 5-opp avg 0.507 → 0.476 (-3.1pp). Chalice-deck matchups (vs prison/painter/eldrazi) all calibrate near 50 %.
    * **`decks/tes.py` (AUDITED 2026-04-26 iter 6 — REVERTED)**: 33 raw sites; 14 confirmed TRUE BYPASS (Probe, cantrips, Dark Ritual, Veil, Burning Wish, Infernal Tutor ×2, Tendrils, Empty, FoW, Ad Nauseam). **Two-step lesson learned**:
        1. *First attempt used `opp_can_cast()` — broke even Burn matchup -45pp.* Root cause: `opp_can_cast()` calls `can_afford()` which checks UNTAPPED lands, but TES tracks mana via a local int counter (Petals/Rituals/LED produce floating mana, not untapped lands). By Step 6 (Wish/Tendrils) all lands are tapped, so `can_afford()` falsely blocked the cast. **For Manu**: any storm-style strategy that uses a local `mana` counter cannot use `opp_can_cast()` directly — `can_afford` will false-block.
        2. *Second attempt used a tax-only helper that skips `can_afford` and only checks Chalice/Trini/Thalia*. 5-opp avg moved only +1.2pp at n=500 — minimum threshold not met. **Why**: Chalice rarely lands in time vs T1-T2 storm kill. Only `eldrazi` (-6.9pp) showed the expected drop because Eldrazi reliably deploys T1 Chalice via Eldrazi Temple's extra mana. Prison/painter/uwx Chalice arrives T2-T4, after TES has already won. Reverted per regression policy.

        **Drop-in tax-only helper for Manu's storm decks** (paste inside the strategy function):
        ```python
        def _tax_blocks_cast(card, current_mana):
            if gs.spell_blocked_by_chalice(card.cmc):
                return True
            eff = card.cmc
            if gs.trinisphere_active:
                eff = max(eff, 3)
            if gs.thalia_on_board and not card.is_creature():
                eff += 1
            return current_mana < eff
        ```
        Then gate each spell with `if not _tax_blocks_cast(spell, mana):`. **Don't expect WR movement** — the fix is for correctness only, especially in matchups where opponents reliably land T1 Chalice.

    * **Unaudited (raw site counts of `find_tag` + `remove_from_hand` without `cast_spell` nearby)**:
        - `decks/belcher.py`: 7 sites
        - `decks/sneak_b.py`: 7 sites
        - `decks/affinity.py`: ~~6~~ now 1 (Sink into Stupor manual cast remains)
        - `decks/depths.py`: 5
        - `decks/sneak_a.py`: 5
        - `decks/goblins.py`: 6 *(activated abilities — Vial, Lackey-trigger; mostly NOT spells, so likely safe; verify each site)*
        - `decks/eldrazi.py`: 3
        - `decks/cloudpost.py`: 2
        - `decks/eight_cast.py`: 2

    **Detection one-liner**:
    ```bash
    for f in decks/*.py; do
      bypass=$(grep -c "player.remove_from_hand" "$f")
      gated=$(grep -c "opp_can_cast" "$f")
      [ "$bypass" -gt 0 ] && echo "$(basename $f): $bypass remove_from_hand, $gated opp_can_cast usage"
    done
    ```
    *(Heuristic — not every `remove_from_hand` is a spell-cast bypass. Activated abilities like Aether Vial / Goblin Lackey legitimately put creatures into play without casting. Inspect each site before fixing.)*

    **Fix template**:
    ```python
    # BEFORE (bypass):
    spell = player.find_tag('mutagenic')
    if spell:
        player.remove_from_hand(spell)
        # ... apply effect

    # AFTER (gated):
    spell = player.find_tag('mutagenic')
    if spell and opp_can_cast(spell, mana, gs, caster=player):
        player.remove_from_hand(spell)
        # ... apply effect
    ```
    Add `opp_can_cast` to the strategy's `from engine import ...` line.

    **Impact on calibration ρ**: affinity over-tuning (lesson 26) AND infect over-tuning (this lesson) were both partly maintained by Chalice bypass. Closing both shipped a -5.8pp infect drop in iter 4 and a -3.1pp affinity drop in iter 5 — both move the **calibration Spearman ρ** (lesson 27) closer to positive on the all-decks measure. T1 ρ specifically still requires fixing the underperforming T1 decks (doomsday, lands, prison) — those need structural strategy work beyond bypass auditing.

29. **Combo deck audit produced six independent classes of bug** *(2026-05-03, PR #111, full writeup `docs/lessons/2026-05-03_combo_deck_audit.md`)*. Tracing the lowest-WR combo matchups (doomsday vs ur_delver 12.5%, reanimator vs burn 20%, depths vs burn 35%) found seven bugs — one card-data error (DD CMC=5 instead of BBB=3), two tier-1 omissions (Lion's Eye Diamond missing from DD, Lotus Petal missing from ANT), one off-by-one in a deck-name gate (combo-land priority hook hardcoded to `'lands'`, missed `'depths'`), one strategy/preamble interaction (Reanimator's T2 ritual mana eaten by shared `_execute_turn` Thoughtseize), one heuristic over-counting (Eidolon post-strategy treated cycled cards as missed casts), and one rule violation (Oracle ETB win used `≤` not `<`). Single-line fixes lifted depths vs burn 35→62% (+27pp) and storm vs dnt 34→50% (+16pp). **For Manu**: every Modern combo deck almost certainly has at least one of these bug classes. The diagnostic workflow is mechanical: rank matchups by `|sim_wr − expected_wr|`, generate 5-10 deep traces of the worst, read every line, then break down conditional WR by turn — discontinuities in the cast-turn → win-rate curve point at the bug. The bug taxonomy (cards.py / deck-construction / strategy-preamble / off-by-one-gate / heuristic / rule) is closed under Magic; future audits should classify each finding into one of those five buckets.

    **Audit checklist for any combo deck** (Modern + Legacy):
    1. Card data: every key combo card's `cmc` and `mana_cost` matches the printed card. Add a regression test naming the card.
    2. Tier-1 conformance: deck contains the canonical 4-of staples from a current top-8 list (LED, Petal, Wraith, Brainstorm, Ponder, etc.). Add a regression test asserting the count.
    3. Strategy/preamble: when the strategy needs T1-T2 mana for a combo line, no shared `_execute_turn` step (Thoughtseize, removal, Bowmasters flash) silently consumes that mana.
    4. Single-deck gates: `grep` for `active_deck == '...'` and `deck in ('...',)` — if the gate controls a *mechanic* (combo-land priority, fast-mana priority), the right side should be a *class* of decks, not a single name.
    5. Heuristic cardinality: any "post-strategy estimate based on graveyard growth" or similar proxy is suspect. Track the bypass channel (cycling, sacrifice, discard) explicitly.
    6. Rule strictness: re-read each win-condition card's oracle text. Strict `<` vs loose `≤` is a recurring bug class (Oracle, Test of Endurance, Helix Pinnacle, Lab Maniac).

## Out of scope for the cross-project sync
- Modern uses `gs.player1` / `gs.player2`, Legacy uses `gs.p1` / `gs.p2`. The `state_encoder.py` port to Modern must rename the slot accessors. All other features (life, hand, lands, etc.) are named identically in both repos.
- Modern's `combat_manager.py` and `turn_planner.py` are not present in Legacy — the `lookahead.py` mutators may need additional helpers to handle Modern's richer combat / multi-ordering decisions.
