---
title: Audit — belcher vs uwx
date: 2026-05-17
observed_wr: 0.275
target_wr: 0.45
gap_pp: -17.5
status: open
---

# belcher vs uwx — 27.5% WR

## Replays
- seed 42: LOSS (T11) — ramped to mana=7 storm=4 on T2, no payoff in hand (Wish was imprinted), passed; Mentor + tokens killed Belcher.
- seed 99: WIN (T7) — Wish countered by FoN, fell back to Empty (14 goblins).
- seed 7:  WIN (T1) — Wish countered by FoW (no Veil), Empty backup (14 goblins).

## Divergence
- Turn 2 (seed 42): Chrome Mox imprinted **Burning Wish** — the deck's sole sideboard tutor and primary chain to Empty. The exclusion list in `decks/belcher.py:237` only blocks `{chrome_mox, belcher, led}`, treating Wish/Empty/Veil as fodder.
- Same turn: with mana=7 storm=4 and no Belcher/Wish/Empty in hand, the strategy passed with budget unused. The deck has no plan to *hold* ramp when payoff lives only in the topdeck, and no Veil-protected pivot when the imprint ate the payoff.

## Responsible subsystem
`decks/belcher.py:_strategy_belcher` (Step 3, Chrome Mox imprint selector) — greedy on the first colored nonland; win conditions count as equivalent fodder.

## Remediation hypothesis
Make the imprint chooser payoff-aware: exclude `{burning_wish, empty, vos}` in addition to the current set, and prefer surplus rituals/Spirit Guides/Probe whose value collapses once mana is fixed. Additionally, gate Mox imprint on payoff redundancy — only fire when hand still contains ≥1 castable payoff (Charbelcher OR Empty OR Burning Wish) after the pitch. Single-module change inside `decks/belcher.py`; no engine edits and no card-name strings introduced into core.
