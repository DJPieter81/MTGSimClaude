---
title: Audit — painter vs ur_tempo
date: 2026-05-17
observed_wr: 0.28
target_wr: 0.45
gap_pp: -17
status: partial
follow_up: 2026-05-17 — COMBO_META wired into `decks/painter.py` and
  `_strategy_painter` now consults `combo_plan`; combo-piece deployment
  is gated on Defer. Sweep n=200: 28.0% → 27.0% (no improvement — ur_tempo's
  Daze/Bolt mix produces lower opp `p_free_counter` than dimir/sneak_b,
  so Defer fires less often; the gap here is driven by the decklist's
  lack of any Murktide answer rather than naked-piece casting. Companion
  audit (`painter_vs_sneak_b`) moved +7.5pp on the same fix.
---

# painter vs ur_tempo — 28% WR

## Replays
- seed 42: loss T9 — Grindstone FoW'd T4, One Ring Dazed T6, DRC kills at -5
- seed 99: loss T8 — Tezzeret Dazed T3, combo never assembled, life 0
- seed 7:  loss T10 — Painter cast naked T5, Wasteland eats lands, -4

## Divergence
- T4 seed 42: Grindstone into representable FoW (DRC active, 3 cards, U up). Correct: Defer for Karn ({4}) to wish a piece and combo same-turn, denying the counter window.
- T3 seed 99: Tezzeret naked into Daze (UR up, peak Daze turn). Same defect — no BHI-gated Hold/Defer.
- T5 seed 7: Painter solo with no Grindstone, no Karn. Pieces deploy as soon as castable rather than assembling + protecting.

## Responsible subsystem
`decks/painter.py:DECK_META` — missing `combo` metadata (`pieces`, `protection_tags`, `assembly_paths`), so `combo_engine.combo_plan()` returns `NoPlan('no combo metadata for deck')` and the BHI free-counter check in `_check_protection` is never consulted. `engine.py:_strategy_painter` therefore deploys pieces unconditionally on the first affordable turn.

## Remediation hypothesis
Add a `combo` block to `decks/painter.py:DECK_META` declaring `pieces={'painter','grind'}`, `protection_tags=frozenset()`, and a two-path assembly (painter+grind at 4; karn+piece at 5). Gate piece deployment in `_strategy_painter` on `not isinstance(plan, Defer)` — mirroring `storm.py` and `show.py`. Decklist likely also needs 4× Veil of Summer or 2× Defense Grid so Hold is viable; the 0-counter list forces every protect-decision to Defer, costing tempo against a 3-power flier clock.
