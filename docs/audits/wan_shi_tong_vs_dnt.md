---
title: Audit — wan_shi_tong vs dnt
date: 2026-05-17
observed_wr: 0.145
target_wr: 0.45
gap_pp: -30.5
status: open
---

# wan_shi_tong vs dnt — 14.5% WR

## Replays
- seed 42: LOSS — life 0 on T13. Self-cast Chalice@1 on T10; subsequent
  March / STP draws bricked.
- seed 99: LOSS — T15 board/life. Wasteland + Rishadan Port stripped
  manabase; Solitude flickered en-Vec twice; no wrath assembled.
- seed 7:  LOSS — T15 board/life. Self-cast Chalice@1 on T9; 4× March
  + STP draws bricked through T30.

## Divergence
- **T9 (seed 7) & T10 (seed 42)**: cast Chalice on X=1 while own 1-CMC
  removal (March, STP) sat in library. Correct play vs DnT is **Chalice
  off** — DnT's only relevant 1-drops are Vial / SFM tutors. Bricking
  4× March + 4× STP collapses the removal plan and tempo.
- **All seeds T5–T14**: no Wasteland / Karakas line vs Rishadan Port +
  Wasteland; protagonist accepts repeated manascrew.

## Responsible subsystem
`decks/wan_shi_tong.py:wan_shi_tong_turn` — Chalice-on-1 gate checks
only `player.hand` for own 1-CMCs (lines 81–83), ignoring library
composition and the opponent's 1-CMC threat density.

## Remediation hypothesis
Chalice-X selection must be a matchup-aware EV calc, not a "hand clean
now" snapshot. Wan Shi Tong's library is 1-CMC-heavy (STP, March, pitch
fodder); against opponents whose 1-CMC threat weight is below the
protagonist's own remaining 1-CMC spell density, Chalice@1 is negative
EV. A library-aware threshold belongs in the plugin's chalice selector
(or a shared `lock_piece_ev` helper). No engine change required —
decision lives in the deck-plugin layer per the abstraction contract.
