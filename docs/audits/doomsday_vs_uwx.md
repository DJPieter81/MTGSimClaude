---
title: Audit — doomsday vs uwx
date: 2026-05-17
observed_wr: 0.12
target_wr: 0.45
gap_pp: -33
status: open
---

# doomsday vs uwx — 12% WR

## Replays
- seed 42: OPP wins T15 (life -2); DD held T12, T14.
- seed 99: OPP wins T23 timeout; DD held T12 / T18 / T20.
- seed 7:  OPP wins T12 (life 0); DD cast naked T5, FoN-countered.

## Divergence
- Turn 12 (seeds 42 & 99): AI held DD with 2 LEDs + 4 lands + Oracle-in-hand. The close-path gate only matches "LED + Brainstorm in hand." The correct line — cast DD, crack LED for BBB, BS sits inside the pile — is unmodelled. "LED + Oracle-in-hand → pile Wraith chain" is also missed. DD sat 8+ turns while Sanctifier en-Vec ticked life 20→0.
- Turn 5 (seed 7): Reverse. With Therapy + LED + DD, AI cast DD without first stripping FoW/FoN. Therapy sits in the generic interaction block (engine.py:2970) but the combo gate fires earlier, so DD hits the stack naked.

## Responsible subsystem
`engine.py:_combo_main` close-path gate (lines 5048–5082) — under-counts Path A (ignores LED→pile-BS, LED+Oracle), and the multi-turn gate (5079) over-penalises 2-power active clocks, stranding DD above 9 life.

## Remediation hypothesis
Enumeration is hand-only; should be pile-aware: LED + Oracle-in-hand enables pile [BS, Oracle, Wraith, Wraith, pad] — LED post-DD yields BBB → BS resolves Oracle + Wraith chain. Multi-turn gate uses raw `actual_opp_clock` without crediting DD's own removal or pre-DD Therapy; reframe as "expected turns to Oracle" vs "turns until life ≤ 0," and sequence Therapy/Veil ahead of the combo block when a counter is live in opponent's hand or graveyard.
