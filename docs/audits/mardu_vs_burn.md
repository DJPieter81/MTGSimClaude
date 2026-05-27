---
title: Audit — mardu vs burn
date: 2026-05-17
observed_wr: 0.09
target_wr: 0.45
gap_pp: -36
status: open
---

# mardu vs burn — 9% WR

## Replays
- seed 42: loses T6 at -1. Mono-Mountain keep + 3 Bowmasters, no black/red T1. Bowmasters first deploys T6 at 10 — lethal range.
- seed 99: wins T21 at 1. Burn fizzles post-Fireblast T8; mardu grinds via Bowmasters + double Grief.
- seed 7: loses T5 at -2. T3 Ragavan trades into Swiftspear. Held FoW, never fired on Lava Spike / Fireblast.

## Divergence
- T3 seed 7: Ragavan attacks known Swiftspear blocker, trades. Correct: hold Ragavan, flash Bowmasters for ping + chump. `combat_declare` lacks an unfavorable-trade veto when the attacker is the clock.
- All seeds: FoW never fires on burn spells. Counter pipeline treats Lava Spike / Fireblast as low threat — face-damage scoring ignores `player.life` proximity to lethal.
- Decklist: zero lifegain main, only 2 STP, 8 self-damaging fetches. Against a 3-turn clock the race math is unwinnable.

## Responsible subsystem
`decks/mardu.py` (decklist + `_keep_mardu`) and the burn-branch of `engine.py:_strategy_mardu` — no main lifegain, no race-mode threat scoring for face burn, FoW priority blind to burn-spell tag vs life total.

## Remediation hypothesis
Deck-plugin fix. (1) Decklist: add 2-3 Auriok Champion (or Lurrus companion) and a 3rd STP; cut a fetch and a Bowmasters. (2) `_keep_mardu` vs burn: require T1 black-for-Grief or a lifegain piece; else mull. (3) Burn-branch: when `vs_burn` and `player.life <= 10`, max-priority FoW on burn-tagged spells.
