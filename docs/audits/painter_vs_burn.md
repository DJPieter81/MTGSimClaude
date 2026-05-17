---
title: Audit — painter vs burn
date: 2026-05-17
observed_wr: 0.315
target_wr: 0.45
gap_pp: -13.5
status: open
---

# painter vs burn — 31.5% WR

## Replays
- seed 42: loses T8, life -1. Grindstone T4 without Painter; Ring T6 at 11 cannot stabilise.
- seed 99: loses T5, life 0. 4-card hand (Painter + 3 lands) after triple mull — no second combo half, no fast mana.
- seed 7:  loses T8, life 0. T1 Planar Nexus tapped, no T2-T4 spell; Ring T7 at 11, too late.

## Divergence
- Turn 0 (seed 99): mull-keep accepted a hand with one combo half, no defence, no fast mana, no combo before T6. `_keep_painter` ignores `matchup` — a burn-losing hand passes like any other.
- Turn 1-3 (all seeds): `_strategy_painter` deploys nothing burn-relevant. Kozilek's Command (4-of kill instant) and Portable Hole sit unplayed because no strategy branch casts them. Painter ramps toward T4+ Karn/Ring while a 3-turn clock kills it.

## Responsible subsystem
`engine.py:_strategy_painter` (and `decks/painter.py:_keep_painter`) — no fast-clock branch: never casts Kozilek's Command or Portable Hole, never prioritises Ring over Karn vs aggro, keep heuristic discards `matchup`.

## Remediation hypothesis
Deck-plugin fix only. (1) `_keep_painter` should consult `matchup`: vs burn/aggro require a T1-T3 interaction piece (Kozilek's Command, Portable Hole, Ring castable T4) or complete combo+mana path; else mull. (2) Add an aggro branch to `_strategy_painter`: when opponent clock exceeds turns-to-combo, cast Kozilek's Command on largest attacker, Portable Hole on a 1-drop, prefer Ring over Karn (Ring protects same turn; Karn waits). No engine-core change.
