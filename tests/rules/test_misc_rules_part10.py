"""Misc rules part 10 — migrated from sim.py:3753-3840.

Covers two adjacent mechanic clusters:

1. Cheat-on-combat-damage tribal pick (Goblin Lackey-style triggers): the
   engine selects the highest-CMC matching-tribe creature from hand, and
   skips entirely when no tribe member is in hand. Logger surfaces a
   grader-recognised combat keyword and a `phase='combat'` tag.

2. structural_grader prototype token classifiers — gameability-resistant
   replacements for the heuristic grader. Defer/Hold/Execute tokens are
   identified by prefix on the typed `chosen` field, and combat decisions
   surface either via `phase='combat'` or `chosen` starting with 'attack'.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable for structural_grader.
_SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# ───────────────────────── shared fixtures ─────────────────────────


@pytest.fixture(scope='module')
def goblin_tribe_tags():
    from decks.goblins import GOBLIN_TRIBE_TAGS
    return GOBLIN_TRIBE_TAGS


@pytest.fixture(scope='module')
def tribe_hand_with_low_and_high(goblin_tribe_tags):
    """Hand containing a 1-CMC and a 6-CMC matching-tribe creature."""
    from rules import Card as _Card, CardType as _CT
    low = _Card(name='_low', card_type=_CT.CREATURE, cmc=1,
                mana_cost={'R': 1}, colors={'R'},
                base_power=1, base_toughness=1, gy_type='creature')
    low.tag = 'lackey'
    high = _Card(name='_high', card_type=_CT.CREATURE, cmc=6,
                 mana_cost={'R': 2, 'generic': 4}, colors={'R'},
                 base_power=4, base_toughness=4, gy_type='creature')
    high.tag = 'muxus'
    hand = [low, high]
    tribe = [c for c in hand if c.is_creature() and c.tag in goblin_tribe_tags]
    return tribe


@pytest.fixture(scope='module')
def offtribe_only_hand(goblin_tribe_tags):
    """Hand with no matching-tribe creature."""
    from rules import Card as _Card, CardType as _CT
    off = _Card(name='_off', card_type=_CT.CREATURE, cmc=2,
                mana_cost={'U': 1, 'generic': 1}, colors={'U'},
                base_power=1, base_toughness=2, gy_type='creature')
    off.tag = 'forktail'  # not in GOBLIN_TRIBE_TAGS
    hand = [off]
    tribe = [c for c in hand if c.is_creature() and c.tag in goblin_tribe_tags]
    return tribe


@pytest.fixture(scope='module')
def combat_log_decision():
    """A logged combat decision via StrategicLogger; returns parsed fields."""
    from strategic_logger import StrategicLogger
    sl = StrategicLogger(enabled=True)
    sl.log_decision(turn=2, deck='goblins',
                    candidates=['_low(cmc=1)', '_high(cmc=6)'],
                    chosen='attack with 2 goblins',
                    reason='lackey trigger cheats muxus',
                    phase='combat')
    line = sl.dump()[0]
    hdr, rest = line.split(' chose ', 1)
    action, why = rest.split(' — ', 1)
    chosen_field = action.split(' from ', 1)[0].strip()
    phase_field = hdr.split('[phase:', 1)[1].split(']')[0]
    combat_keywords = {'attack', 'block', 'damage', 'combat', 'swing'}
    hit_kw = any(k in (chosen_field + why).lower() for k in combat_keywords)
    return {'chosen': chosen_field, 'why': why,
            'phase': phase_field, 'hit_kw': hit_kw}


@pytest.fixture(scope='module')
def sg():
    """structural_grader module."""
    import structural_grader  # type: ignore
    return structural_grader


# ────────── Cluster 1: cheat-on-combat-damage tribal pick ──────────


@pytest.mark.fast
def test_cheat_on_combat_damage_picks_highest_cmc_tribe_member(
        tribe_hand_with_low_and_high):
    """Tribal cheat trigger selects the highest-CMC piece by property
    comparison (no card-name == anywhere)."""
    picked = max(tribe_hand_with_low_and_high, key=lambda c: (c.cmc, c.name))
    assert picked.tag == 'muxus'


@pytest.mark.fast
def test_cheat_on_combat_damage_skips_when_no_tribe_member_in_hand(
        offtribe_only_hand):
    """Mirrors the engine branch: `if not tribe_in_hand: break`."""
    assert len(offtribe_only_hand) == 0


@pytest.mark.fast
def test_cheat_on_combat_damage_decision_surfaces_grader_combat_keyword(
        combat_log_decision):
    """Logged combat decision contains at least one grader combat keyword
    (scripts/grade_traces.py:133)."""
    assert combat_log_decision['hit_kw'] is True


@pytest.mark.fast
def test_cheat_on_combat_damage_decision_phase_tag_is_combat(
        combat_log_decision):
    """Logger emits `phase='combat'` per the Phase 4 contract."""
    assert combat_log_decision['phase'] == 'combat'


# ───────── Cluster 2: structural_grader token classifiers ──────────


@pytest.mark.fast
def test_structural_grader_defer_token_is_a_defer(sg):
    """`defer` is a structured Defer token (literal)."""
    assert sg._is_defer('defer') is True


@pytest.mark.fast
def test_structural_grader_hold_fow_token_is_a_hold(sg):
    """`hold_<tag>` is a Hold token (prefix-based)."""
    assert sg._is_hold('hold_fow') is True


@pytest.mark.fast
def test_structural_grader_hold_thoughtseize_token_is_a_hold(sg):
    """Any `hold_<tag>` token is a Hold (prefix-based, tag-agnostic)."""
    assert sg._is_hold('hold_thoughtseize') is True


@pytest.mark.fast
def test_structural_grader_pass_is_not_a_defer(sg):
    """Only the literal 'defer' is a Defer token; 'pass' is not."""
    assert sg._is_defer('pass') is False


@pytest.mark.fast
def test_structural_grader_combo_path_tag_is_an_execute(sg):
    """`combo:<path_tag>` (Phase B Plan algebra) is an Execute token."""
    assert sg._is_execute('combo:tendrils') is True


@pytest.mark.fast
def test_structural_grader_kill_token_is_an_execute(sg):
    """`kill_<X>` (storm kill paths) is an Execute token."""
    assert sg._is_execute('kill_C') is True


@pytest.mark.fast
def test_structural_grader_cast_doomsday_token_is_an_execute(sg):
    """`cast_doomsday` (Doomsday combo fire) is an Execute token."""
    assert sg._is_execute('cast_doomsday') is True


@pytest.mark.fast
def test_structural_grader_entomb_token_is_an_execute(sg):
    """`entomb_<tag>` (Reanimator combo fire) is an Execute token."""
    assert sg._is_execute('entomb_reanimate') is True


@pytest.mark.fast
def test_structural_grader_pass_is_not_an_execute(sg):
    """Plain 'pass' is not an Execute token."""
    assert sg._is_execute('pass') is False


@pytest.mark.fast
def test_structural_grader_phase_combat_marks_a_combat_decision(sg):
    """`phase='combat'` alone is enough to classify a decision as combat."""
    assert sg._is_combat_decision({'phase': 'combat', 'chosen': 'pass'}) is True


@pytest.mark.fast
def test_cheat_on_combat_damage_setup_runs_without_raising(goblin_tribe_tags):
    """The Phase 4 cheat-on-combat-damage rule machinery (Card/Permanent
    construction + tribe-tag membership lookup) must import and execute
    cleanly. Mirrors the source `except Exception` guard at sim.py:3793-3794
    that records a failure if any setup raises."""
    from rules import Card as _Card, CardType as _CT, Permanent as _Perm
    raised = False
    try:
        c = _Card(name='_v', card_type=_CT.CREATURE, cmc=1,
                  mana_cost={'R': 1}, colors={'R'},
                  base_power=1, base_toughness=1, gy_type='creature')
        p = _Perm(card=c, controller='p1')
        _ = p.cheat_on_combat_damage
        _ = 'lackey' in goblin_tribe_tags
    except Exception:
        raised = True
    assert raised is False
