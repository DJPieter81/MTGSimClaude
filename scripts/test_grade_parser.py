#!/usr/bin/env python3
"""Unit tests for grade_traces.py parser and helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grade_traces import parse_grades, grade_avg, check_threshold, RUBRIC_DOMAINS


# ---------------------------------------------------------------------------
# parse_grades
# ---------------------------------------------------------------------------

def test_parse_normal():
    """Standard 6-domain + overall response."""
    raw = """mulligan: B+ — Kept a reasonable 7
mana: A — Efficient sequencing throughout
combat: C — Missed a key block on T5
combo: A+ — Perfect Tendrils assembly
interaction: B — Decent Veil timing
meta: B+ — Played to the matchup well
overall: B+ — Solid but combat needs work"""

    g = parse_grades(raw)
    assert g['mulligan']['grade'] == 'B+'
    assert g['mana']['grade'] == 'A'
    assert g['combat']['grade'] == 'C'
    assert g['combo']['grade'] == 'A+'
    assert g['interaction']['grade'] == 'B'
    assert g['meta']['grade'] == 'B+'
    assert g.get('overall', {}).get('grade') == 'B+'
    print('  ✓ test_parse_normal')


def test_parse_with_dashes():
    """Response uses plain dash instead of em-dash."""
    raw = """mulligan: B - Good keep
mana: A+ - Perfect
combat: D - Terrible blocks
combo: F - Never assembled
interaction: C+ - Late counterspell
meta: B+ - Knew the matchup"""

    g = parse_grades(raw)
    assert g['mulligan']['grade'] == 'B'
    assert g['combo']['grade'] == 'F'
    assert g['interaction']['grade'] == 'C+'
    print('  ✓ test_parse_with_dashes')


def test_parse_empty():
    """Empty / garbage response → all UNGRADED."""
    g = parse_grades('')
    for d in RUBRIC_DOMAINS:
        assert g[d]['grade'] == 'UNGRADED'
    print('  ✓ test_parse_empty')


def test_parse_partial():
    """Only some domains present → rest UNGRADED."""
    raw = "mulligan: A — Great\nmana: B — Fine"
    g = parse_grades(raw)
    assert g['mulligan']['grade'] == 'A'
    assert g['mana']['grade'] == 'B'
    assert g['combat']['grade'] == 'UNGRADED'
    assert g['combo']['grade'] == 'UNGRADED'
    print('  ✓ test_parse_partial')


def test_parse_noisy():
    """Response has extra text / preamble before grade lines."""
    raw = """Here is my evaluation of the storm player's performance:

After careful review of the trace data, I'll grade each domain:

mulligan: B+ — The opening hand with LED + Infernal Tutor was a clear keep
mana: C+ — Could have sequenced lands better given Thalia tax
combat: B — N/A for storm but no misplays
combo: A — Assembled Tendrils efficiently once the window opened
interaction: B+ — Good Veil of Summer timing against potential removal
meta: A — Recognized the D&T matchup and played around hatebears

overall: B+ — Strong strategic play with room for improvement in mana management"""

    g = parse_grades(raw)
    assert g['mulligan']['grade'] == 'B+'
    assert g['mana']['grade'] == 'C+'
    assert g['combo']['grade'] == 'A'
    assert g['meta']['grade'] == 'A'
    print('  ✓ test_parse_noisy')


# ---------------------------------------------------------------------------
# grade_avg
# ---------------------------------------------------------------------------

def test_grade_avg_simple():
    assert grade_avg(['A', 'A']) == 'A'
    assert grade_avg(['A+', 'F']) in ('C+', 'C', 'B')  # midpoint
    assert grade_avg(['UNGRADED']) == 'UNGRADED'
    assert grade_avg([]) == 'UNGRADED'
    print('  ✓ test_grade_avg_simple')


# ---------------------------------------------------------------------------
# check_threshold
# ---------------------------------------------------------------------------

def test_threshold_pass():
    graded = [{
        'grades': {d: 'A' for d in RUBRIC_DOMAINS},
        'matchup': 'test', 'seed': 1
    }]
    passed, fails = check_threshold(graded, 'B-')
    assert passed
    assert len(fails) == 0
    print('  ✓ test_threshold_pass')


def test_threshold_fail():
    graded = [{
        'grades': {'mulligan': 'A', 'mana': 'F', 'combat': 'A',
                   'combo': 'A', 'interaction': 'A', 'meta': 'A'},
        'matchup': 'test', 'seed': 1
    }]
    passed, fails = check_threshold(graded, 'B-')
    assert not passed
    assert any('mana' in f for f in fails)
    print('  ✓ test_threshold_fail')


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print('Running grade parser tests...')
    test_parse_normal()
    test_parse_with_dashes()
    test_parse_empty()
    test_parse_partial()
    test_parse_noisy()
    test_grade_avg_simple()
    test_threshold_pass()
    test_threshold_fail()
    print('\nAll tests passed.')
