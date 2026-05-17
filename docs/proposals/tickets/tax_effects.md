# Ticket: migrate `tax_effects` into `tests/rules/test_tax_effects.py`

**Source range**: `sim.py:1987-2483` inside `run_rules_tests()`
**Tests to migrate**: 19
**Target file**: `tests/rules/test_tax_effects.py`

## Section headers in this slice

- Chalice CMC check (printed CMC)
- Trinisphere: all spells cost at least {3}
- Must place an actual Thalia creature on board (computed property)
- Chalice at X=0: blocks CMC 0 spells
- Chalice@1 blocks a CMC-1 spell
- Trinisphere taxes CMC-1 to cost 3
- Thalia +1 tax on noncreature spells

## Scope

You are migrating the `test(...)` assertions inside the source range above into
a new pytest file. **Touch nothing else.** When you are done, the parity
script (`python3 tools/test_parity.py`) must still pass.

## Allowed-to-touch

- `tests/rules/test_tax_effects.py` (rewrite this stub completely)
- `tests/conftest.py` (only to add a fixture if multiple tests in this slice need it; do not change existing fixtures)

## Forbidden

- Editing `sim.py`, `engine.py`, `game.py`, `rules.py`, `cards.py`, `config.py`,
  or any deck file. The point of Phase 2 is migration, not behavior change.
- Adding any `card.name == "X"` check outside a `# abstraction-allow: rules-test` line.
- Combining multiple original `test(...)` calls into one pytest `def test_…()`.
  One assertion per test function.

## Success criteria

1. `python3 -m pytest tests/rules/test_tax_effects.py -n auto` is green.
2. Test count matches: there are exactly **19** `def test_…` functions in
   the new file (one per source assertion).
3. Test names describe the **mechanic**, not the card. Rename anything that
   leaks a card name into the function name (card names in the test body are
   fine — that's where the rule fires).
4. `python3 tools/test_parity.py` still passes.

## How to migrate

1. Open `sim.py` lines 1987-2483. Look at the `test(name, actual, expected, detail)`
   pattern.
2. For each call:
   - Convert `test("X", a, b)` → `def test_<snake_x>(): assert a == b`.
   - Lift any local setup (variable bindings) into either the test body or a
     module-level fixture if shared.
   - Add `@pytest.mark.fast` decorator.
3. Run the file under `pytest -n auto`. Iterate until green.
4. Remove the `pytestmark = pytest.mark.skip(...)` from the stub.

## Hand-off

Commit message: `tests: migrate tax_effects (19 asserts) [ticket]`
