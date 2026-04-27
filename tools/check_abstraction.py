#!/usr/bin/env python3
"""Abstraction ratchet — block commits that add hardcoded card-name conditionals.

Pattern detected:
    <expr>.name == "<literal>"
    <expr>.name == '<literal>'
    name in (<literals>) / name in {<literals>}

Scope:
    All *.py at repo root and subdirs EXCEPT:
      - decks/        — deck-plugin modules legitimately reference card names
      - import_deck.py — CLI deck-import utility
      - this file itself

Lines tagged `# abstraction-allow: <reason>` are exempted (use for true
exceptions like enum checks or test fixtures).

Baseline behavior:
    count > baseline → exit 1, print new offenders
    count < baseline → exit 1, prompt to lower baseline (forces explicit ratchet)
    count == baseline → exit 0

Usage:
    python tools/check_abstraction.py
    python tools/check_abstraction.py --list
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = ROOT / "tools" / "abstraction_baseline.json"
ALLOW_MARKER = "# abstraction-allow"

# Files / directories that legitimately reference card names — excluded from scan.
EXCLUDE_DIRS = {"decks", ".git", "docs", "gameplans", "guides", "models",
                "replays", "results", "skills", "templates", "traces", "node_modules"}
EXCLUDE_FILES = {"import_deck.py"}

PATTERNS = [
    re.compile(r'\.name\s*==\s*"[^"]+"'),
    re.compile(r"\.name\s*==\s*'[^']+'"),
    re.compile(r"\bname\s+in\s+[\(\{]\s*['\"]"),
    re.compile(r"\bname\s+in\s+[\(\{]\s*$"),
]


def find_hits() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name in EXCLUDE_FILES:
            continue
        if rel == Path("tools/check_abstraction.py"):
            continue
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if ALLOW_MARKER in line:
                continue
            if any(p.search(line) for p in PATTERNS):
                hits.append((rel, i, line.rstrip()))
    return hits


def load_baseline() -> int:
    if not BASELINE_FILE.exists():
        return 0
    return int(json.loads(BASELINE_FILE.read_text())["hardcoded_name_count"])


def main(argv: list[str]) -> int:
    hits = find_hits()
    count = len(hits)

    if "--list" in argv:
        for path, lineno, line in hits:
            print(f"{path}:{lineno}: {line}")
        print(f"\nTotal: {count}")
        return 0

    baseline = load_baseline()

    if count > baseline:
        print(
            f"ABSTRACTION CONTRACT VIOLATION: hardcoded card-name conditionals "
            f"increased from {baseline} → {count}.",
            file=sys.stderr,
        )
        for path, lineno, line in hits:
            print(f"  {path}:{lineno}: {line}", file=sys.stderr)
        print(
            "\nFix options:\n"
            "  1. Use oracle text / type / tag fields, not card names.\n"
            "  2. Move card-specific knowledge into decks/*.py (excluded from this scan).\n"
            f"  3. If genuinely unavoidable, tag the line:  {ALLOW_MARKER}: <reason>",
            file=sys.stderr,
        )
        return 1

    if count < baseline:
        print(
            f"Abstraction count dropped from {baseline} → {count}. "
            f"Lower the baseline explicitly:",
            file=sys.stderr,
        )
        print(
            f'  echo \'{{"hardcoded_name_count": {count}}}\' > '
            f"{BASELINE_FILE.relative_to(ROOT)}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
