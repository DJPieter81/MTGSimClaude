# Cowork Brief E: Matrix N bump (200 → 500)

## One-sentence task
Re-run the full 36×36 matrix at n=500 to tighten σ from ±3.9pp to ±2.5pp and commit the new artifacts as the canonical reference.

## Why this matters
Current matrix is n=200. PLANNING_REFERENCE §3 says σ at n=200 is ±3.9%; bumping to n=500 brings it to ±2.5%. This:
- Resolves WR differences between 3-4pp that currently disappear in noise
- Gives the meta audit (EXPECTED_RANGES + symmetrise) cleaner signal
- Is the last data-quality step before declaring the sim ready for external use

Should run *after* sessions A (clock+BHI adoption), B (Karn), and C (response unification) land, so the matrix captures their WR impact in a single fresh dataset.

## Scope

### Part 1 — Baseline snapshot

```bash
# Copy current matrix so we can diff later
cp results/matrix_*.json /tmp/matrix_n200_baseline.json
cp results/matrix_bo3_*.json /tmp/matrix_bo3_n200_baseline.json
```

### Part 2 — Run both matrices at n=500

```bash
python3 refresh_all.py --resim 500 --decks 36 --seed 2026
# ~25 min for Bo1 matrix + regenerate all downstream artifacts
python3 run_meta.py --bo3-matrix --decks 36 -n 250 -s 2026
# ~10 min for Bo3 matrix at n=250 matches (300 games/pair worst case = ±2.8pp)
```

### Part 3 — Diff analysis

Produce `results/matrix_n200_vs_n500_diff.md`:
- How many matchup WRs moved by >3pp (should be < 1260 × 0.05 = 63 by σ alone)
- How many moved by >5pp (investigate these — likely real changes from sessions A/B/C)
- Sum of symmetry deltas: did averaging improve?

### Part 4 — Update docs

- `PLANNING_REFERENCE.md` §3 "Performance baselines" — update σ from ±3.9% to ±2.5%
- `CLAUDE.md` — bump sim count ("63,000 games → 180,000 games/pair" or similar)
- `guides/*.html` — regenerate via `gen_guides.py` against the fresh matrix (sentinel-protected guides survive)

### Part 5 — Spot-check regression

Run `python3 meta_audit.py` to ensure all EXPECTED_RANGES matchups stay in range. If any drop out, diagnose before merging.

## Constraints
- Seed must be pinned (`-s 2026`) for reproducibility.
- Don't commit the intermediate trace logs — just the final `matrix_*.json` / `matrix_bo3_*.json` / matrix HTMLs.
- If a spot-check drops out of range, it's either a real regression (investigate) or a calibration update to `EXPECTED_RANGES` (justify).

## Branch / PR
- Branch: `claude/mtgsim-matrix-n500-<suffix>` off main (AFTER A/B/C have merged).
- Title: "Matrix N bump 200 → 500 (±3.9pp → ±2.5pp)"
- 1-2 commits: run + regenerate all artifacts, optional findings doc.

## Expected outputs
- `results/matrix_<ts>_n500.json`
- `results/matrix_bo3_<ts>_n250.json`
- `results/meta_matrix_<ts>.html` (rebuilt)
- `results/meta_matrix_bo3_<ts>.html` (rebuilt)
- All 36 deck guides regenerated (sentinel-preserved for hand-crafts)

## Validation
- `verify.py all` exits 0
- `meta_audit.py` flags ≤ the current count of out-of-range spot-checks
- Symmetry outliers > 10%: current ~50, target ≤ 40 (tighter σ exposes fewer false-positive outliers)

## Timing
Don't start until A/B/C are merged. Running earlier wastes ~35 min of compute on a snapshot that won't reflect the latest strategy fixes.
