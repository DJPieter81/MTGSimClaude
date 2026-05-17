---
title: Audit — painter vs eldrazi
date: 2026-05-17
observed_wr: 0.305
target_wr: 0.45
gap_pp: -14.5
status: open
---

# painter vs eldrazi — 30.5% WR

## Replays
- seed 42: LOSS T9 — Eldrazi swarm kills painter at -4; Karn held in hand 8 turns.
- seed 99: LOSS T8 — 3-mull keep, T1 Painter's Servant, no Grindstone ever, dies at -5.
- seed 7:  WIN T13 — Painter + Grindstone via Karn-wished Grindstone.

## Divergence
Turn 8 (seed 42): Painter has Workshop+Tomb (2 lands), cracks Grim Monolith → 5 mana. Strategy casts **The One Ring** (CMC 4) ahead of **Karn** (CMC 4). Ring drains the budget; Karn cannot deploy. Karn would have wished Grindstone — and with Chalice@1 blocking all four hand-Grindstones for 4 turns, `Karn → wish Grindstone` is the ONLY legal combo path. Choosing Ring over Karn delays combo ≥1 turn against a 4-power clock that kills next turn. Same pattern seed 99.

## Responsible subsystem
`engine.py:_strategy_painter` (lines 5874-5917) — fixed-order budget consumption (Ring before Karn) with no Chalice-aware reordering and no Manifold/Voltaic Key activation that would let Grindstone be cast around Chalice.

## Remediation hypothesis
Painter needs a Chalice-aware priority gate: when `gs.chalice_x == 1` and Grindstone is unplayable from hand, Karn outranks The One Ring in the budget queue because Karn is the only combo path. Generalises deck-agnostically: when a combo piece is blocked by a continuous effect, prioritise the tutor/wish that bypasses it before card-draw engines. Manifold/Voltaic Key are unused in the strategy; activating Key on Grindstone is the canonical Chalice-around play.
