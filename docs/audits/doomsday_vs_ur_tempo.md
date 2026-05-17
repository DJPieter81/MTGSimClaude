---
title: Audit — doomsday vs ur_tempo
date: 2026-05-17
observed_wr: 0.125
target_wr: 0.45
gap_pp: -32.5
status: open
---

# doomsday vs ur_tempo — 12.5% WR

## Replays
- seed 42: LOSS T9 — DRC clock; never drew DD; cast BS T2, Lurrus T6, sat thereafter.
- seed 99: LOSS T17 — DD drawn T17 with mana=5 + LED + Oracle in hand; gate held it; died next turn to 8-power board.
- seed 7: WIN T3 — natural Ponder → fast DD → Oracle.

## Divergence
- T17 (seed 99): held DD despite next-turn lethal. Gate at `engine.py:5081` requires `has_close_path`; none triggered (BS=0, Wraith=0). Correct: fire DD — `hold` EV is 0, `cast` may chain off next draw. Gate treats absence of guaranteed close as hard block even when holding is strictly worse.
- T2–16 (seed 99), T2–9 (seed 42): Cabal Therapy never cast. Deck runs 4-of to strip opp FoW/Daze pre-DD (`cards.py:619`), but `_strategy_doomsday` has no Therapy clause; Therapy logic at `engine.py:2970` lives in `_strategy_bug`. ur_tempo runs 4 FoW + 4 Daze; one strip swings conversion.

## Responsible subsystem
`engine.py:_strategy_doomsday` (4599–5180) — close-path gate is binary and one-shot; strategy never deploys Cabal Therapy.

## Remediation hypothesis
Gate should compare EV of `cast_now` vs `hold` rather than gate on existence of a deterministic close. When opp next-turn damage ≥ player life and no protection held, `hold` EV is 0, so any nonzero pile EV dominates. Separately, add pre-DD Therapy phase targeting most-likely free counter via `belief.p_free_counter` (already computed line 4617). Both fixes mechanic-level; no card-name checks.
