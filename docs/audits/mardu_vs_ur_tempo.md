---
title: Audit — mardu vs ur_tempo
date: 2026-05-17
observed_wr: 0.09
target_wr: 0.45
gap_pp: -36
status: open
---

# mardu vs ur_tempo — 9% WR

## Replays
- seed 42: loss T9 — Grief never resolves; Fury T4 FoW'd; DRCs kill at 0
- seed 99: loss T12 — no Grief; Fury T5 FoW'd, T7/T9 hit empty board; Murktide untouched
- seed 7:  loss T12 — Grief drawn T5 sans ephemerate; Bowmasters chump-trade; Murktide closes

## Divergence
- T1 seed 42: opener Grief/Eph/FoW/3xBowm/Mtn/TS. Pitch picker scans `'B' in colors and c is not grief and c is not ephemerate` — first match is Bowmasters, a 4-of threat. Real Mardu pitches dead cards (lands, redundant TS), never its own clock.
- T4 seed 42 / T5 seed 99: Fury cast naked into representable FoW (DRC + 2 cards + UU up). No BHI gating, no bait spell first. Losing the sole sweep is the matchup.
- All seeds: zero answer to Murktide (toughness 5-8). Bolt/STP/Fury whiff at full size.

## Responsible subsystem
`engine.py:_strategy_mardu` (lines 6692-6776) — Grief pitch picks first black card, not lowest-value; Fury/Grief lack the `combo_engine.combo_plan()` BHI counter-gate used by storm/painter/show. Compounded by `cards.py:make_mardu_deck` lacking Lurrus, Solitude, or any Murktide answer despite `decks/mardu.py` claiming a Lurrus engine.

## Remediation hypothesis
Two layered fixes, no patches. (1) Drive Grief-pitch from a `pitch_priority` ordering on the deck plugin (own threats = do_not_pitch; lands/dead-matchup = pitch_first) so the engine reads per-card metadata, not first-match. (2) Route Fury and Grief through `combo_engine.combo_plan()` with `protection_tags=frozenset()` so `Defer` fires when `bhi.p_free_counter(opp) > BHI_FREE_COUNTER_THRESHOLD`; bait Bolt or STP first to drain UU. Decklist gap (no Murktide answer, no Lurrus) is a separate `cards.py` audit.
