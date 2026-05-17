---
title: Audit — belcher vs dimir_b
date: 2026-05-17
observed_wr: 0.315
target_wr: 0.45
gap_pp: -13.5
status: open
---

# belcher vs dimir_b — 31.5% WR

## Replays
- seed 42: LOSS T9 — hit `mana=7 storm=4` on T2 but Burning Wish was Mox-imprinted; no finisher resolved.
- seed 99: LOSS T16 — Belcher activated T7, revealed only 10 cards (Taiga still in library) → 10 dmg, opp at 7, no backup.
- seed 7: LOSS T20 — T1 Empty for storm 6 with no follow-up; goblins chumped once, Barrowgoyf killed through.

## Divergence
- **seed 42, T2:** Chrome Mox exiled the only finisher (Burning Wish). Correct: pitch a spare ritual; never imprint the sole win-con.
- **seed 99, T7:** Activated Belcher without verifying lethality. Correct: hold for a second ritual to redraw past Taiga, or sequence Empty backup. Sub-lethal Belcher vs a creature deck loses.
- **seed 7, T1:** Empty-on-T1 for 6 storm, no plan-B vs removal/clock.

## Responsible subsystem
`decks/belcher.py:_strategy_belcher` plus `_keep_belcher` — strategy is context-free. No discard-disruption modeling (`matchup` arg accepted then ignored), no expected-damage check before activation, no Chrome Mox imprint blacklist for the sole finisher.

## Remediation hypothesis
Belcher fires whenever `storm + mana ≥ threshold`, ignoring whether the kill is lethal given current library composition, and whether Mox is about to exile the only finisher. The fix is one `combo_engine` view (`expected_belcher_damage(library, opp_life)` + `imprint_safe_pitch(hand)`) consumed by `_strategy_belcher` before committing rituals — same Execute/Hold/Defer pattern Storm uses. Mulligan should also pass `matchup` through `_keep_belcher` to require finisher + protection vs `dimir_*`.
