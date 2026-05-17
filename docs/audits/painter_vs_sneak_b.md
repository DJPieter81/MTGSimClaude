---
title: Audit — painter vs sneak_b
date: 2026-05-17
observed_wr: 0.31
target_wr: 0.45
gap_pp: -14
status: partial
follow_up: 2026-05-17 — COMBO_META declared in `decks/painter.py` and
  `_strategy_painter` now consults `combo_plan` before deploying naked
  combo pieces. When opp BHI `p_free_counter > BHI_FREE_COUNTER_THRESHOLD`
  (and painter has no `protection_tags` to Hold), Defer skips Painter +
  Grindstone deployment this turn; Ring/Karn/Tezzeret still deploy.
  Sweep n=200: 31.0% → 38.5% (+7.5pp). Decklist gap (Veil of Summer /
  Defense Grid) remains open to make Hold viable.
---

# painter vs sneak_b — 31% WR

## Replays
- seed 42: painter on draw, T3 loss — opp Show+Tell → Omniscience before painter assembles; opener had no 2-drop combo piece and no disruption.
- seed 99: painter on play after 3 mulls; T1 Painter's Servant slammed into held FoW, then dies T8 to Atraxa.
- seed 7:  painter wins T11 via Karn → Grindstone; opp lacked a fast hand.

## Divergence
Turn 1 (seed 99): painter cast Painter's Servant with no protection vs a deck whose BHI free-counter probability is high (4x FoW + 4x Daze in 60). Correct line: hold the combo piece, develop lands/Ring/Karn first. The Show/Storm strategies route through `combo_engine.combo_plan` and return `Hold(card)` / `Defer()` when `belief.p_free_counter > IP.BHI_FREE_COUNTER_THRESHOLD`; painter never consults that gate. Across 50 seeds painter loses 20/33 games by turn 4, consistent with no race awareness.

## Responsible subsystem
`engine.py:_strategy_painter` together with missing `COMBO_META` in `decks/painter.py` — painter is the only declared combo deck lacking `assembly_paths`, so `combo_plan` returns `NoPlan` and the strategy deploys combo pieces ungated.

## Remediation hypothesis
Register `COMBO_META` in `decks/painter.py` (pieces: painter, grind, karn; protection_tags including ring; assembly path painter+grind+3-mana) and have `_strategy_painter` consult `combo_plan` before deploying naked Painter's Servant on T1/T2 when opp BHI shows high free-counter probability. Expected effect: stop the games lost to a T1 piece walking into FoW and defer one turn when opp likely holds Daze, recovering toward 45%.
