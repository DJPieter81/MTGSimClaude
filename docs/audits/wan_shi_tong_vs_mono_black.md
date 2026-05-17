---
title: Audit — wan_shi_tong vs mono_black
date: 2026-05-17
observed_wr: 0.155
target_wr: 0.45
gap_pp: -29.5
status: open
---

# wan_shi_tong vs mono_black — 15.5% WR

## Replays
- seed 42: LOSS — life 0 on T15 (Hymn + Grief beatdown after self-Chalice lock)
- seed 99: WIN T7 — Sanctifier en-Vec quad (pro-black is unblockable here)
- seed 7:  WIN T15 by timeout/board only (no real kill)

## Divergence
- Seed 42 T10: casts `Chalice of the Void` on 1 with 4 `March of Otherworldly Light` (CMC 1) still in library. From T11 onward March is countered by own Chalice on every draw (T17, T19, T21, T23, T25). Removal pool collapses to 4 STP + 5 wraths against 8 discard + recursive threats.
- Seed 42 T16: deploys `Wan Shi Tong` at exactly 4 mana, tapped out, without holding FoW/FoN. Mono-black instantly Snuff Outs it (CMC 4, not blocked by Chalice@1, 4 life is trivial). Engine never survives a turn.
- Seed 7 T5/T7: same pattern — Chalice@1 blanks own March, Snuff Out kills WST on entry.

## Responsible subsystem
`decks/wan_shi_tong.py:_strategy_wst` — Chalice deployment ignores remaining March copies in library, and engine deployment never reserves mana for a counter.

## Remediation hypothesis
Chalice-on-1 should be gated on remaining own-CMC-1 in `library` (not just hand), or on opponent archetype: vs discard-aggro, value of countering Push is low and locking out own March is catastrophic. WST should hold 2U for FoN/FoW when opponent has untapped Swamp. Both fixes live in the deck plugin.
