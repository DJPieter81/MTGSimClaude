---
title: combo_engine — architecture
status: superseded-in-part
date: 2026-05-09
phase: Phase 1 of B+ rubric lift
supersedes: null
superseded_by: docs/design/2026-05-15_post-phase-6-re-architecture.md
superseded_scope: |
  The "decision emitter" concern (log_combo_decision) is retired in
  Phase A of the post-Phase-6 re-architecture. The strategic-decision
  log format remains identical, but the canonical emitter is now
  StrategicLogger.log_decision in strategic_logger.py — with an
  optional `phase=` override that preserves the Phase 4 use case
  (`phase='combat'` for combat-trigger logging without a gameplan entry).

  The three predicate functions (is_combo_ready_this_turn,
  combo_protection_check, fastest_assemble_plan) remain accurate as
  described here until Phase B replaces them with a Plan algebra.
---

# combo_engine — architecture

## Why this module exists

The [B+ rubric lift plan](../../README.md) wants four bottleneck combo decks
(Storm, Reanimator, Goblins, Depths) to lift their LLM-graded combo and
interaction averages from C+/B- to B+. The first audit round
(`results/llm_audit_report.md`) exposed two structural issues:

1. **`strategic_decisions` is empty in every trace.** `llm_judge.collect()`
   parses log lines of the form `T<n> [<deck>] [phase:<p>] chose <x> from
   [...] — <reason>`, but nothing in the engine ever emits that format. The
   heuristic grader (`scripts/grade_traces.py:_heuristic_grade`) keys on
   `decision.chosen + decision.reason` keywords (`'protect'`, `'force'`,
   `phase=='combo'`, `'attack', 'block', 'damage'`). With zero decisions
   logged, every combo deck falls through to the empty-decisions branches
   (line 165-167, 195-197) — locked at C/D regardless of whether the sim
   plays well.
2. **Combo decision-making is scattered.** Storm's protection check, the
   Reanimator-specific Thoughtseize-defer in `engine._execute_turn`, and the
   Depths multi-path tutor are all ad-hoc — no single module owns "should
   the combo deck go off this turn?" Per CLAUDE.md ABSTRACTION CONTRACT #2
   (which single module owns this rule?), they need a home.

`combo_engine.py` is that home and that emitter.

## Boundary

```
decks/<deck>.py               engine.py                 combo_engine.py
─────────────────             ─────────                 ──────────────
strategy(...)         ─────►  _execute_turn      ─────► is_combo_ready_this_turn(p, gs)
                                                        combo_protection_check(p, o, gs)
                                                        fastest_assemble_plan(p, gs, paths)
                                                        log_combo_decision(log_fn, ...)
```

- **decks/`<deck>`.py** declares `'combo'` metadata in `DECK_META` (combo
  pieces, protection tags, assembly paths). Strategy functions call into
  `combo_engine` for the four interface points above.
- **engine.py** consults `is_combo_ready_this_turn()` from the shared
  discard preamble (Phase 3) and otherwise stays out.
- **combo_engine.py** owns the predicates, the protection decision, the
  assembly-path chooser, and the canonical `log_combo_decision` emitter.

## Interface

### Pure-function predicates (Phases 2-5 implement)

- `is_combo_ready_this_turn(player, gs) -> bool`
  Reads deck-registry combo metadata. True iff every piece-flag is present
  in hand/board AND mana sufficient for the cheapest assembly path.
- `combo_protection_check(player, opponent, gs) -> ProtectionDecision`
  Consults `bhi.py` for opponent-known disruption. Returns
  `ProtectionDecision(defer: bool, hold: Card | None, reason: str)`.
- `fastest_assemble_plan(player, gs, paths) -> AssemblyPath | None`
  Sorts `paths` by `(turns_to_kill, mana_cost)`, returns the cheapest.

### Decision emitter (Phase 1 implements)

- `log_combo_decision(log_fn, *, turn, deck, phase, chosen, reason,
                      candidates=None)`
  Single source of truth for the line format consumed by
  `llm_judge.collect()`. Format:
  ```
  T<turn> [<deck>] [phase:<phase>] chose <chosen> from [<candidates>] — <reason>
  ```
  All keywords the heuristic grader cares about (`protect`, `force`,
  `phase:combo`, `attack`, `block`) appear via `phase` / `chosen` / `reason`.

## Schema additions

### `DECK_META['combo']` (optional)

Only combo decks declare it. Schema:

```python
'combo': {
    'pieces':          set[str],         # tag strings (no card names)
    'protection_tags': set[str],         # tags that can protect (fow, fon, …)
    'assembly_paths':  list[AssemblyPath],
    'preamble_skip':   bool,             # generalises engine TS-defer carve-out
}
```

`AssemblyPath` (dataclass in `combo_engine.py`):

```python
@dataclass(frozen=True)
class AssemblyPath:
    tag:           str          # internal name, no card-name strings
    required_tags: frozenset[str]  # combo-piece tags this path needs
    mana_cost:     int          # CMC sum of pay-to-fire spells
    turns_to_kill: int          # turns from completion to win
```

### `ProtectionDecision`

```python
@dataclass(frozen=True)
class ProtectionDecision:
    defer:  bool
    hold:   object | None  # Card or None — typed as object to avoid circular import
    reason: str
```

## Architecture-level invariants (mechanical tests)

These pin the boundary itself. They live in `sim.run_rules_tests()`
following the existing convention.

1. `test_log_combo_decision_emits_format_parsed_by_llm_judge` — round-trip
   the formatter through `llm_judge.collect()`'s parser; the parsed
   decision must have `phase`, `chosen`, `reason`, `candidates` populated.
2. `test_combo_engine_module_owns_zero_card_name_strings` — grep
   `combo_engine.py` for `\.name == "` and `name in [({]`. Must be 0.
3. `test_deck_registry_combo_meta_schema_validates` — every deck declaring
   `'combo'` has all four required keys (`pieces`, `protection_tags`,
   `assembly_paths`, `preamble_skip`).
4. `test_assembly_path_dataclass_required_fields` — building an
   `AssemblyPath` without all four fields raises.
5. `test_protection_decision_dataclass_required_fields` — same for
   `ProtectionDecision`.

Phases 2-5 add behaviour tests for the three `NotImplementedError` stubs.

## Out of scope for Phase 1

- Implementations of the three predicate stubs — Phases 2/3/5.
- Wiring strategy functions to call into `combo_engine` — Phases 2/3/5.
- Doomsday-specific Cabal Therapy work — Phase 6 (separate design doc).

## Open questions

- Should `combo_engine` consult the existing `goal_engine` / gameplan JSON,
  or stay independent? Defer until Phase 5 (Depths) — the multi-path
  chooser is the consumer that exposes the answer.
- `bhi.py` currently exposes `HandBelief` directly; should
  `combo_protection_check` go through a thin facade (e.g.
  `bhi.opponent_known_threats(gs, tags)`)? Decide in Phase 2.
