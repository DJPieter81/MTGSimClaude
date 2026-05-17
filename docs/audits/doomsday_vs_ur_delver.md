---
title: Audit — doomsday vs ur_delver
date: 2026-05-17
observed_wr: 0.145
target_wr: 0.45
gap_pp: -30.5
status: open
---

# doomsday vs ur_delver — 14.5% WR

## Replays
- seed 42: loss T11 — on the draw, never finds DD; Brainstorm T2, Cabal Therapy never fires, Lurrus chumps a Bolt.
- seed 99: loss T12 — opens 2 Oracle + Dark Ritual + 2 fetch + Island + FoW, no cantrip, never digs to DD.
- seed 7: loss T10 — T5 casts DD into 1 open mana with Daze visible; DD countered. Cavern of Souls sat unplayed T1-T6.

## Divergence
- Turn 5 (seed 7): casts Doomsday with `bhi_p_free_counter` known-high and Cavern of Souls in hand. Correct: play Cavern T1-T3 naming Oracle's type, or hold DD until counter mana taps. Cast gate (engine.py:5084-5092) checks only `self_kill` and `has_close_path` — no counter-risk threshold, no Cavern awareness. ~half of DD casts vs UR Delver die to Daze/FoW with pile stranded at half life.

## Responsible subsystem
`engine.py:_strategy_doomsday` — emits `bhi_p_free_counter` at line 4630 but never consumes it; also blind to Cavern of Souls when sequencing lands and DD.

## Remediation hypothesis
Add a counter-risk gate parallel to engine.py:6085: when `belief.p_free_counter > IP.BHI_FREE_COUNTER_THRESHOLD` and no protection (Veil, Cavern on Oracle's type, opp tapped out), defer DD one turn — the multi-turn-close branch tolerates the delay. Independently, sequence Cavern as first land whenever DD/Oracle is in hand and tag its mana uncounterable in `budget` so DD bypasses `try_reactive_counter`. No engine-core changes or card-name references outside `decks/`.
