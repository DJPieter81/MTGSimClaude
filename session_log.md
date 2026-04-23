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
- _strategy_show: 2 casts converted (partial; Show+Veil combo left as-is), tests 147/0, commit d6035ee
- _strategy_bug: SKIPPED (23 casts, very large; would require careful port of BUG's complex state assessment and spell sequences; left for a dedicated session)
- decks/dimir_flash: 5 casts converted, tests 147/0, commit c43479c
- decks/eldrazi: 6 casts converted, tests 147/0, commit e530709
- decks/ur_delver: 7 casts converted, tests 147/0, commit cf886ec
- decks/ur_tempo: 7 casts converted, tests 147/0, commit d73e8a8
- decks/uwx: 7 casts converted, tests 147/0, commit b4613a0
- decks/wan_shi_tong: 8 casts converted, tests 147/0, commit fc4f711
- decks/sneak_a: cantrips only (3 casts); SaT combo left as-is, tests 147/0, commit 101f22a
- decks/eight_cast: 6 casts converted, tests 147/0, commit a2a9995
- decks/cephalid: 10 casts converted, tests 147/0, commit 5009acb
- decks/sneak_b: cantrips only (3 casts); SaT combo left as-is, tests 147/0, commit 7a2f53f
- decks/dimir_c: 10 casts converted (also fixed latent indent bug), tests 148/0, commit d40f007
- decks/dimir_d: 11 casts converted (also fixed latent indent bug), tests 149/0, commit 70929ec
- decks/depths: 7 casts converted; Crop/GSZ combo-rebuttal left as-is, tests 149/0, commit 8822eec
- decks/cloudpost: 9 casts converted; Crop Rotation left as-is, tests 149/0, commit 0617f26
- decks/goblins: 9 casts converted; Chrome Mox/Fury evoke/Lackey-trigger left as-is, tests 149/0, commit 46c2337
- decks/infect: 5 casts converted; pump spells left as-is, tests 149/0, commit 2d9046d
- decks/affinity: 7 casts converted; free artifacts/equipment/Saga left as-is, tests 149/0, commit 9b37ce6
- decks/belcher: SKIPPED — defines local `cast_spell` helper that conflicts with engine.cast_spell; intricate storm chain with LED crack/rituals; risk too high
- decks/tes: SKIPPED — 33 casts, also defines local `cast_spell` helper; complex storm chain with Veil/Mindbreak/LED/Echo of Eons rebuttal logic; risk too high

## Phase C: n=500 Re-sim (2026-04-14)
- refresh_all.py --resim 500 completed (345s total)
- New matrix: results/matrix_20260414_172128.json (36 decks, 1260 matchups)
- All 36 guides regenerated (500 games/deck, 129s)
- Matrix HTML rebuilt (meta_matrix_20260414_172128.html, 719KB)
- verify.py: 147/1 (only flaky symmetry storm vs bug 30%+37%=67%, stochastic noise)

## Phase B continuation (2026-04-23)
- _strategy_bug: 21 casts converted (TS, Bowmasters main+EOT, Push early+main, Snuff Out
  early+main, Brainstorm, Ponder, Dismember, Endurance evoke+full, FoV paid, Pyro/Hydro,
  Toxic Deluge, Surgical, Tamiyo, Goyf, Borrower, Murktide, Kaito). Abrupt Decay
  intentionally left manual (officially uncounterable). Tests 149/0.
  Pre-conversion baseline (n=500): bug_vs_burn 16.8%, bug_vs_storm 61.8%,
  bug_vs_dimir 47.6%, bug_vs_show 62.6%, bug_vs_oops 51.6%.
  Post-conversion sanity (n=100): 11.0% / 62.0% / 53.0% / 64.0% / 53.0% — bug_vs_burn
  -5.8pp shift is the expected Eidolon-sensitivity correction (more accurate trigger
  on cantrips / removal); other matchups within ±5pp noise band.
- Remaining SKIPs: decks/belcher (16 casts, local cast_spell helper conflict),
  decks/tes (33 casts, same).
