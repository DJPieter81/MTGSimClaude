"""
test_new_decks.py — Smoke tests for all new deck plugins.
Validates: deck size, key cards, strategy import, and 10-game BO3.
"""
import sys, time
sys.path.insert(0, '.')
sys.path.insert(0, '..')

from cards import DECKS
from decks import register_decks

# Register all plugin decks
registered = register_decks()
print(f"Registered plugin decks: {registered}\n")

NEW_DECKS = ['depths', 'burn', 'infect', 'goblins', 'belcher', 'ur_delver', 'tes']

results = []


def test_deck(name, expected_tags=None):
    """Test a single deck: size, key tags, and 10-game BO3 vs dimir."""
    print(f"--- {name} ---")
    errs = []

    # 1. Deck exists
    if name not in DECKS:
        print(f"  SKIP: {name} not in DECKS")
        results.append((name, 'SKIP', 'not registered'))
        return

    # 2. Deck size
    try:
        deck = DECKS[name]()
        if len(deck) != 60:
            errs.append(f"deck size = {len(deck)}, expected 60")
        else:
            print(f"  OK deck size = 60")
    except Exception as e:
        errs.append(f"deck construction failed: {e}")
        results.append((name, 'FAIL', str(e)))
        return

    # 3. Key tags
    tags = {c.tag for c in deck}
    if expected_tags:
        missing = expected_tags - tags
        if missing:
            errs.append(f"missing tags: {missing}")
        else:
            print(f"  OK key tags present: {expected_tags}")

    # 4. BO3 smoke test (10 games vs dimir)
    try:
        from sim import run_any_bo3
        t0 = time.time()
        r = run_any_bo3(name, 'dimir', 10)
        wr = r['match_wr'] * 100
        elapsed = time.time() - t0
        print(f"  OK BO3 vs dimir (10 games): {wr:.0f}% WR ({elapsed:.1f}s)")
    except Exception as e:
        errs.append(f"BO3 failed: {e}")

    # 5. BO3 vs bug (tests as antagonist)
    try:
        r2 = run_any_bo3('bug', name, 10)
        wr2 = r2['match_wr'] * 100
        print(f"  OK BUG vs {name} (10 games): {wr2:.0f}% BUG WR")
    except Exception as e:
        errs.append(f"antagonist BO3 failed: {e}")

    if errs:
        results.append((name, 'FAIL', '; '.join(errs)))
        for e in errs:
            print(f"  FAIL: {e}")
    else:
        results.append((name, 'PASS', ''))
        print(f"  PASS")


# Expected key tags for each deck
EXPECTED = {
    'depths':     {'depths', 'stage', 'crop'},
    'burn':       {'bolt', 'guide', 'eidolon'},
    'infect':     {'glistener', 'blighted', 'invigorate'},
    'goblins':    {'lackey', 'muxus', 'matron'},
    'belcher':    {'belcher', 'led', 'petal'},
    'ur_delver':  {'delver', 'drc', 'murk', 'bolt'},
    'tes':        {'led', 'burning_wish', 'tendrils'},
}

for name in NEW_DECKS:
    try:
        test_deck(name, EXPECTED.get(name))
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results.append((name, 'ERROR', str(e)))
    print()

# Summary
print("=" * 50)
print("SUMMARY")
print("=" * 50)
passed = sum(1 for _, s, _ in results if s == 'PASS')
failed = sum(1 for _, s, _ in results if s == 'FAIL')
skipped = sum(1 for _, s, _ in results if s == 'SKIP')
errors = sum(1 for _, s, _ in results if s == 'ERROR')
for name, status, msg in results:
    indicator = {'PASS': 'OK', 'FAIL': 'XX', 'SKIP': '--', 'ERROR': '!!'}[status]
    extra = f" ({msg})" if msg else ""
    print(f"  [{indicator}] {name}{extra}")
print(f"\n{passed} passed, {failed} failed, {skipped} skipped, {errors} errors")
print(f"Total decks in DECKS: {len(DECKS)}")
