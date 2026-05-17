---
title: Audit — goblins vs ur_tempo
date: 2026-05-17
observed_wr: 0.075
target_wr: 0.45
gap_pp: -37.5
status: open
---

# goblins vs ur_tempo — 7.5% WR

## Replays
- seed 42: LOSS T9 — kept 1-land 6-spell hand; stuck on 1 land through T5, Vial Dazed T2, second land T6. DRC clock kills.
- seed 99: LOSS T18 — Vial T3, Matron tutors Muxus T5, never hard-cast despite 5 lands by T17. Strategy gates Muxus behind Vial=6 (reached T15). FoW counters Lackey T15.
- seed 7:  LOSS T12 — Muxus + Ringleader opener but 4 lands by T7; neither hard-cast. Lackey T5 traded into 2x DRC. 4 Caverns drawn 0.

## Divergence
- Turn 5 (seed 99): Matron tutors Muxus. Strategy idles (lines 286-319 require `rem >= muxus_cost=6`) with no mana development plan. Correct: hard-cast once mana available OR Vial-cheat at vc=6 — whichever first. Lost ~10 turns of payoff.
- Turn 5 (seed 7): Lackey deployed into open board with no Cavern. Correct: hold Lackey until Cavern (uncounterable + payoff in hand).
- Turn 1 keep (seed 42): `_keep_goblins` accepts 1-land/2-threat hands lacking Lackey/Vial — should mull vs Daze decks.

## Responsible subsystem
`decks/goblins.py:_strategy_goblins` + `decks/goblins.py:_keep_goblins` — strategy lacks Muxus hard-cast trigger independent of Vial state, Lackey protection heuristic, and Ringleader-first refill ordering; mulligan rule too permissive for no-enabler hands.

## Remediation hypothesis
Tighten `_keep_goblins`: require `(lands>=2 AND creature)` or `(lands>=1 AND lackey/vial AND payoff)`. Decouple Muxus hard-cast from Vial — once `rem >= muxus_cost`, cast directly. Add Ringleader-before-Warchief ordering when no Muxus in hand. Deck-private; no engine edits.
