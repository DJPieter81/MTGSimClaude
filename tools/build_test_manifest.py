"""Parse sim.py:run_rules_tests() and emit a migration manifest + ticket stubs.

Outputs:
- docs/proposals/2026-05-17_pytest-migration.md  (overview table)
- docs/proposals/tickets/<slug>.md               (one per target test file)
- tests/rules/test_<slug>.py                     (skip stubs)
- tools/test_parity_data.json                    (machine-readable manifest)

The grouping rule: scan run_rules_tests() top-to-bottom, accumulate adjacent
test() calls under their nearest preceding "header comment", then bin headers
into target files (~10-20 tests per file). Each target file = one ticket.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "sim.py"
OUT_MANIFEST = ROOT / "docs" / "proposals" / "2026-05-17_pytest-migration.md"
OUT_TICKETS = ROOT / "docs" / "proposals" / "tickets"
OUT_TESTS = ROOT / "tests" / "rules"
OUT_DATA = ROOT / "tools" / "test_parity_data.json"

TARGET_TESTS_PER_FILE = 15  # soft cap; we split when exceeded
HEADER_RE = re.compile(r"^\s*#\s*(?:──\s*)?(.+?)\s*(?:──+\s*)?$")
TEST_CALL_RE = re.compile(r"\btest\(")


@dataclass
class TestCall:
    line: int
    section: str
    raw: str


@dataclass
class Bucket:
    slug: str
    title: str
    headers: List[str] = field(default_factory=list)
    tests: List[TestCall] = field(default_factory=list)
    line_lo: int = 0
    line_hi: int = 0


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:48] or "section"


def classify(header: str) -> str:
    """Map a header to a topical bin key."""
    h = header.lower()
    m = re.search(r"cr\s*(\d+)", h)
    if m:
        return f"cr_{m.group(1)[:3]}"
    keywords = [
        ("trinisphere", "tax_effects"),
        ("thalia", "tax_effects"),
        ("chalice", "tax_effects"),
        ("sphere", "tax_effects"),
        ("eidolon", "burn_triggers"),
        ("bowmaster", "bowmasters"),
        ("force of will", "force_of_will"),
        ("fow", "force_of_will"),
        ("daze", "free_counters"),
        ("foil", "free_counters"),
        ("doomsday", "deck_doomsday"),
        ("storm", "deck_storm"),
        ("ant", "deck_storm"),
        ("eldrazi", "deck_eldrazi"),
        ("depths", "deck_depths"),
        ("dnt", "deck_dnt"),
        ("d&t", "deck_dnt"),
        ("burn", "deck_burn"),
        ("oops", "deck_oops"),
        ("reanimator", "deck_reanimator"),
        ("lands", "deck_lands"),
        ("painter", "deck_painter"),
        ("prison", "deck_prison"),
        ("sneak", "deck_sneak"),
        ("affinity", "deck_affinity"),
        ("dimir", "deck_dimir"),
        ("delver", "deck_delver"),
        ("nethergoyf", "deck_dimir"),
        ("tarmogoyf", "creature_pt"),
        ("legend rule", "legend_rule"),
        ("thoughtseize", "discard"),
        ("wasteland", "lands_mechanics"),
        ("fetch", "lands_mechanics"),
        ("blood moon", "lands_mechanics"),
        ("back to basics", "lands_mechanics"),
        ("mana", "mana_pool"),
        ("sideboard", "sideboard"),
        ("bo3", "sideboard"),
        ("control", "matchup_invariants"),
        ("symmetry", "matchup_invariants"),
        ("decklist", "deck_construction"),
        ("60", "deck_construction"),
        ("companion", "deck_construction"),
        ("priority", "stack_priority"),
        ("counter", "counter_spells"),
        ("damage", "combat_damage"),
        ("combat", "combat_damage"),
        ("attack", "combat_damage"),
        ("block", "combat_damage"),
        ("summoning sick", "combat_damage"),
        ("removal", "removal"),
        ("dismember", "removal"),
        ("stp", "removal"),
        ("swords", "removal"),
        ("push", "removal"),
        ("decay", "removal"),
        ("brainstorm", "cantrips"),
        ("ponder", "cantrips"),
        ("preordain", "cantrips"),
        ("cantrip", "cantrips"),
    ]
    for kw, bin_ in keywords:
        if kw in h:
            return bin_
    return "misc_rules"


def parse_run_rules_tests(text: str) -> List[TestCall]:
    """Return ordered list of test() calls inside run_rules_tests()."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("def run_rules_tests"):
            start = i
            break
    if start is None:
        raise RuntimeError("run_rules_tests() not found in sim.py")
    # End at next top-level def or EOF
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("def "):
            end = i
            break

    calls: List[TestCall] = []
    current = "Setup"
    for ln in range(start, end):
        raw = lines[ln]
        stripped = raw.strip()
        # Skip the test() helper definition itself
        if stripped.startswith("def test("):
            continue
        m = HEADER_RE.match(raw)
        if m and stripped.startswith("#"):
            txt = m.group(1).strip()
            # Filter out obvious code comments that aren't section headers
            if (
                len(txt) > 3
                and not txt.lower().startswith(("noqa", "type:", "fmt:"))
                and not stripped.startswith("# nonlocal")
            ):
                current = txt
        if TEST_CALL_RE.search(stripped) and not stripped.startswith("def "):
            calls.append(TestCall(line=ln + 1, section=current, raw=stripped[:120]))
    return calls


def bucket_calls(calls: List[TestCall]) -> List[Bucket]:
    """Group test calls into buckets by classify(section), splitting if too large."""
    by_bin: dict[str, Bucket] = {}
    for c in calls:
        key = classify(c.section)
        b = by_bin.setdefault(key, Bucket(slug=key, title=key.replace("_", " ").title()))
        b.tests.append(c)
        if not b.line_lo or c.line < b.line_lo:
            b.line_lo = c.line
        if c.line > b.line_hi:
            b.line_hi = c.line
        if c.section not in b.headers:
            b.headers.append(c.section)

    # Split buckets that are too large
    out: List[Bucket] = []
    for b in by_bin.values():
        if len(b.tests) <= TARGET_TESTS_PER_FILE * 2:
            out.append(b)
            continue
        # Split into chunks of TARGET_TESTS_PER_FILE
        chunks = [
            b.tests[i : i + TARGET_TESTS_PER_FILE]
            for i in range(0, len(b.tests), TARGET_TESTS_PER_FILE)
        ]
        for idx, chunk in enumerate(chunks, 1):
            nb = Bucket(
                slug=f"{b.slug}_part{idx}",
                title=f"{b.title} (part {idx})",
                tests=chunk,
                line_lo=chunk[0].line,
                line_hi=chunk[-1].line,
            )
            nb.headers = sorted({t.section for t in chunk})
            out.append(nb)
    out.sort(key=lambda x: x.line_lo)
    return out


STUB_TEMPLATE = '''"""Migration stub for ticket: {slug}.

Source: sim.py:run_rules_tests() lines {lo}-{hi}
Test count: {count}
Headers covered:
{header_list}
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Phase-2 migration — ticket {slug}")


@pytest.mark.fast
def test_placeholder_{slug}():
    """Migration ticket: see docs/proposals/tickets/{slug}.md."""
    assert False, "stub — migrate from sim.py:{lo}-{hi}"
'''

TICKET_TEMPLATE = """# Ticket: migrate `{slug}` into `tests/rules/test_{slug}.py`

**Source range**: `sim.py:{lo}-{hi}` inside `run_rules_tests()`
**Tests to migrate**: {count}
**Target file**: `tests/rules/test_{slug}.py`

## Section headers in this slice

{header_block}

## Scope

You are migrating the `test(...)` assertions inside the source range above into
a new pytest file. **Touch nothing else.** When you are done, the parity
script (`python3 tools/test_parity.py`) must still pass.

## Allowed-to-touch

- `tests/rules/test_{slug}.py` (rewrite this stub completely)
- `tests/conftest.py` (only to add a fixture if multiple tests in this slice need it; do not change existing fixtures)

## Forbidden

- Editing `sim.py`, `engine.py`, `game.py`, `rules.py`, `cards.py`, `config.py`,
  or any deck file. The point of Phase 2 is migration, not behavior change.
- Adding any `card.name == "X"` check outside a `# abstraction-allow: rules-test` line.
- Combining multiple original `test(...)` calls into one pytest `def test_…()`.
  One assertion per test function.

## Success criteria

1. `python3 -m pytest tests/rules/test_{slug}.py -n auto` is green.
2. Test count matches: there are exactly **{count}** `def test_…` functions in
   the new file (one per source assertion).
3. Test names describe the **mechanic**, not the card. Rename anything that
   leaks a card name into the function name (card names in the test body are
   fine — that's where the rule fires).
4. `python3 tools/test_parity.py` still passes.

## How to migrate

1. Open `sim.py` lines {lo}-{hi}. Look at the `test(name, actual, expected, detail)`
   pattern.
2. For each call:
   - Convert `test("X", a, b)` → `def test_<snake_x>(): assert a == b`.
   - Lift any local setup (variable bindings) into either the test body or a
     module-level fixture if shared.
   - Add `@pytest.mark.fast` decorator.
3. Run the file under `pytest -n auto`. Iterate until green.
4. Remove the `pytestmark = pytest.mark.skip(...)` from the stub.

## Hand-off

Commit message: `tests: migrate {slug} ({count} asserts) [ticket]`
"""


def main() -> None:
    text = SIM.read_text()
    calls = parse_run_rules_tests(text)
    buckets = bucket_calls(calls)

    OUT_TICKETS.mkdir(parents=True, exist_ok=True)
    OUT_TESTS.mkdir(parents=True, exist_ok=True)
    (OUT_TESTS / "__init__.py").write_text("")

    # Write per-bucket files
    for b in buckets:
        header_list = "\n".join(f"- L{t.line}: {t.section}" for t in b.tests)
        header_block = "\n".join(f"- {h}" for h in b.headers) or "- (none)"
        (OUT_TESTS / f"test_{b.slug}.py").write_text(
            STUB_TEMPLATE.format(
                slug=b.slug,
                lo=b.line_lo,
                hi=b.line_hi,
                count=len(b.tests),
                header_list=header_list,
            )
        )
        (OUT_TICKETS / f"{b.slug}.md").write_text(
            TICKET_TEMPLATE.format(
                slug=b.slug,
                lo=b.line_lo,
                hi=b.line_hi,
                count=len(b.tests),
                header_block=header_block,
            )
        )

    # Manifest
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    total = sum(len(b.tests) for b in buckets)
    lines = [
        "---",
        "title: Pytest migration manifest",
        "date: 2026-05-17",
        "status: open",
        "owner: claude/plan-rapid-iterations-ktjdj",
        "---",
        "",
        "# Pytest Migration Manifest",
        "",
        f"Generated by `tools/build_test_manifest.py` on 2026-05-17. ",
        f"Total source assertions: **{total}**. ",
        f"Target test files: **{len(buckets)}**.",
        "",
        "## Tickets",
        "",
        "| Slug | Tests | Source lines | Title |",
        "|------|-------|--------------|-------|",
    ]
    for b in buckets:
        lines.append(
            f"| [`{b.slug}`](tickets/{b.slug}.md) | {len(b.tests)} "
            f"| L{b.line_lo}-{b.line_hi} | {b.title} |"
        )
    lines += [
        "",
        "## Parity gate",
        "",
        "`python3 tools/test_parity.py` runs both `run_rules_tests()` and pytest, ",
        "asserts the pass count is identical. Until every ticket above lands, this ",
        "script is the source of truth that no test was dropped.",
        "",
        "## Dispatch",
        "",
        "Phase 2 launches 8 agents per batch, each picks one open ticket. ",
        "Agents work in `isolation: \"worktree\"` to avoid collisions.",
    ]
    OUT_MANIFEST.write_text("\n".join(lines) + "\n")

    # Machine-readable data for the parity script + dispatcher
    OUT_DATA.write_text(
        json.dumps(
            {
                "total_assertions": total,
                "buckets": [
                    {
                        "slug": b.slug,
                        "count": len(b.tests),
                        "line_lo": b.line_lo,
                        "line_hi": b.line_hi,
                        "headers": b.headers,
                    }
                    for b in buckets
                ],
            },
            indent=2,
        )
    )

    print(f"Wrote {len(buckets)} ticket files, {total} assertions, manifest at {OUT_MANIFEST}")


if __name__ == "__main__":
    main()
