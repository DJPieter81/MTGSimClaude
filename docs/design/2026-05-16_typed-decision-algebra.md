---
status: proposed
author: agent-e
date: 2026-05-16
session: typed-decision-algebra
supersedes: null
superseded_by: null
---

# Typed `Decision` algebra — replacing the prefix-string contract

## 1. Problem statement

The structural grader's contract with the strategy layer is currently a set
of prefix-encoded **strings** that callers stuff into the `chosen` field of
a `log_decision(...)` call:

| token shape                              | meaning                                  |
|------------------------------------------|------------------------------------------|
| `combo:<path_tag>`                       | combo plan fired                         |
| `kill_<X>`, `cast_<combo>`, `entomb_<>`  | execute alternates                       |
| `tried_combo:<piece_tag>`                | piece played, kill disrupted             |
| `hold_<piece_tag>`                       | piece withheld for protection            |
| `defer`                                  | pass on firing this turn                 |
| `counter_<target>_with_<spell>`          | counterspell fired                       |
| `discard_<target>_with_<spell>`          | hand-disruption fired                    |
| `remove_<target>_with_<spell>`           | spot-removal fired                       |
| `attack with N <tribe>`                  | combat decision                          |

The structural grader reads these via `_is_counter() / _is_remove() /
_is_discard() / _is_execute() / _is_hold() / _is_defer() / _is_tried_combo() /
_is_combat_decision()` — eight prefix-matching helpers, each with a
constant tuple of allowed prefixes.

### Pain

1. **No type safety.** Typos in a `chosen` string get silently misclassified.
   `'counter_lightning_bolt_wth_fow'` (note the typo) currently still hits
   `_is_counter()` but is otherwise meaningless.
2. **Schema is implicit.** A new disruption kind ("rebound", "land-destroy",
   "extract") requires (a) inventing a prefix, (b) adding an `_is_X()`
   helper, (c) adding a `_PREFIX` constant, (d) hoping every emit site
   stays consistent. The schema lives in prose across two files.
3. **Composability is one-way.** The strategy can construct the token, but
   anything reading a token must re-parse `'counter_X_with_Y'` to recover
   the two tags — and there is no canonical parser.
4. **Anti-gameability is brittle.** The grader's gameability resistance
   depends on the prefix set being a closed list; a new emit site that
   accidentally uses a prefix collision (e.g. `'cast_counterspell'`
   shadowing the legacy `cast_<combo>` Execute prefix) is silently
   miscredited.

## 2. Algebra

A frozen-dataclass hierarchy. Root `Decision` carries the four fields every
trace entry already had (`turn`, `deck`, `phase`, `reason`, `candidates`).
Each subclass adds typed slots for its mechanic.

```
Decision (frozen)
├── ComboDecision        kind ∈ {execute, hold, defer, tried}, path_tag, piece_tag
├── DisruptionDecision   kind ∈ {counter, discard, remove, extract, land_destroy}, target_tag, instrument_tag
├── CombatDecision       kind ∈ {attack, block, hold}, attacker_count, attacker_tag
├── ManaDecision         kind ∈ {ramp, fix, burn, keep_open}, mana_value
├── MulliganDecision     kind ∈ {mull, keep}, hand_size, reason_tag
└── MetaDecision         kind ∈ {play_around, sideboard}, threat_tag
```

The mechanic each subclass models:

- **ComboDecision** unifies the four combo-axis tokens (`execute`/`hold`/
  `defer`/`tried`) under one type with a `kind` Literal.
- **DisruptionDecision** unifies counters, discard, removal, extract, and
  land-destroy under one type. New disruption kinds become new `kind`
  variants — no new `_is_*` helper required.
- **CombatDecision** captures the `attack with N <tribe>` form plus
  block/hold for future use.
- **ManaDecision**, **MulliganDecision**, **MetaDecision** are scaffolded
  but not yet wired by any callsite — they're placeholders so the grader
  has a place to dispatch when those axes get instrumented.

Every Decision is **frozen** (immutable). The grader can't accidentally
mutate a Decision after the strategy logged it.

## 3. Backward compatibility

`Decision.to_token()` returns a string byte-identical with what the
strategy layer currently puts in `chosen`. The JSON serialization shape
(`{'turn', 'deck', 'phase', 'candidates', 'chosen', 'reason'}`) is
unchanged.

| Decision (typed)                                    | `.to_token()` output         |
|-----------------------------------------------------|------------------------------|
| `ComboDecision(kind='execute', path_tag='storm')`   | `combo:storm`                |
| `ComboDecision(kind='execute', path_tag='')`        | `kill_C`                     |
| `ComboDecision(kind='hold', piece_tag='fow')`       | `hold_fow`                   |
| `ComboDecision(kind='defer')`                       | `defer`                      |
| `ComboDecision(kind='tried', piece_tag='darkrit')`  | `tried_combo:darkrit`        |
| `DisruptionDecision(kind='counter', target_tag='lightning_bolt', instrument_tag='fow')` | `counter_lightning_bolt_with_fow` |
| `DisruptionDecision(kind='discard', target_tag='fow', instrument_tag='ts')` | `discard_fow_with_ts` |
| `DisruptionDecision(kind='remove', target_tag='goyf', instrument_tag='push')` | `remove_goyf_with_push` |
| `CombatDecision(kind='attack', attacker_count=2, attacker_tag='goblins')` | `attack with 2 goblins` |

The legacy entry points:

- `log_decision(turn, deck, candidates, chosen, reason, phase=None)` —
  thin pass-through. Still accepts raw strings. **No change in behavior.**
- (Future) `log_disruption(turn, gs, player, kind, target_tag, instrument_tag, reason)` —
  constructs a `DisruptionDecision(...)` and calls the new `log(decision)`
  method. Currently no `log_disruption()` exists in the merged code; this
  doc reserves the contract for the upcoming PR.

## 4. Grader migration

`scripts/structural_grader.py` `_count_structural()` gains a typed
fast-path *at the head of the iteration loop*:

```python
for d in decisions:
    if isinstance(d, Decision):
        if isinstance(d, DisruptionDecision):
            counts[{'counter': 'counter',
                    'discard': 'discard',
                    'remove': 'removal',
                    'extract': 'discard',           # extract maps to discard bucket
                    'land_destroy': 'removal'}[d.kind]] += 1
        elif isinstance(d, ComboDecision):
            counts[{'execute': 'execute',
                    'hold': 'hold',
                    'defer': 'defer',
                    'tried': 'tried_combo'}[d.kind]] += 1
        elif isinstance(d, CombatDecision):
            counts['combat'] += 1
        # ManaDecision, MulliganDecision, MetaDecision — no axis yet
        continue
    # Legacy dict / string path (unchanged).
    chosen = d.get('chosen', '') or ''
    # … existing prefix-matching logic
```

The `_is_*` prefix helpers stay (they still grade JSON traces written
before this PR). The grader sees both shapes interchangeably.

## 5. Migration sequence

| Phase | Scope                                                         | Risk      |
|-------|---------------------------------------------------------------|-----------|
| 1     | Add `decision.py` + 6 subclasses + tests                       | Zero      |
| 2     | Add `StrategicLogger.log(decision)` method + tests             | Zero      |
| 3     | Shim `log_decision` (no behavior change) + tests               | Zero      |
| 4     | Grader `isinstance(d, Decision)` fast-path + tests             | Zero      |
| 5     | *(skipped this PR)* migrate the 36 `log_decision` callsites in `engine.py` / `sim.py` to construct Decision objects directly | Scope-creep |

Phase 5 is explicitly deferred. The 36 callsites all emit raw token
strings via `log_decision(...)`; rewriting them is a per-callsite mechanical
edit with regression risk that scales with the count. The shim path keeps
them unchanged. A follow-up PR can migrate per-deck strategies one at a
time, each guarded by `to_token()` byte-equality tests.

## 6. Risks

- **Serialization byte-equality.** Every `Decision.to_token()` output must
  be byte-identical with the prior token format. Round-trip tests pin this.
- **Frozen mutation.** Tests verify `FrozenInstanceError` is raised on
  attribute assignment, so accidental mutation cannot corrupt grader state.
- **Backward-compat trace JSON.** Old graded traces (pre-refactor) still
  load; tests pin a synthetic legacy trace grades identically.
- **Determinism.** 5-seed byte-identical replay verifies the shim doesn't
  alter game flow.
- **Regression sweep 0pp.** All 10 baseline matchups stay within tolerance.

## 7. Verification gates (this PR)

1. `python3 -c "from sim import run_rules_tests; run_rules_tests()"` — 282+ tests pass + 10+ new Decision tests.
2. `python3 tools/regression_sweep.py` — exit 0 (0pp delta on all 10 matchups).
3. `python3 tools/check_abstraction.py` — exit 0.
4. 5-seed determinism: storm/burn s42, bug/storm s7, depths/dimir s13, goblins/reanimator s99, ur_delver/dimir s1 — byte-identical replay log.
5. The four invariant tests from Agent C (adversarial keywords, empty-decisions storm-win-T4, storm-faked) stay green.
