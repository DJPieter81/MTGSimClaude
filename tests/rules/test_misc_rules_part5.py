"""Misc rules part 5 — migrated from sim.py:3143-3218.

Covers:
- Phase 0 lifted-constant invariants (Daze pay-prob monotonicity, chump-spare
  delta, Flusterstorm fizzle range, FoW minor-threat floor, Heritage Druid
  target count, mulligan TS priority ordering).
- Phase 1 combo_engine architecture invariants (StrategicLogger.dump()
  round-trip parser shape, removal of log_combo_decision, abstraction
  contract for combo_engine.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config import (
    CombatThresholds as CT,
    CounterLogic as CL,
    Elves as EL,
    MulliganTSPriority as MTSP,
)


# ── Phase 0: lifted-constant mechanical invariants ──────────────────────


@pytest.mark.fast
def test_daze_pay_prob_monotone_in_turn_spare_column():
    assert CL.DAZE_PAY_PROB_T2_SPARE <= CL.DAZE_PAY_PROB_T3_SPARE <= CL.DAZE_PAY_PROB_T4_SPARE


@pytest.mark.fast
def test_daze_pay_prob_monotone_in_turn_tapped_column():
    assert CL.DAZE_PAY_PROB_T2_TAPPED <= CL.DAZE_PAY_PROB_T3_TAPPED <= CL.DAZE_PAY_PROB_T4_TAPPED


@pytest.mark.fast
def test_daze_pay_prob_spare_dominates_tapped_every_turn():
    assert (
        CL.DAZE_PAY_PROB_T2_SPARE >= CL.DAZE_PAY_PROB_T2_TAPPED
        and CL.DAZE_PAY_PROB_T3_SPARE >= CL.DAZE_PAY_PROB_T3_TAPPED
        and CL.DAZE_PAY_PROB_T4_SPARE >= CL.DAZE_PAY_PROB_T4_TAPPED
    )


@pytest.mark.fast
def test_chump_spare_drops_by_one_near_lethal():
    assert CT.CHUMP_SPARE_NORMAL - CT.CHUMP_SPARE_DESPERATE == 1


@pytest.mark.fast
def test_fow_minor_threat_counter_floor_is_non_negative():
    assert CL.FOW_MINOR_THREAT_COUNTER_FLOOR >= 0


@pytest.mark.fast
def test_heritage_druid_target_elf_count_matches_activation_cost():
    assert EL.HERITAGE_TARGET_ELVES == 3


@pytest.mark.fast
def test_flusterstorm_fizzle_probability_is_valid_probability():
    assert 0.0 < CL.FLUSTERSTORM_FIZZLE_PROB <= 1.0


@pytest.mark.fast
def test_mulligan_ts_priority_ordering_win_combo_counter_creature():
    assert (
        MTSP.WIN_CONDITION > MTSP.COMBO_PIECE > MTSP.COUNTER > MTSP.CREATURE_BASE
    )


# ── Phase 1: combo_engine architecture invariants ───────────────────────


@pytest.fixture(scope='module')
def _parsed_decision_line():
    """Round-trip a synthetic StrategicLogger decision through dump() and
    parse it with the shape llm_judge.collect() relies on."""
    from strategic_logger import StrategicLogger

    sl = StrategicLogger(enabled=True)
    sl.log_decision(
        turn=4,
        deck='storm',
        candidates=['kill_C', 'pass'],
        chosen='kill_C',
        reason='ritual chain → tendrils for lethal',
        phase='combo',
    )
    line = sl.dump()[0]
    hdr, rest = line.split(' chose ', 1)
    action, why = rest.split(' — ', 1)
    chosen_field = action.split(' from ', 1)[0].strip()
    phase_field = hdr.split('[phase:', 1)[1].split(']')[0]
    deck_field = hdr.split('[', 1)[1].split(']')[0]
    turn_field = int(hdr.split()[0].lstrip('T'))
    return {
        'deck': deck_field,
        'phase': phase_field,
        'turn': turn_field,
        'chosen': chosen_field,
        'why': why,
    }


@pytest.mark.fast
def test_strat_log_dump_round_trip_parsed_deck(_parsed_decision_line):
    assert _parsed_decision_line['deck'] == 'storm'


@pytest.mark.fast
def test_strat_log_dump_round_trip_parsed_phase(_parsed_decision_line):
    assert _parsed_decision_line['phase'] == 'combo'


@pytest.mark.fast
def test_strat_log_dump_round_trip_parsed_turn(_parsed_decision_line):
    assert _parsed_decision_line['turn'] == 4


@pytest.mark.fast
def test_strat_log_dump_round_trip_parsed_chosen(_parsed_decision_line):
    assert _parsed_decision_line['chosen'] == 'kill_C'


@pytest.mark.fast
def test_strat_log_dump_round_trip_reason_contains_keyword():
    """Phase A unified parser must preserve the reason text verbatim."""
    from strategic_logger import StrategicLogger

    sl = StrategicLogger(enabled=True)
    sl.log_decision(
        turn=4,
        deck='storm',
        candidates=['kill_C', 'pass'],
        chosen='kill_C',
        reason='ritual chain → tendrils for lethal',
        phase='combo',
    )
    line = sl.dump()[0]
    _hdr, rest = line.split(' chose ', 1)
    _action, why = rest.split(' — ', 1)
    assert ('tendrils' in why) is True


@pytest.mark.fast
def test_phase_a_invariant_log_combo_decision_removed():
    """Phase A retired combo_engine.log_combo_decision; canonical emitter is
    StrategicLogger.log_decision. This test catches re-introduction."""
    import combo_engine

    assert hasattr(combo_engine, 'log_combo_decision') is False


@pytest.mark.fast
def test_combo_engine_source_owns_zero_card_name_equality_literals():
    """ABSTRACTION CONTRACT: combo_engine.py must contain zero card-name
    equality literals (regex catches re-introduction)."""  # abstraction-allow: rules-test
    import re

    import combo_engine

    src_path = Path(combo_engine.__file__).resolve()
    src = src_path.read_text()
    bad = re.findall(r'\.name\s*==\s*[\'"]', src)
    assert len(bad) == 0
