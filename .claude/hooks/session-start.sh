#!/bin/bash
# SessionStart hook: install dev dependencies so `pytest` and the
# verification tooling work in Claude Code on the web sessions.
set -euo pipefail

# Only needed in the remote (web) environment; local clones manage their own venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# pytest + xdist + timeout (test runner). Idempotent: pip skips satisfied reqs.
python3 -m pip install --quiet -r requirements-dev.txt

# Runtime dep used by guide generation / Scryfall lookups.
python3 -m pip install --quiet requests
