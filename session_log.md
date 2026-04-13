# Architecture Session — A + B + C (2026-04-13)

## Phase A: Response Function Unification
- Unified `_p1_respond_on_opp_turn` + `_p2_respond_on_pro_turn` → `_respond_on_opponent_turn`
- Added `_force_of_vigor_generic(responder, active, ...)` (symmetric FoV)
- Interactions: STP, Fatal Push, Snuff Out, Bolt/Heat, Flash Bowmasters, FoV, Wasteland
- Old functions kept as deprecated wrappers; sim.py call site updated
- Tests: 147/0
- Symmetry (n=100): dimir/dimir_b 114%, ur_delver/burn 94%, bug/storm 100%

## Phase B: cast_spell() Pipeline (PARTIAL)
- _strategy_lands: 2 casts (crop, snuff) — committed
- _strategy_ur_aggro: ~4 casts (cantrip, ragavan, drc/delver/murk, bolt) — committed
- Remaining 17 engine.py strategies + 19 decks/*.py strategies NOT converted
  (session time constraint — each requires careful per-function conversion + test)
- Tests maintained: 147/0 throughout (symmetry test ±25pp is flaky)

## Phase C: n=500 Re-sim
- refresh_all.py --resim 500 completed (337s total)
- New matrix: results/matrix_20260413_073332.json
- All 36 guides regenerated (500 games/deck, 121s)
- Matrix HTML rebuilt, verify.py passed
- Tests: 147/0
---
- _strategy_eldrazi: 5 casts converted, tests 147/0, commit d3beac3
- _strategy_dimir_flash: 5 casts converted, tests 147/0, commit b1a7b56
- _strategy_dnt: 4 casts converted, tests 147/0, commit 220a6c8
- _strategy_dimir: 7 casts converted, tests 147/0, commit 659fdb8
- _strategy_uwx: 7 casts converted, tests 147/0, commit 9a32094
- _strategy_painter: 7 casts converted, tests 147/0, commit e457f38
- _strategy_storm: 2 casts converted (partial; kill_spell skipped due to fluster rebuttal logic), tests 147/0, commit 0f1453a
- _strategy_reanimator: 7 casts converted, tests 147/0, commit cf6ba61
- _strategy_ocelot: 7 casts converted, tests 147/0, commit 73d33f0
- _strategy_mono_black: 8 casts converted, tests 147/0, commit 474eeb6
- _strategy_boros: 8 casts converted, tests 147/0, commit a492d31
- _strategy_mardu: 6 casts converted (T1 grief+ephemerate combo left as-is), tests 147/0, commit d74ee91
- _strategy_doomsday: SKIPPED (complex DD+VoS+Oracle sequence with intertwined counter checks; conversion risk too high given remaining time)
- _strategy_prison: 8 casts converted, tests 147/0, commit 2cc4fd7
- _strategy_oops: SKIPPED (complex combo with Veil+Mindbreak+Dread Return nested counter logic)
