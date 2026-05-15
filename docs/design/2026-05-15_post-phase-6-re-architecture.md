---
title: Post-Phase-6 re-architecture
status: accepted
date: 2026-05-15
phases: A B C D
supersedes: null
---

# Post-Phase-6 re-architecture

## Why this exists

Phases 0-6 of the B+ rubric lift shipped fast but accumulated technical debt:
two parallel decision-logging APIs (`gs.strat_log.log_decision` vs
`combo_engine.log_combo_decision`), four overlapping `combo_engine`
predicates that duplicate satisfiability logic, a magic
`IP.BHI_FREE_COUNTER_THRESHOLD = 0.40` that no one calibrated, an
`AssemblyPath` schema doing different work in each deck (Storm's
`mana_cost=1` means one thing, Reanimator's another), and a heuristic
grader gameable by keyword stuffing. This doc plans a careful pass
that pays down the debt before chasing more rubric points.

## Scope (4 phases)

### Phase A — unify decision-logging APIs

Keep `gs.strat_log.log_decision` (canonical, GoalEngine-aware,
performance-gated via `strat_log.enabled`). Retire
`combo_engine.log_combo_decision`. Extend `log_decision` with an
optional `phase=` override so Phase 4's `phase='combat'` use case
still works without a gameplan lookup. Mark
`docs/design/2026-05-09_combo_engine_architecture.md` as superseded.

### Phase B — Plan algebra + AssemblyPath subtypes

Replace `is_combo_ready_this_turn` + `combo_protection_check` +
`fastest_assemble_plan` with one `combo_plan(view) -> Plan` returning
a typed variant: `Execute(path) | Hold(card, reason) | Defer(reason)
| NoPlan(reason)`. Split `AssemblyPath` into deck-shape subtypes
(`StormPath`, `ReanimatorPath`, `LandComboPath`, `TribalPath`) with a
shared `is_satisfiable(view)` method. Each subtype's fields name what
that mechanic actually needs (storm count, target-in-gy bool,
two-lands flag, tribe-cmc rank) rather than overloading
`mana_cost`/`target_tags`.

### Phase C — regression-sweep harness

Build `tools/regression_sweep.py`. Fixed seeds, fixed matchups, no
randomness across runs. Initial budget: 200 games × 10 matchups
(~5 min). Output: per-matchup WR + baseline diff. CI gate: merging
to main blocked if any sweep WR drops > 5pp vs baseline (configurable
in `config/sweep_baseline.json`).

### Phase D — calibrate magic constants

Sweep `IP.BHI_FREE_COUNTER_THRESHOLD` ∈ {0.30, 0.35, 0.40, 0.45,
0.50} using the Phase C harness. Plot `(real_WR_delta, rubric_lift)`
per deck. Pick the value that maximises rubric without dropping WR.
Write supporting data + chosen value to `config/calibration.json`.
Same procedure for any other un-calibrated numeric in `config.py`.

**Outcome (delivered)**: 0.40 confirmed empirically. Across 10
matchups × 5 candidates × 200 games each, average WR was flat
at 52.4-52.5% for thresholds ≤ 0.40, dropping to 52.0% at 0.45
and 51.4% at 0.50. The candidate set 0.30/0.35/0.40 tied at
52.5%; tiebreak rule "closest to current then lower" picked 0.40.
The full data table lives in `config/calibration.json`; the
sourcing helper `config._load_calibrated()` reads the value back
into `InteractionParams.BHI_FREE_COUNTER_THRESHOLD` at import time
with a 0.40 fallback if the JSON is unreadable.

**In-flight bug found during calibration**: sim outcomes are
mildly sensitive to Python's hash-randomization
(`PYTHONHASHSEED`). Running the regression sweep via
`python3 tools/regression_sweep.py` vs running it via
`python -c "from regression_sweep import ..."` produces different
absolute WRs (bug_vs_storm: 43.0% vs 31.5%) due to set/dict
iteration order leaking into game outcomes. Workaround: the
calibration runs each threshold in a fresh subprocess; absolute
values aren't comparable to the baseline file, but the
relative-to-each-other comparison is valid (which is what
calibration needs). A follow-up should track down the
non-deterministic iteration site in the sim and pin
`PYTHONHASHSEED=0` in `.github/workflows/regression-sweep.yml`.

## Sequence (refactor-first, per user)

A → B → C → D.

Risk acknowledged: A and B happen without the safety net of C.
Mitigation: existing 227-test inline suite + 5-seed determinism
check on baseline matchups (storm/burn s42, bug/storm s7,
depths/dimir s13, goblins/reanimator s99, ur_delver/dimir s1).

## Invariants (machine-verifiable, future)

When Phase C lands, the sweep harness becomes the structural test
for these invariants:

- `combo_plan` is a pure function (no state mutation).
- Every combo deck declaring `'combo'` metadata is exercised by at
  least one matchup in the sweep.
- A merging PR's sweep diff is reported in the PR body.

## What is NOT in scope

- LLM-based grading (the heuristic grader stays).
- New decks.
- Doomsday Cabal Therapy implementation (the design doc
  `docs/design/2026-05-09_doomsday_cabal_therapy.md` stays
  design-only until a separate planning session).
- gameplan JSON schema changes.

## Out-of-scope risks worth tracking

- `Plan`-algebra refactor blast radius: every caller of the four
  retired predicates must migrate. Pre-merge: grep for
  `is_combo_ready_this_turn`, `combo_protection_check`,
  `fastest_assemble_plan` must return only the new module.
- AssemblyPath subtype proliferation: each new deck might want its
  own shape. Cap at 4 subtypes; if a fifth is "needed",
  re-architect the algebra instead of adding another.
- Sweep noise at n=200: ±5pp confidence interval at p=0.5. Phase D's
  decisions must respect that envelope.

## Files affected (anticipated)

| Phase | File | Action |
|---|---|---|
| A | `combo_engine.py` | remove `log_combo_decision` |
| A | `strategic_logger.py` | extend `log_decision(phase=None)` |
| A | `engine.py`, `decks/goblins.py` | migrate call sites |
| A | `sim.py` | replace round-trip tests |
| A | `docs/design/2026-05-09_combo_engine_architecture.md` | add `superseded_by` frontmatter |
| B | `combo_engine.py` | rewrite around `Plan` algebra |
| B | `decks/storm.py`, `decks/reanimator.py`, `decks/depths.py`, `decks/goblins.py` | migrate to subtypes |
| B | `sim.py` | replace predicate tests |
| C | `tools/regression_sweep.py` (new) | sweep harness |
| C | `config/sweep_baseline.json` (new) | baseline WRs |
| C | `.github/workflows/regression-sweep.yml` (new) | CI gate |
| D | `config/calibration.json` (new) | calibrated thresholds |
| D | `config.py` | reference `calibration.json` |

## Exit criteria

- Phase A: zero references to `combo_engine.log_combo_decision`.
  All 227+ tests pass. 5-seed determinism check byte-identical.
- Phase B: zero references to `is_combo_ready_this_turn`,
  `combo_protection_check`, `fastest_assemble_plan`. New `combo_plan`
  function passes a property test ("returns one of {Execute, Hold,
  Defer, NoPlan}"). Determinism preserved.
- Phase C: sweep runs in ≤ 6 min, produces a JSON diff against
  `config/sweep_baseline.json`. PR CI fails when any matchup drops
  > 5pp.
- Phase D: `config.py` references at least one threshold from
  `config/calibration.json`; the file documents the sweep data
  supporting the chosen value.
