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

## Lessons learned (continued)

25. **Decklist audits hit diminishing returns after the obvious wins.** Iters 9-11 produced large WR lifts from single-edit fixes on three decks — Lurrus + Petal for doomsday (+4 pp combined), Grindstone 1→4 for painter (+10.8 pp). Iter 12 audited the next four candidates from the iter-7 low-WR list (oops, wan_shi_tong, belcher, mardu) and found:
    * **oops 36.2 % audit number was Bo3 sideboard hate.** Bo1 measurement at n=200/side is **56.3 %** combined — out of scope for "decklist audit" because the gap is post-board, not pre-board.
    * **wan_shi_tong 37.4 %.** Sanctifier en-Vec is in the deck but its protection-from-red effect isn't modelled (just a 2/2 stat-block). Approximating via ETB lifegain (+8 vs Burn / +4 vs other red aggro) lifted the worst matchups by 1-3 pp but the AVG didn't move meaningfully and the hack felt wrong. Reverted. Real fix is implementing damage-prevention in the engine — substantial work, out of scope for a single-iteration audit.
    * **belcher 35.8 %.** Strategy fires Burning Wish for Empty the Warrens unconditionally — even when an Empty is already in hand, AND without checking that we have ≥ 6 mana to actually cast it. Tightened the gate (`not has_empty_in_hand and budget ≥ 6`); WR moved -1.2 pp combined (within noise). The deeper bug is "all-in T1 or fail" — Belcher has no plan B. Reverted.
    * **mardu 34.7 %.** Uniformly low across many matchups (vs burn 10 %, vs ur_delver 11 %, vs ur_tempo 13 %, vs bug 15 %) — not a single decklist gap, deeper strategy issue. Out of scope.

    **Updated rule of thumb:** decklist audits work when there's an obvious quantitative gap (1 of a 4-of, missing companion, missing fast mana). For decks with broader weakness, the real fix is in the strategy code — typically 50-200 lines of careful logic, not a 1-line edit. **For Manu**: the audit pattern transfers, but expect 2-3 obvious wins out of every 5-10 candidates. Don't burn cycles on candidates with uniform weakness — those signal strategy gaps that need their own iteration.

## Out of scope for the cross-project sync
- Modern uses `gs.player1` / `gs.player2`, Legacy uses `gs.p1` / `gs.p2`. The `state_encoder.py` port to Modern must rename the slot accessors. All other features (life, hand, lands, etc.) are named identically in both repos.
- Modern's `combat_manager.py` and `turn_planner.py` are not present in Legacy — the `lookahead.py` mutators may need additional helpers to handle Modern's richer combat / multi-ordering decisions.
