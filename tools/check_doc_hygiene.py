#!/usr/bin/env python3
"""Doc hygiene — enforce root .md allowlist and ban _V[0-9]+.md / numbered-suffix versioning.

Rules enforced:
  1. Root-level *.md must be in ALLOWLIST below.
  2. No file anywhere named *_V[0-9]+.md or *2.md / *3.md (number-suffix versioning).
     Supersession is recorded via frontmatter `superseded_by` on the original
     doc; never by spawning a sibling.

Usage:
    python tools/check_doc_hygiene.py
    python tools/check_doc_hygiene.py --list
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROOT_MD_ALLOWLIST = {
    "README.md",
    "CLAUDE.md",
    "PLANNING.md",
    "CROSS_PROJECT_SYNC.md",
}

# Catches *_V2.md, *_V3.md, etc. NOT date-suffixed files (those don't have _V).
# Number-suffix-only files like OVERNIGHT_TASK2.md are already caught by the
# root allowlist rule when they live at root.
VERSIONED_FILENAME = re.compile(r"_V[0-9]+\.md$")


def find_root_md() -> list[Path]:
    return sorted(p for p in ROOT.iterdir() if p.is_file() and p.suffix == ".md")


def find_versioned_md() -> list[Path]:
    hits: list[Path] = []
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT)
        if rel.parts and rel.parts[0] in {".git", "node_modules"}:
            continue
        if rel.parts[:3] == ("docs", "history", "plans"):
            continue
        if VERSIONED_FILENAME.search(p.name):
            hits.append(rel)
    return hits


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for p in find_root_md():
            mark = " " if p.name in ROOT_MD_ALLOWLIST else "!"
            print(f"  {mark} {p.name}")
        return 0

    failed = False

    root_md = find_root_md()
    disallowed = [p for p in root_md if p.name not in ROOT_MD_ALLOWLIST]
    if disallowed:
        failed = True
        print("DOC HYGIENE VIOLATION: root-level .md not in allowlist:", file=sys.stderr)
        for p in disallowed:
            print(f"  {p.name}", file=sys.stderr)
        print(
            "\nAllowed at root: " + ", ".join(sorted(ROOT_MD_ALLOWLIST)),
            file=sys.stderr,
        )
        print(
            "Move design/plan docs to docs/design/ or docs/proposals/ with frontmatter.\n"
            "Move finished single-shot tasks to docs/history/plans/.",
            file=sys.stderr,
        )

    versioned = find_versioned_md()
    if versioned:
        failed = True
        print(
            "\nDOC HYGIENE VIOLATION: number-suffix versioning is forbidden "
            "(use frontmatter `superseded_by` instead):",
            file=sys.stderr,
        )
        for p in versioned:
            print(f"  {p}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
