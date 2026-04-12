# Tempo Mirror Root Cause Analysis — FIXED

## Status: FIXED (2026-04-12)

Turn-function unification merged `protagonist_turn` (sim.py, 294 lines) and `opp_turn`
(engine.py, 155 lines) into a single `_execute_turn()` code path.

## Root Cause

`protagonist_turn` (P1) and `opp_turn` (P2) diverged over time. P1's path had features
that were never backported to P2:

| Feature | protagonist_turn (P1) | opp_turn (P2) | Impact |
|---|---|---|---|
| Bauble draws | Yes | **Missing** | P2 never resolved pending bauble draws |
| Land priority | Fetch > dual > basic > utility | `find_any(is_land)` — random pick | P2 played suboptimal lands |
| Wasteland activation | Yes (pre-strategy) | **Missing** | P2 never Wastelanded |
| Thoughtseize | Yes (pre-strategy) | **Missing** | P2 never stripped cards |
| Removal (Push/STP) | Yes (pre-strategy) | **Missing** | P2 never used pre-strategy removal |
| Goyf update at EOT | Yes | **Missing** | P2's Goyf stale at turn end |
| land_played reset | Yes | **Missing** | P2 could play 2 lands next turn |
| spells_cast reset | Yes | **Missing** | P2 spell count not reset |
| teferi_active reset | Missing | Yes | Minor |
| Rishadan Port | Missing | Yes | Minor (only for Vial decks) |
| Combat ordering | Combat → opponent responses | Opponent responses → combat | P2 combat after removal |

## Fix: `_execute_turn(gs, turn, b, o, who, matchup)`

Single 300-line function in sim.py parameterized by:
- `b` (active player), `o` (opponent)
- `who` ('p1' or 'p2') — for slot-specific lookups (treasure, deck key, log tag)
- `matchup` — deck key for strategy dispatch

Both `protagonist_turn` and `opp_turn` are now thin wrappers:
```python
def protagonist_turn(gs, turn, matchup):
    return _execute_turn(gs, turn, gs.p1, gs.p2, 'p1', matchup)

def opp_turn_unified(gs, turn, matchup):
    return _execute_turn(gs, turn, gs.p2, gs.p1, 'p2', matchup)
```

## Before/After

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Avg pairwise asymmetry | 12.5pp | 7.8pp | <=8pp |
| Dimir vs dimir_flash sum | 145% | ~126% | <=115% |
| Rules tests | 144/144 | 144/144 | 144/144 |
| 5 spot-checks | Pass | Pass | Pass |
| 36-deck smoke test | Pass | Pass | Pass |

## Remaining Asymmetry

The `_p1_respond_on_opp_turn` and `_p2_respond_on_pro_turn` response functions still
offer different instant-speed options per slot (P1 gets Flash Bowmasters + Force of Vigor;
P2 gets Snuff Out + Lightning Bolt). Unifying these is a follow-up task.
