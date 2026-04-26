# Affinity Audit — 2026-04-26

## Baseline (matrix_20260420_184146.json, n=500/pair)

- Flat avg WR: **72.47%**
- Weighted EV (meta_ev): **70.71%**
- Target: 50-55% weighted

## Live 5-opp baseline (n=200/opp, captured before any edits)

| Opponent | WR |
|---|---|
| bug    | 0.730 |
| dimir  | 0.770 |
| burn   | 0.580 |
| lands  | 0.710 |
| oops   | 0.605 |
| **avg** | **0.679** |

Saved to `results/affinity_5opp_baseline.json`. Target: avg ≤ 0.55.

## Top over-performers in stale matrix (sorted desc)

| Opponent | WR | Notes |
|---|---|---|
| doomsday | 0.942 | combo |
| eight_cast | 0.916 | mirror — affinity vs affinity-like |
| goblins | 0.886 | aggro |
| elves | 0.842 | combo-aggro |
| cloudpost | 0.824 | ramp/combo |
| mardu | 0.792 | aggro |
| dnt | 0.784 | hatebears |
| ocelot | 0.782 | aggro |
| storm | 0.780 | combo |
| boros | 0.778 | aggro |
| ur_delver | 0.776 | tempo |
| dimir_flash | 0.772 | tempo |
| bug | 0.770 | tempo |
| painter | 0.766 | combo |
| reanimator | 0.752 | combo |
| ... | (15 more decks > 0.65) | |

**Pattern**: dominates combo (78-94%), aggro (78-89%), tempo (62-78%). Only loses to: oops (0.51), prison (0.60), lands (0.60), depths (0.60), burn (0.61). The combo over-performance is the clearest tell — Affinity has main-deck FoW that real 8-Cast doesn't run, letting it pre-emptively counter T1-T2 combo wins.

## Root cause hypotheses (cited)

1. **R1 — Maindeck 4× Force of Will** at `decks/affinity.py:145-146`. Real Legacy 8-Cast does NOT run maindeck FoW (no blue critical mass — only 3 Monitor + 2 Cannoneer cast U). With 4 Seat-of-the-Synod blue + 4 FoW the deck plays like a control deck. **Top driver vs combo**.
2. **R2 — Cannoneer +N/+N stacks unbounded** at `decks/affinity.py:837-845`. With 8 Baubles + 4 Petals + 4 Opals on T2-T3, Cannoneer becomes a 7/7 unblockable trampler vs anything. Real Cannoneer counter cap should be 1-2 per turn under realistic ETB cadence.
3. **R3 — `_keep_affinity` keeps essentially anything** at `decks/affinity.py:942-949`. Predicate is `fast_mana ≥ 1 AND (threats ≥ 1 OR engine)`. With 16 fast-mana sources + 16 affinity creatures, this keeps ~95% of openers including 1-land Petal hands.
4. **R4 — Emry recursion is unconditional** at `decks/affinity.py:619-793`. Single untapped Emry recurs arbitrary GY artifact every turn at affinity-reduced cost; never modeled as a removal target. Real Emry is a 1/2 that gets bolted on sight.
5. **R5 — Land count 15** vs real lists ~22. Combined with 4 Tomb + 4 Opal + 4 Petal = 16 fast/free mana sources, the deck almost never floods or stalls. **Deferred** — risks toxic interaction with `_affinity_cost` and Saga chapter logic.

## Fix order (4 attempts max)

| # | Fix | Addresses | File:Line |
|---|---|---|---|
| F1 | Remove 4× FoW, swap in 4× Frogmite | R1 | decks/affinity.py:145-146, test L872-879 |
| F2 | Cap Cannoneer counters at min(triggers, 2) | R2 | decks/affinity.py:837-845 |
| F3 | Tighten `_keep_affinity`: 2+ lands OR (1 land AND 2+ fast mana) | R3 | decks/affinity.py:942-949 |
| F4 | Restrict Emry recursion to 0-cost artifacts | R4 | decks/affinity.py:619-793 |

## Regression policy

- **Per attempt**: `verify.py all` (must show ≥147 passed) + 5-opp sweep n=200. Keep only if avg drops ≥3pp toward 50%.
- **Post-resim gates**: tests pass, affinity weighted < 70.71%, cross-deck mean |Δ| ≤ 3pp.
- **Single failed gate**: revert last commit. **All 3 failed**: hard reset to 3b01a13 + force-with-lease push.
