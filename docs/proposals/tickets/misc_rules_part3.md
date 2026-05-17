# Ticket: migrate `misc_rules_part3` into `tests/rules/test_misc_rules_part3.py`

**Source range**: `sim.py:2686-2936` inside `run_rules_tests()`
**Tests to migrate**: 15
**Target file**: `tests/rules/test_misc_rules_part3.py`

## Section headers in this slice

- (≥3) to make a hand-presence on the kill turn likely.
- Also assert deck construction has exactly 4 Cabal Therapy and 0 Lurrus
- Each subclass must inherit from Pile.
- Pre-fix the count was 0 (TS preamble consumed pitch fuel every game).
- Pre-fix the sim was 0-2/10. Set bar at ≥4/10 to catch regressions.
- Smoke-test the opener does not contain Lurrus (full deck draw).
- a regression pulls the matchup back below ~50%.
- canonical activation marker.

## Scope

You are migrating the `test(...)` assertions inside the source range above into
a new pytest file. **Touch nothing else.** When you are done, the parity
script (`python3 tools/test_parity.py`) must still pass.

## Allowed-to-touch

- `tests/rules/test_misc_rules_part3.py` (rewrite this stub completely)
- `tests/conftest.py` (only to add a fixture if multiple tests in this slice need it; do not change existing fixtures)

## Forbidden

- Editing `sim.py`, `engine.py`, `game.py`, `rules.py`, `cards.py`, `config.py`,
  or any deck file. The point of Phase 2 is migration, not behavior change.
- Adding any `card.name == "X"` check outside a `# abstraction-allow: rules-test` line.
- Combining multiple original `test(...)` calls into one pytest `def test_…()`.
  One assertion per test function.

## Success criteria

1. `python3 -m pytest tests/rules/test_misc_rules_part3.py -n auto` is green.
2. Test count matches: there are exactly **15** `def test_…` functions in
   the new file (one per source assertion).
3. Test names describe the **mechanic**, not the card. Rename anything that
   leaks a card name into the function name (card names in the test body are
   fine — that's where the rule fires).
4. `python3 tools/test_parity.py` still passes.

## How to migrate

1. Open `sim.py` lines 2686-2936. Look at the `test(name, actual, expected, detail)`
   pattern.
2. For each call:
   - Convert `test("X", a, b)` → `def test_<snake_x>(): assert a == b`.
   - Lift any local setup (variable bindings) into either the test body or a
     module-level fixture if shared.
   - Add `@pytest.mark.fast` decorator.
3. Run the file under `pytest -n auto`. Iterate until green.
4. Remove the `pytestmark = pytest.mark.skip(...)` from the stub.

## Hand-off

Commit message: `tests: migrate misc_rules_part3 (15 asserts) [ticket]`
