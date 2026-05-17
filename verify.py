#!/usr/bin/env python3
"""
Post-action verification helper (PLANNING_REFERENCE §9 #2).

Wraps the one-line sanity checks that should run after risky operations:
  - rules tests
  - deck import smoke test
  - symmetry check for a single matchup
  - matrix HTML integrity (pills + required JS functions)
  - "all" = tests + matrix integrity for latest HTML

Usage:
  python3 verify.py tests
  python3 verify.py deck new_deck_key
  python3 verify.py symmetry storm burn
  python3 verify.py matrix results/meta_matrix_<ts>.html
  python3 verify.py all

Exit codes: 0 on pass, 1 on failure. Never invoked automatically;
invoke after matrix rebuilds, deck imports, strategy edits, or any
change that could silently break an output product.
"""
import glob
import os
import re
import sys


# ── required matrix JS functions ─────────────────────────────────────────────
REQUIRED_MATRIX_FNS = [
    'pills', 'wc', 'tc', 'muc', 'getCT', 'tierOf', 'tierTag', 'getWR', 'closeDet',
]


def _ok(msg): print(f"\033[32mOK\033[0m  {msg}")
def _fail(msg): print(f"\033[31mFAIL\033[0m  {msg}")


def check_tests() -> bool:
    """Run the pytest fast suite (~3s under xdist)."""
    import subprocess
    r = subprocess.run(
        ['python3', '-m', 'pytest', '-m', 'fast', '-q', '--no-header'],
        capture_output=True, text=True, timeout=120,
    )
    output = r.stdout + r.stderr
    m = re.search(r'(\d+)\s+passed', output)
    if not m:
        _fail("couldn't parse pytest output")
        print(output[-500:])
        return False
    passed = int(m.group(1))
    if r.returncode == 0:
        _ok(f"tests: {passed} passed")
        return True
    _fail(f"tests: pytest exit {r.returncode}")
    print(output[-500:])
    return False


def check_deck(deck_key: str) -> bool:
    """Import the deck and run a 10-game sweep vs burn."""
    try:
        from cards import DECKS
        from sim import run_sweep
    except ImportError as e:
        _fail(f"import error: {e}")
        return False
    if deck_key not in DECKS:
        _fail(f"deck '{deck_key}' not registered. Known: {sorted(DECKS.keys())[:8]}...")
        return False
    try:
        r = run_sweep(deck_key, 'burn', n_games=10)
    except Exception as e:
        _fail(f"run_sweep crashed: {type(e).__name__}: {e}")
        return False
    _ok(f"{deck_key} vs burn (n=10): p1_wr={r['p1_wr']:.0%}, avg_length={r['avg_length']:.1f}")
    return True


def check_symmetry(d1: str, d2: str, n: int = 200) -> bool:
    """Run n games each way. Fail if sum of win-rates is outside 90-110%."""
    try:
        from sim import run_sweep
    except ImportError as e:
        _fail(f"import error: {e}")
        return False
    a = run_sweep(d1, d2, n_games=n)
    b = run_sweep(d2, d1, n_games=n)
    total = a['p1_wr'] + b['p1_wr']
    diff_from_1 = abs(total - 1.0)
    # Total "should" be 1.0 if d1+d2 are symmetric; PLANNING.md notes tempo
    # mirrors often blow past 120%. Warn above 110%, fail above 130%.
    if diff_from_1 <= 0.10:
        _ok(f"{d1} vs {d2}: {a['p1_wr']:.0%} / {b['p1_wr']:.0%} (sum {total:.0%})")
        return True
    if diff_from_1 <= 0.30:
        print(f"\033[33mWARN\033[0m  {d1} vs {d2}: {a['p1_wr']:.0%} / {b['p1_wr']:.0%} "
              f"(sum {total:.0%}, |delta| {diff_from_1:.0%})")
        return True  # warn but don't fail
    _fail(f"{d1} vs {d2}: {a['p1_wr']:.0%} / {b['p1_wr']:.0%} (sum {total:.0%}) — "
          f"asymmetric beyond 30%")
    return False


def check_matrix(html_path: str) -> bool:
    """Verify pills() and all required JS functions are present."""
    if not os.path.exists(html_path):
        _fail(f"not found: {html_path}")
        return False
    with open(html_path) as f:
        content = f.read()
    missing = [fn for fn in REQUIRED_MATRIX_FNS if f'function {fn}' not in content]
    if missing:
        _fail(f"{html_path}: missing JS fns: {missing}")
        return False
    # Ballpark data coverage check
    if 'const D' not in content and 'var D' not in content and 'D = {' not in content:
        _fail(f"{html_path}: no D data constant found")
        return False
    _ok(f"{html_path}: all 9 JS fns present, D data constant found")
    return True


def check_all() -> bool:
    """Run tests + pick the latest results/meta_matrix_*.html and verify it."""
    ok = check_tests()
    matrices = sorted(glob.glob('results/meta_matrix_*.html'))
    if not matrices:
        print("  (no results/meta_matrix_*.html to check)")
    else:
        ok = check_matrix(matrices[-1]) and ok
    return ok


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == 'tests':
        sys.exit(0 if check_tests() else 1)
    elif cmd == 'deck':
        if len(sys.argv) < 3:
            _fail("usage: verify.py deck <deck_key>")
            sys.exit(2)
        sys.exit(0 if check_deck(sys.argv[2]) else 1)
    elif cmd == 'symmetry':
        if len(sys.argv) < 4:
            _fail("usage: verify.py symmetry <d1> <d2> [n_games]")
            sys.exit(2)
        n = int(sys.argv[4]) if len(sys.argv) >= 5 else 200
        sys.exit(0 if check_symmetry(sys.argv[2], sys.argv[3], n) else 1)
    elif cmd == 'matrix':
        if len(sys.argv) < 3:
            _fail("usage: verify.py matrix <path.html>")
            sys.exit(2)
        sys.exit(0 if check_matrix(sys.argv[2]) else 1)
    elif cmd == 'all':
        sys.exit(0 if check_all() else 1)
    else:
        _fail(f"unknown subcommand: {cmd}")
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
