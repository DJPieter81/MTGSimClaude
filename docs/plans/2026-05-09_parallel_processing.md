---
title: Parallel processing — next plan
date: 2026-05-09
audience: future-claude (Legacy session)
status: pending
branch: claude/plan-parallel-processing-nkYnY
prereq_reading:
  - parallel.py  (current 4 parallel entrypoints)
  - gen_guides.py:215-232  (sequential 72K-game bottleneck)
  - sim.py:276,308  (sequential public API)
  - refresh_all.py  (sequential 4-step pipeline)
---

# Parallel processing — next plan

## Goal

Cut wall-clock time for the three hot pipelines by parallelising the
remaining sequential bottlenecks and tightening the existing parallel
entrypoints. Target: `refresh_all.py --resim 200` from ~6 min → ~2.5 min,
`gen_guides.py` from ~250 s → ~60-80 s.

Out of scope: AI/strategy threading, GIL workarounds inside a single game,
GPU offload.

## Current state — findings

### Already parallel (`parallel.py`)
- `parallel_sweep` — splits N games across workers
- `parallel_meta_matrix` — one matchup per task
- `parallel_meta_matrix_bo3` — one Bo3 matchup per task
- `parallel_field` — one opponent per task

All use `mp.Pool(min(cpu_count(), 8))` and `pool.map`. Worker cap is
hard-coded; no progress reporting; no env-var override.

### Sequential bottlenecks
| Site | Volume | Why it matters |
|---|---|---|
| `gen_guides.py:215-232` | 72,000 games (2,000 × 36 decks) | Single-process loop. Largest sim cost in the pipeline. |
| `sim.run_sweep` (sim.py:276) | N games per call | Public API users (notebooks, ad-hoc scripts) hit serial path even though `parallel_sweep` exists. |
| `sim.run_meta_matrix` (sim.py:308) | NxN matchups | Same — `run_meta_matrix` is serial; `parallel_meta_matrix` is the parallel sibling. Easy to call the slow one by mistake. |
| `scripts/grade_traces.py:494-502` | 41 traces × API call + `time.sleep(0.5)` | Strictly serial; no rate-aware ThreadPool, no Anthropic Batch API. |
| `refresh_all.py:55-59` | 4 steps run in sequence | `gen_guides.py` and `build_matrix_html.py` are independent after `build_meta_inputs.py`. |

### Seed handling
Current behaviour (kept per session decision): each task gets
`random.randint(0, 2**31)` derived from the main process's random state, and
worker calls `random.seed(seed)` on entry. Reproducibility is preserved iff
the main process seeded its `random` first (the matrix CLI does so via
`-s SEED`). No API change; this plan will not re-architect seeding.

---

## Phase 1 — `gen_guides.py` parallelisation (P0, biggest win)

The 36-deck loop in `gen_guides.py:215-232` is embarrassingly parallel:
each deck's 2,000 games are independent. Today this runs single-process.

### Change shape
- Add `gen_guides_worker(deck_key, n_games, seed)` returning the same
  dict that the loop currently builds into `all_data[dk]`.
- Replace the outer loop with `mp.Pool(...).imap_unordered(...)` over
  `[(dk, 2000, seed_per_dk) for dk in DECKS]`.
- Wrap `imap_unordered` in a tqdm-free progress print (`done/total`).
- Keep the existing per-deck try/except guard inside the worker so a single
  bad deck doesn't poison the pool.
- Keep `all_data` assembly serial in the parent — workers return the
  per-deck dict, parent stitches.

### Files
- `gen_guides.py:215-232` — replace loop
- `parallel.py` — add `parallel_gen_guides(decks, n_games, n_workers, seed)`
  helper next to `parallel_field` so the worker function is picklable
  at module top level

### Acceptance
- `python3 gen_guides.py` produces byte-identical output for a fixed seed
  vs. a from-scratch single-process run on a small (3-deck) subset
- Wall-clock < 100 s on an 8-core box at n=2000 (down from ~250 s)
- All 7 guide features still present; `verify.py all` passes

---

## Phase 2 — Core API parallelisation in `sim.py`

`sim.run_sweep` and `sim.run_meta_matrix` are the documented entrypoints
(quoted in CLAUDE.md and PLANNING.md); the parallel versions live in
`parallel.py` and require an explicit import. Easy to use the slow one
by accident.

### Change shape
- `run_sweep(deck1, deck2, n_games, parallel=True)`:
  - default `parallel=True` when `n_games >= 50`, else serial (avoid pool
    overhead for tiny calls)
  - `parallel=True` delegates to `parallel.parallel_sweep`
  - keep all existing `use_*` kwargs (neural gates etc.) — they tunnel
    through the worker via task tuple
- `run_meta_matrix(decks, n_games, top_tier, parallel=True)`:
  - default `parallel=True`
  - delegates to `parallel.parallel_meta_matrix`
- Add `parallel=False` opt-out for debugging (single-process traces are
  much easier to read).

### Risk
Worker pickling of `use_neural_*` flags. Currently `parallel._run_games_worker`
ignores those kwargs entirely. Either (a) plumb them through, or (b) raise
a clear error if any are truthy and `parallel=True`. Recommend (a).

### Files
- `sim.py:276-305` — `run_sweep`
- `sim.py:308-354` — `run_meta_matrix`
- `parallel.py:14-32` — extend `_run_games_worker` to accept neural flags
- `tests/` — add a parity test: `run_sweep('storm','burn',60,parallel=True) == run_sweep(...,parallel=False)` under fixed seed

### Acceptance
- All existing call-sites (run_meta.py, refresh_all.py, notebooks) keep
  working without changes
- Parity test passes (same WR within ±1 game on fixed seed)
- Documented in CLAUDE.md "Core API" block

---

## Phase 3 — Workers + `imap_unordered` + `refresh_all.py` DAG

Three small, related changes.

### 3a. Lift the 8-worker cap
- Add `_resolve_workers(n_workers)` helper in `parallel.py`:
  - explicit arg wins
  - else `MTGSIM_WORKERS` env var
  - else `min(cpu_count(), 16)` (was 8)
- Document the env var in CLAUDE.md "Quick Start"

### 3b. Switch `pool.map` → `pool.imap_unordered`
For each parallel function: switch to `imap_unordered` and consume in a
loop with a `done/total` print every K results. Benefits:
- Live progress (current `pool.map` is a black box for ~6 min)
- Better load balancing when matchup runtimes vary (combo decks finish
  much faster than aggro mirrors)

Keep result aggregation deterministic (sort by `(d1, d2)` before building
the matrix dict) so symmetry-audit output is stable across runs.

### 3c. `refresh_all.py` DAG
After `build_meta_inputs.py`, `gen_guides.py` and `build_matrix_html.py`
are independent. Run them concurrently with `concurrent.futures.ProcessPoolExecutor(2)`:

```
build_meta_inputs.py
        |
   +----+----+
   |         |
gen_guides  build_matrix_html
   |         |
   +----+----+
        |
   verify.py all
```

Estimated savings: ~30 s on a 6-min refresh (`build_matrix_html.py` is
~30 s and currently sits behind `gen_guides.py`).

### Files
- `parallel.py` — `_resolve_workers`, four `imap_unordered` rewrites
- `refresh_all.py` — split `STEPS` into stages; run stage 2 concurrently
- `CLAUDE.md` — note `MTGSIM_WORKERS` env var

### Acceptance
- `MTGSIM_WORKERS=16 python3 refresh_all.py --resim 200` finishes in
  < 3.5 min on a 16-core box (was ~6 min on 8 cores)
- Matrix output is bit-for-bit identical to `pool.map` version under fixed seed
- Progress output shows N/M every 30 matchups during the matrix step

---

## Phase 4 — `grade_traces.py` API parallelism

API mode iterates serially with `time.sleep(0.5)` between calls (~22 s
minimum for 41 traces, longer with API latency). Two options:

### Option A — `concurrent.futures.ThreadPoolExecutor(max_workers=8)`
- Anthropic SDK is thread-safe; rate-limit headers can be inspected
- Drop the `time.sleep(0.5)` — the SDK handles 429 backoff if we wrap
  the call in the SDK's retry logic
- 8 concurrent calls × ~5 s/call → finishes in ~30 s instead of ~5 min

### Option B — Anthropic Message Batches API
- Submit all 41 prompts as a single batch
- 50% cost reduction; takes up to 24 h but typically minutes
- Better for nightly CI, worse for interactive `--force` re-grades

**Recommend Option A for this plan.** Option B is a follow-up if we move
to nightly CI grading. Local heuristic mode (`--local`) is already fast;
no change needed there.

### Files
- `scripts/grade_traces.py:493-503` — replace serial loop with
  ThreadPoolExecutor; preserve the `--force` semantics and the
  per-trace `_graded.json` write path (file IO is per-trace and
  thread-safe since paths differ)

### Acceptance
- `python3 scripts/grade_traces.py results/traces/*.json --force` finishes
  in < 1 min on the current 41-trace set (was ~5 min)
- `_graded.json` files are byte-identical to serial version (deterministic
  given fixed model + temperature)
- No 429 floods in the log

---

## Test plan

1. **Parity tests** (added in Phase 2, run in CI):
   - `run_sweep('storm','burn',60,parallel=True/False)` agree under fixed
     seed (within ±1 win — multiprocessing reorders, can't be exact)
   - `parallel_meta_matrix` output equals `run_meta_matrix(parallel=False)`
     on a 4-deck subset under fixed seed (within ±1 win/cell)

2. **Smoke**: `python3 -c "from sim import run_rules_tests; run_rules_tests()"`
   still prints `170 passed`. Tests must not regress.

3. **Walltime regression**: capture before/after on the same machine in
   the PR description. No need to add a benchmark suite.

4. **Output equality**: post-Phase-3, `results/matrix_*.json` from a
   fixed-seed re-run is bit-identical between `pool.map` and
   `imap_unordered` (after sort).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Pickling failure for neural-flag kwargs in worker | Phase 2 plumbs flags through task tuple; explicit test |
| `imap_unordered` reorders matrix → diff churn | Sort by `(d1,d2)` before building dict |
| Anthropic 429 storms in Phase 4 | Cap ThreadPool at 8; wrap in SDK retry |
| `gen_guides` worker imports `from sim import run_game` 36 times | One-time fork-cost; on Linux fork is cheap. Verify on macOS spawn. |
| `refresh_all.py` concurrent steps both write logs to stdout | Capture each step's output to a temp buffer, print serially when done |

## Suggested PR slicing

One PR per phase (4 PRs total), in order:
1. **PR A** — `gen_guides.py` parallelisation. Largest user-visible win,
   no API change. Ship first to validate the worker pattern.
2. **PR B** — `sim.py` core API `parallel=True` default + parity tests.
   Touches docs.
3. **PR C** — Workers + `imap_unordered` + `refresh_all.py` DAG.
   Includes `MTGSIM_WORKERS` env var.
4. **PR D** — `grade_traces.py` ThreadPool. Optional / lower urgency.

Estimated wall-clock: PR A 2-3 h, PR B 2 h, PR C 2-3 h, PR D 1-2 h.
Total ~8-10 h across 1-2 sessions.

## Out of scope (parking lot)

- Anthropic Batch API for `grade_traces.py` (Phase 4 Option B)
- GPU/Numba speedups for the inner game loop
- Replacing `multiprocessing` with `concurrent.futures.ProcessPoolExecutor`
  in `parallel.py` (cosmetic; current code is fine)
- Distributed runs across machines
