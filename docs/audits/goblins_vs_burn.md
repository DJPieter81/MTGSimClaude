---
title: Audit — goblins vs burn
date: 2026-05-17
observed_wr: 0.125
target_wr: 0.45
gap_pp: -32.5
status: partial
follow_up: 2026-05-17 — pitch-target picker fixed (`select_pitch_target` in `engine.py`).
  Goblins Mox no longer exiles matron/ringleader/sling/muxus/warchief/pashalik.
  Sweep n=200 unchanged (13.5% vs 12.5% baseline; pitch-fuel is not the bottleneck
  in this matchup — race-mode chump-trade gating + Vial priority remain open).
---

# goblins vs burn — 12.5% WR

## Replays
- seed 42: WIN T9 — Vial T2 + Fury kill Guide; Vial-ramp lands Muxus.
- seed 99: LOSS T8 (life -1) — Vial deployed T3 (late), Matron T5, Muxus stuck in hand.
- seed 7: LOSS T10 — Lackey T5 never connects; Warchief chump-trades into Guide T7.

## Divergence
- T1 (seed 99): hand = Mire+Mox+Matron+Cratermaker. Strategy pays 1 mana for Cratermaker and exiles Matron to Chrome Mox. Correct: hold Mox until a non-tutor pitch target arrives. Net cost: −1 Matron tutor (≈ a Muxus).
- T3 (seed 99): Vial enters on T3 instead of T1/T2 because Mox/Matron sequencing ran first. First flash-in is T6 at vc=2 — Sling-Gang and Muxus never deploy in time.
- T7 (seed 7): Warchief attacks into open Guide; chump-trade with no haste-grant value. Correct: hold Warchief as blocker for T8.

## Responsible subsystem
`decks/goblins.py:_strategy_goblins` — ordering: Vial gated on `gs.turn <= 3` but not prioritized above Chrome Mox exile; Mox pitch-target picker (lines 232–242) accepts Matron/Ringleader as fuel; no race-aware tutor-preservation guard.

## Remediation hypothesis
Add a race-mode branch driven by opponent burn-class detection: (a) Vial cast precedes Mox pitch decisions, (b) Mox pitch-target excludes tutors (`matron`, `ringleader`) and finishers (`muxus`, `sling`), (c) chump-trade gating requires `player.life <= burn_hand_clock` before sacrificing a 2-power threat. These rules generalize to mardu vs burn — the helper belongs in `interaction_model.py`, not goblins-specific code.
