---
title: Audit — goblins vs dimir_d
date: 2026-05-17
observed_wr: 0.08
target_wr: 0.45
gap_pp: -37
status: open
---

# goblins vs dimir_d — 8% WR

## Replays
- seed 42: LOSS T21, life -7. Vial late; Muxus Vial-flashed but ETB never fired.
- seed 99: LOSS T24, life -1. T3 Vial FoW'd; Matron tutors Muxus but Muxus never cast; Lackey lands T15/19 after TS stripped Muxus.
- seed 7:  LOSS T16, life 0. No Vial/Lackey; Muxus stuck at 6cmc behind Wasteland; Warchief Pushed T14.

## Divergence
- T14 (seed 7): Warchief deployed bare into open Push mana — correct is to hold until Muxus castable same turn, preserving the discount that beats Wasteland.
- T15/19 (seed 99): Lackey chump-blocked by Tamiyo each turn — strategy never sequences Expert ETB to clear the blocker first.
- T18 (seed 42): Vial-6 flashes Muxus in, but reveal-6 ETB never fires — Vial path treats entry as silent ETB.

## Responsible subsystem
`decks/goblins.py:_strategy_goblins` (Vial branch L321-331; Muxus branch L286-319). The Lackey `cheat_on_combat_damage` flag at `rules.py:204` has zero consumers in `engine.py` combat — the declared cheat trigger is dead code.

## Remediation hypothesis
Goblins treats Vial and Lackey as deploy-and-hope, not a wired tribal-cheat subsystem. Two layered failures: Lackey's combat trigger has no consumer (combat should, on unblocked Lackey damage, put the largest Goblin from hand into play with ETB firing); Vial-flash duplicates put-into-play and skips ETBs. One shared tribal-cheat helper invoked from both sites fires Muxus's reveal-6 either way. Pre-combat sequencing should clear chump blockers before Lackey attacks walls.
