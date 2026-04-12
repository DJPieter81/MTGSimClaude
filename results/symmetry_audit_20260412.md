# Symmetry Audit — matrix_20260412_085236

**Matrix:** 36 decks, 1260 matchups, n=200, seed 2026
**Generated:** 2026-04-12

## Summary

Of 630 matchup pairs, **107** have an asymmetry larger than 10% between P1 and P2 orderings (where "asymmetry" = |wr_as_p1 + wr_as_p2 − 1|). Ideally every pair sums to exactly 1.0; tempo mirrors routinely blow past 120% because P1 has inherent tempo advantage.

## Top 20 worst outliers

| Pair | P1 WR + P2 WR | Sum | &#124;Δ&#124; |
|------|---------------|-----|---------|
| dimir vs dimir_flash | 71.0 + 74.0 | 145.0 | 45.0 |
| dimir_b vs dimir_flash | 66.0 + 68.0 | 134.0 | 34.0 |
| dimir vs ur_tempo | 62.0 + 71.0 | 133.0 | 33.0 |
| eight_cast vs mono_black | 20.0 + 47.0 | 67.0 | 33.0 |
| bug vs ocelot | 72.0 + 60.0 | 132.0 | 32.0 |
| dimir_flash vs dnt | 56.0 + 75.5 | 131.5 | 31.5 |
| dimir_flash vs ocelot | 79.0 + 50.5 | 129.5 | 29.5 |
| bug vs dimir | 51.0 + 78.0 | 129.0 | 29.0 |
| dimir vs ocelot | 76.0 + 51.5 | 127.5 | 27.5 |
| dimir_b vs dnt | 54.0 + 71.5 | 125.5 | 25.5 |
| bug vs ur_tempo | 55.0 + 69.5 | 124.5 | 24.5 |
| dimir vs dimir_b | 53.5 + 70.5 | 124.0 | 24.0 |
| dimir vs dnt | 52.5 + 71.0 | 123.5 | 23.5 |
| burn vs eldrazi | 31.0 + 46.0 | 77.0 | 23.0 |
| dimir vs ur_delver | 51.0 + 71.5 | 122.5 | 22.5 |
| ur_aggro vs ur_delver | 7.5 + 70.5 | 78.0 | 22.0 |
| bug vs dimir_b | 42.5 + 79.5 | 122.0 | 22.0 |
| dimir_b vs ocelot | 56.5 + 65.5 | 122.0 | 22.0 |
| boros vs dimir_flash | 60.5 + 61.0 | 121.5 | 21.5 |
| dimir_b vs ur_tempo | 64.5 + 57.0 | 121.5 | 21.5 |

## Deck offender ranking

Counts of appearances across the 60 worst outlier pairs:

| Deck | Count | Note |
|------|-------|------|
| dimir | 13 | Tempo mirror inflation — every Dimir-mirror pair hits 120%+ |
| dimir_flash | 12 | Same tempo-mirror pattern |
| dimir_b | 12 | Same |
| ur_tempo | 7 | Tempo mirror |
| mono_black | 7 | Proxy strategy, PLANNING_REFERENCE §10 P1 #3 target |
| bug | 7 | Tempo mirror |
| dnt | 7 | Creature-based + blue disruption asymmetry |
| ocelot | 6 | Proxy strategy, highest meta share (12%) |
| depths | 6 | Combo asymmetry |
| ur_delver | 3 | Tempo mirror |

## Two patterns in the tail

1. **Tempo-mirror inflation (most of the list):** Both sides report 60%+ as P1. Caused by first-turn initiative in tempo matchups: P1 gets to land Delver / Ragavan / True-Name a turn ahead, and each side's simulation reflects this. Real Legacy dimir-mirrors have this exact asymmetry — PLANNING.md's §"Known Sim Limitations" P1 advantage row explicitly calls this out.

2. **Both-sides-lose (eight_cast vs mono_black, ur_aggro vs ur_delver, burn vs eldrazi):** These pairs sum to well under 1.0 (e.g. 67%, 78%, 77%). Not tempo inflation — asymmetric strategy failure. When one deck is asymmetrically nerfed by being in the P1 slot (or vice versa), both sides record a low WR. The `ur_aggro vs ur_delver` case is striking: 7.5% as P1, 70.5% as P2 — the ur_aggro-as-P1 strategy is actively broken.

## Recommended next steps

Most of the tempo-mirror inflation is unfixable without a proper initiative model (or accepting Bo3 with side change). `symmetrise_matrix()` already produces a properly-averaged JSON that downstream consumers should prefer.

The both-sides-lose cases are worth a pass each:
- `ur_aggro vs ur_delver` — investigate ur_aggro's P1 opener (7.5% is a smoking gun)
- `eight_cast vs mono_black` — both are proxy-strategy decks, upgrading either per §10 P1 #3 likely closes this
- `burn vs eldrazi` — check Eldrazi's Chalice timing vs Burn (Chalice@1 should blank Burn's CMC-1 spells but may not be firing fast enough)

## Reproduce

```bash
python3 -c "
from meta_results import load_matrix, symmetrise_matrix
out = symmetrise_matrix(load_matrix(), asymmetry_threshold=0.10)
for d1, d2, wr1, wr2, asym in sorted(out['symmetry_warnings'], key=lambda x: -x[4])[:20]:
    print(f'{d1} vs {d2}: {wr1:.0%} + {wr2:.0%} (|delta| {asym:.0%})')"
```
