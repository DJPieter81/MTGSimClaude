---
title: Audit — doomsday vs burn
date: 2026-05-17
observed_wr: 0.12
target_wr: 0.45
gap_pp: -33
status: open
---

# doomsday vs burn — 12% WR

## Replays
- seed 42: loss T11 (DD in hand T10, held; died to Goblin Guide T11)
- seed 99: loss T7 (Doomsday never drawn; cantrip-light hand)
- seed 7:  WIN T5 (Doomsday → Oracle, devotion 2 > library 0)

## Divergence
- **Turn 10 (seed 42)**: At life 2 with Goblin Guide on board, AI held Doomsday despite BBB available (Petal×2 + Swamp), 2 LED, 1 Wraith, FoW, Therapy. Close-path gate rejected casting: Path A (LED+BS) lacked BS; Paths B/C lacked BS or Oracle in hand; Path D (multi-turn) needed `post_dd_life ≥ 2·opp_clock + 7 = 11`, but post_dd_life was 1. Logged: `Doomsday held: no same-turn close (LED×2, BS×0, Oracle=False, Wraith×1, mana_after_dd=3)`. Correct play: cast — holding loses 100% (Guide hits for 2 → 0). Post-DD pile always contains Oracle+Wraith+BS, so `P(win | cast) > 0 = P(win | hold)`. The gate treats EV(hold) as positive when it is 0.

## Responsible subsystem
`engine.py:_strategy_doomsday` (lines 5019–5092) — `has_close_path` requires an in-hand kill. All four paths assume luxury of waiting; against Burn's 2-life-from-dead clock that fails.

## Remediation hypothesis
The gate needs a survival comparator, not a binary close test. Compute `opp_lethal_in = ceil(player.life / actual_opp_clock)`; when `opp_lethal_in ≤ 1`, no self-kill, and ≥1 playable land, add a `forced_send` disjunct to `has_close_path`. Justification: death is certain next turn, post-DD pile guarantees Oracle + 3 Wraiths, so interim draw + cycle has non-zero kill chance. Rule-phrased, combo-generic; test: `test_combo_strategy_casts_finisher_when_alternative_is_certain_death`.
