---
title: Audit — belcher vs ur_delver
date: 2026-05-17
observed_wr: 0.29
target_wr: 0.45
gap_pp: -16
status: open
---

# belcher vs ur_delver — 29% WR

## Replays
- seed 42: LOSS T15 (life -7). On draw, T2 hit mana=7 storm=4, no kill piece; drew Charbelcher only T8.
- seed 99: WIN T7 (Charbelcher → 10 dmg). Canonical line fires.
- seed 7:  LOSS T10. T1 hit storm=6 mana=4, Burning Wish fetched Empty the Warrens, never cast.

## Divergence
- T1 (seed 7): Wish resolved at storm=6, fetched Empty the Warrens, turn ended. Storm resets next turn (CR 700.2), so Empty resolves at storm=1 → 4 tokens, under the `>= 6` lethal gate. Wish must fire *before* rituals burn storm, or defer to a turn that can still cast Empty.
- T2 (seed 42): Wish in hand, mana=7, no Belcher drawn. Step 11 only fetches `Empty the Warrens`, never `Goblin Charbelcher`. With 7 mana + fetched Belcher this is T2 lethal; the strategy cannot see it.

## Responsible subsystem
`decks/belcher.py:_strategy_belcher` (Steps 11–12) — Burning Wish target is hardcoded to Empty the Warrens, and wish fires after rituals burn storm, so the fetched copy is uncastable for a lethal token count. Belcher-via-wish line is absent.

## Remediation hypothesis
Evaluate Burning Wish *before* rituals when no Belcher is in hand, and gate the tutor target on state: fetch Charbelcher when post-wish mana covers {4} + activation (LED-in-response bridges the gap); else fetch Empty only when remaining mana + storm support a ≥6-token same-turn resolution. Single-module change.
