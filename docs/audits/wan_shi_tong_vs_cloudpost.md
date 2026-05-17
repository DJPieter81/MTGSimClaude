---
title: Audit — wan_shi_tong vs cloudpost
date: 2026-05-17
observed_wr: 0.12
target_wr: 0.45
gap_pp: -33
status: partial
follow_up: 2026-05-17 — Wasteland bumped 1 → 3 in WST decklist (cut
  1 Island + 1 Plains; 23 lands total unchanged). Sweep n=200: 12% →
  16% (+4pp on this matchup). Bonus: vs lands 61%, vs depths 49%
  (Wastelands disrupt land-combo engines broadly). Strategy gaps
  remain open: no Wasteland activation block in `_strategy_wst`, no
  counter-mana reservation against ramp payoffs, no Stock Up counter.
---

# wan_shi_tong vs cloudpost — 12% WR

## Replays
- seed 42: p1 win — opp life −1 T9 (atypical fast hand)
- seed 99: p1 win — opp life −2 T8 (atypical fast hand)
- seed 7:  p2 win — Karn lock T14 (representative; 50-seed: 3W/47L)

## Divergence
Note: `wan_shi_tong` is **UW Chalice Control** (DECK_META name `Wan Shi
Tong Control`, categories `{control,prison}`), NOT Dimir Flash — that
lives in `decks/dimir_flash.py`.

- **T2**: cloudpost Crop Rotation → Cloudpost. No counter; opener lacks
  blue card to pitch FoW.
- **T4/T6/T8**: 3× Stock Up unopposed. wst draws STP/March/Wrath —
  useless vs empty board.
- **T7 & T11**: Chalice in hand both turns, never deployed —
  `own_cmc1==0` guard blocks it because STP (CMC 1) sits in hand.
- **T12**: Karn resolves uncountered → T14 lock. Across 14 turns wst
  activated **zero** Wastelands despite 10 nonbasic targets — strategy
  has no Wasteland-activation code path.

## Responsible subsystem
`decks/wan_shi_tong.py:_strategy_wst` — strategy never models "deny
ramp": no Wasteland activation, no counter-mana reservation against
CMC-4 ramp payoffs, no Chalice-on-2 against CMC-2 Stock Up engine.
Decklist also ships 1 Wasteland against a 10-nonbasic opponent.

## Remediation hypothesis
Two layers, both inside `decks/wan_shi_tong.py`. Decklist: bump Wasteland
to 3–4 against ramp metas. Strategy: add Wasteland-activation block
(mirror `_strategy_bug` engine.py:1320–1374, lift to shared helper),
reserve UU for instant-speed counters vs `eldrazi`/`prison` category
opponents (mirror `_strategy_dimir_flash`), relax Chalice guard to allow
X=2 vs combo opponents whose engine spell is CMC 2. No engine changes —
strategy-coverage hole.
