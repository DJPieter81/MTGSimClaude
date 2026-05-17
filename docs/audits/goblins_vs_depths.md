---
title: Audit — goblins vs depths
date: 2026-05-17
observed_wr: 0.085
target_wr: 0.45
gap_pp: -36.5
status: open
---

# goblins vs depths — 8.5% WR

## Replays
- seed 42: LOSS T7. Marit Lage online T5; goblins to 0 in one swing.
- seed 99: LOSS T10. Marit Lage T8; cratermaker chips for 2/turn, no path to lethal.
- seed 7:  LOSS T6. Stage T2, Depths T4 → Marit Lage T4; goblins killed T6.

## Divergence
- Turn 2-4 (all seeds): goblins never targets Thespian's Stage or Dark Depths. Cause: `decks/goblins.py:make_goblins_deck` ships 0× Wasteland. No answer exists to the two-land combo window.
- Turn 3-5: goblins offense tops out at ~2 dmg/turn from Cratermaker/Lackey pre-Muxus. Even a T3 Muxus (never assembled in seeds 42/99) can't race a T4-5 indestructible 20/20 flyer. Clock asymmetry: goblins needs ~10 unblocked swings; depths needs two land drops.
- Cratermaker's destroy-colorless-nonland is useless: Marit Lage is indestructible. The only viable disruption (Wasteland on Stage/Depths pre-activation) is absent from the 60.

## Responsible subsystem
`decks/goblins.py:make_goblins_deck` — decklist composition omits Wasteland and Rishadan Port, leaving zero land-disruption vs land-combo; `interaction.soft_to_wasteland: False` mis-signals nonexistent disruption.

## Remediation hypothesis
Real Legacy Goblins lists run 2-4 Wasteland (often +1-2 Rishadan Port) to tax/disrupt combo lands. Restoring 3-4 Wasteland (swap Mountains/one Cavern) and prioritizing `tag=='depths'`/`tag=='stage'` in the existing `engine.py:2307` Wasteland selector should close most of the gap. Wasteland targeting already exists engine-side; the deck simply doesn't field the card.
