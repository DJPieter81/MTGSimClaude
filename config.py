"""
config.py — Single source of truth for all card roles, matchup categories,
and tunable interaction parameters.

Design principles:
  - No tag string or matchup name appears more than ONCE across the codebase.
  - engine.py, interaction.py, gameplan.py import from here.
  - Tunable parameters are named constants — change here, propagates everywhere.
  - Card role sets use frozenset for O(1) membership testing.

Some tunable thresholds are data-driven: their canonical value lives in
`config/calibration.json`, produced by tools/calibrate_bhi_threshold.py
(Phase D of the post-Phase-6 re-architecture). When that file is
missing or unreadable, the hardcoded fallback in the class definition
applies.
"""
from __future__ import annotations

import json as _json
import os as _os


def _load_calibrated(name: str, fallback):
    """Read `name` from config/calibration.json, else return fallback.

    Loads `values` dict from the JSON file next to this module. Quiet
    fallback on FileNotFoundError or JSONDecodeError so a fresh checkout
    works before the calibration file is committed.
    """
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                         'config', 'calibration.json')
    try:
        with open(path) as f:
            data = _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError, OSError):
        return fallback
    return data.get('values', {}).get(name, fallback)


# ═══════════════════════════════════════════════════════════════════
# CARD ROLE SETS  (tag → role mapping)
# ═══════════════════════════════════════════════════════════════════

class CardRoles:
    """Named frozensets of card tags grouped by strategic role.

    Most CardRoles entries were retired in the dead-constants sweep —
    deck-specific card knowledge now lives in `decks/<key>.py` plugin
    modules (per CLAUDE.md ABSTRACTION CONTRACT). Only the cross-deck
    tag sets that engine.py still consults are kept here.
    """

    # ── DnT / Boros equipment cards (engine.py:2539 finds equipment in library) ──
    EQUIPMENT_SET   = frozenset({'equipment', 'kaldra'})


# ═══════════════════════════════════════════════════════════════════
# MATCHUP CATEGORIES
# ═══════════════════════════════════════════════════════════════════

def _registry_decks(category):
    """Get deck keys from deck_registry that declare a given category."""
    try:
        from deck_registry import get_decks_in_category
        return get_decks_in_category(category)
    except ImportError:
        return frozenset()


class MatchupCategory:
    """Named sets of matchup IDs by strategic category.

    Built-in decks are hardcoded here. Plugin decks auto-register via
    DECK_META categories in their modules — no manual edits needed.
    """

    # Built-in (cards.py) deck sets — these don't have DECK_META
    _BUILTIN_COMBO   = frozenset({'storm', 'oops', 'doomsday', 'reanimator', 'show'})
    _BUILTIN_MIRROR  = frozenset({'dimir', 'dimir_b', 'dimir_flash', 'uwx'})
    _BUILTIN_AGGRO   = frozenset({'boros', 'ur_aggro', 'mardu', 'mono_black', 'eldrazi', 'burn'})
    _BUILTIN_VIAL    = frozenset({'dnt', 'boros'})
    _BUILTIN_TEMPO   = frozenset({'dimir', 'dimir_b', 'dimir_flash'})
    # Decks running the Affinity / 8-Cast artifact-storm shell.  Used to gate
    # land-pick priority for Urza's Saga / Seat of the Synod.
    _BUILTIN_ARTIFACT = frozenset({'affinity', 'eight_cast'})
    # Decks running the Dark Depths + Thespian's Stage land combo.  Used to
    # gate `_pick_land`'s combo-piece priority hook.  NOTE: this is a *combo
    # mechanic* category, distinct from `_BUILTIN_LAND` which marks decks
    # whose primary plan revolves around lands (Lands runs the Loam engine,
    # Show ramps via Show and Tell — neither runs the Depths combo).
    _BUILTIN_DEPTHS_COMBO = frozenset({'lands', 'depths'})
    # Decks where the shared `_execute_turn` Thoughtseize step would silently
    # eat the T1-T2 combo mana.  Reanimator is the canonical case; other
    # ritual-into-reanimate plans would join this set.
    _BUILTIN_TS_DEFER = frozenset({'reanimator'})

    # Merged sets: built-in + auto-discovered from deck_registry
    COMBO         = _BUILTIN_COMBO   | _registry_decks('combo')
    MIRROR        = _BUILTIN_MIRROR  | _registry_decks('mirror')
    TEMPO_MIRROR  = _BUILTIN_TEMPO   | _registry_decks('tempo_mirror')
    AGGRO         = _BUILTIN_AGGRO   | _registry_decks('aggro')
    VIAL_DECKS    = _BUILTIN_VIAL    | _registry_decks('vial_decks')
    ARTIFACT      = _BUILTIN_ARTIFACT       | _registry_decks('artifact')
    DEPTHS_COMBO  = _BUILTIN_DEPTHS_COMBO   | _registry_decks('depths_combo')
    TS_DEFER      = _BUILTIN_TS_DEFER       | _registry_decks('ts_defer')

    # Utility predicates — only those with external callers are retained.
    @staticmethod
    def is_combo(gs)  -> bool: return gs.matchup in MatchupCategory.COMBO
    @staticmethod
    def is_mirror(gs) -> bool: return gs.matchup in MatchupCategory.MIRROR
    @staticmethod
    def is_aggro(gs)  -> bool: return gs.matchup in MatchupCategory.AGGRO
    @staticmethod
    def is_vial(gs)   -> bool: return gs.matchup in MatchupCategory.VIAL_DECKS


MC = MatchupCategory  # short alias


# ═══════════════════════════════════════════════════════════════════
# INTERACTION PARAMETERS  (tunable)
# ═══════════════════════════════════════════════════════════════════

class InteractionParams:
    """Tunable thresholds for BUG's interaction decisions."""

    # Thoughtseize: how many turns to cast in each context
    TS_TURN_CAP_COMBO  = 3   # extend to T3 vs combo (strip LED, combo piece)
    TS_TURN_CAP_FAIR   = 2   # cap at T2 vs fair (preserve mana for threats)

    # Bowmasters: hold in mirror when opp has this many cantrips in hand
    BOWM_HOLD_MIRROR   = 1   # hold if opp has ≥1 cantrip

    # Flood-risk gate: back off deploying 2nd threat when opp has this much mana
    FLOOD_RISK_MANA    = 3   # opp has 3+ mana + FoW → hold 2nd threat

    # Murktide: min graveyard spells to cast
    MURKTIDE_DELVE_MIN = 4

    # BHI (Bayesian Hand Inference) thresholds — HandBelief probabilities above
    # which strategies should treat opponent as holding specific threats.
    # Used by _strategy_storm, _strategy_oops, _strategy_doomsday combo gates.
    # The free-counter threshold is calibrated via the regression-sweep
    # harness — see config/calibration.json + tools/calibrate_bhi_threshold.py
    # (Phase D of docs/design/2026-05-15_post-phase-6-re-architecture.md).
    # Hardcoded fallback (0.40) applies when the calibration JSON is
    # missing or unreadable.
    BHI_FREE_COUNTER_THRESHOLD = _load_calibrated('BHI_FREE_COUNTER_THRESHOLD', 0.40)
    # `BHI_COUNTER_THRESHOLD` calibrated via tools/calibrate_bhi_counter_threshold.py
    # — see config/calibration.json `values` dict. Hardcoded fallback (0.55)
    # applies when the JSON file is missing or unreadable. Governs the
    # "any counter in hand" probability cutoff (`belief.p_counter`).
    BHI_COUNTER_THRESHOLD      = _load_calibrated('BHI_COUNTER_THRESHOLD', 0.55)


# ═══════════════════════════════════════════════════════════════════
# THREAT LEVELS  (single source of truth — re-exported from interaction.py)
# ═══════════════════════════════════════════════════════════════════

class ThreatLevel:
    """Categorical threat severity used by classify_threat() and the
    counter/removal priority logic. Defined here so config-layer modules
    (ThreatConfig, ClockDelta) can reference the same integers without
    importing interaction.py and creating a circular dependency."""
    MUST_ANSWER_NOW = 4   # combo / win-con — resolve = likely lose
    HIGH            = 3   # engine / lock / haste — permanent advantage
    MEDIUM          = 2   # fair threat answerable next turn
    LOW             = 1   # cantrip / ritual / minor spell


# ═══════════════════════════════════════════════════════════════════
# GAME RULES  (immutable constants from MTG Comprehensive Rules)
# ═══════════════════════════════════════════════════════════════════

class GameRules:
    """Game-wide constants from the MTG Comprehensive Rules."""
    MAX_TURNS = 15             # simulation turn limit
    STARTING_LIFE = 20         # CR 103.4
    MAX_MULLIGANS = 3          # London mulligan: 0-3 mulligans
    FORCED_KEEP_SIZE = 4       # auto-keep at 4 cards remaining


# ═══════════════════════════════════════════════════════════════════
# COMBAT & LIFE THRESHOLDS  (tunable)
# ═══════════════════════════════════════════════════════════════════

class CombatThresholds:
    """Life-based decision thresholds for combat and removal."""
    DESPERATE_LIFE = 8                                    # attack with everything below this
    HOLD_ATTACK_TAGS = frozenset({'bowm', 'tamiyo'})      # creatures held back from default attacks
    STP_THRESHOLD_AGGRO = 1                               # exile any creature vs aggro
    STP_THRESHOLD_FAIR = 2                                # exile power >= 2 vs fair
    SNUFF_LIFE_BUFFER = 8                                 # need > 8 life to cast Snuff Out
    SNUFF_LIFE_FLOOR_AGGRO = 6                            # need > 6 life to Snuff vs aggro
    BURN_COUNTER_LIFE = 12                                # counter burn at <= 12 life (was 7 — POP went uncountered)
    # Chump-block sparing: only chump if we have at least N spare blockers.
    # Threshold drops by 1 when defender's life ≤ atk.power * MULTIPLIER
    # (close to lethal — chump aggressively).
    CHUMP_DESPERATE_LIFE_MULTIPLIER = 2
    CHUMP_SPARE_DESPERATE = 1
    CHUMP_SPARE_NORMAL    = 2


# ═══════════════════════════════════════════════════════════════════
# COUNTER LOGIC  (tunable decision parameters)
# ═══════════════════════════════════════════════════════════════════

class CounterLogic:
    """Parameters for try_reactive_counter spell evaluation."""
    COUNTER_TAGS = frozenset({'fow', 'fon', 'daze', 'consign', 'counter',
                               'fluster', 'pyro', 'reb'})
    NEVER_COUNTER_TAGS = frozenset({'bs', 'ponder', 'bauble'})  # cantrips — not worth a counter
    BURN_TAGS = frozenset({'bolt', 'pop', 'chain', 'spike', 'fireblast', 'rift',
                            'blaze', 'skullcrack', 'heat', 'lball', 'price'})
    DAZE_PAY_PROB_COMBO = 0.55   # probability combo opponent pays for Daze
    BURN_DAMAGE_DEFAULT = 3      # default damage for a burn spell

    # Turn-indexed Daze pay probability (caster's perspective). Two columns:
    # SPARE  — caster has at least 1 mana left after casting the spell
    # TAPPED — caster has zero spare mana (must pull a mana source from somewhere)
    # T2 row is also used for any earlier turn (T1 should rarely happen but
    # is treated identically to T2). T4_* covers T4 and later.
    DAZE_PAY_PROB_T2_SPARE  = 0.15
    DAZE_PAY_PROB_T2_TAPPED = 0.10
    DAZE_PAY_PROB_T3_SPARE  = 0.50
    DAZE_PAY_PROB_T3_TAPPED = 0.20
    DAZE_PAY_PROB_T4_SPARE  = 0.85
    DAZE_PAY_PROB_T4_TAPPED = 0.45

    # FoW gate for "minor" threats (e.g. tamiyo, borrow): only spend a
    # counter on these when total counters in hand is strictly above this
    # floor — preserves stack depth for must-answer spells.
    FOW_MINOR_THREAT_COUNTER_FLOOR = 2

    # Flusterstorm follow-up: probability that Fluster is cast as a bridge
    # over a previously-resolved counter (FoW/FoN/Daze) when no opponent
    # backup is visible.
    FLUSTERSTORM_FIZZLE_PROB = 0.65


# ═══════════════════════════════════════════════════════════════════
# TIMEOUT SCORING  (board-state tiebreak when sim hits MAX_TURNS)
# ═══════════════════════════════════════════════════════════════════

class TimeoutScoring:
    """Weights for the board-state tiebreak used at simulation timeout.

    Score per side = power*POWER + creatures*CREATURE_COUNT
                   + lands*LAND + max(0, life - opp_life)
    Higher score wins. life_delta has implicit weight 1.
    """
    POWER_WEIGHT          = 2
    CREATURE_COUNT_WEIGHT = 3
    LAND_WEIGHT           = 1


# ═══════════════════════════════════════════════════════════════════
# DISCARD-TARGET PRIORITY  (Thoughtseize / Hymn / Cabal Therapy)
# ═══════════════════════════════════════════════════════════════════

class TSTargetPriority:
    """Priority weights for proactive discard targeting. Higher = strip first.

    All entries are role-based (win_condition, lock_piece, engine, …) — no
    card-name knowledge. Branch order matters in interaction.best_proactive_target;
    these constants set the magnitudes only."""
    WIN_CONDITION       = 100
    COMBO_PIECE         =  90
    MIRROR_DRAW_TRIGGER =  85   # draw-punisher in mirrors
    LOCK_PIECE          =  80
    ENGINE              =  70
    FREE_COUNTER        =  65   # CMC>=3 free-cast-if-blue
    MIRROR_FREE_CAST    =  60   # cheaper free-cast in mirror only
    HASTE_CREATURE      =  60
    HIGH_CMC_CREATURE   =  50   # CMC >= 4
    MID_CMC_CREATURE    =  40   # CMC >= 2
    REMOVAL             =  30
    RITUAL              =  25   # mana ritual — delays combo
    BASELINE            =  10   # cantrips / misc nonland


# ═══════════════════════════════════════════════════════════════════
# CLOCK DELTA  (numeric translation of ThreatLevel for clock.py-style scoring)
# ═══════════════════════════════════════════════════════════════════

class ClockDelta:
    """Threat-level → clock-delta (turns). Negative means the threat
    actually buys time (cantrip-class). Used by threat_level_to_clock_delta
    in interaction.py."""
    MUST_ANSWER_NOW =  3.5
    HIGH            =  1.2
    MEDIUM          =  0.3
    LOW             = -0.1


# ═══════════════════════════════════════════════════════════════════
# RACING / BOARD-STATE THRESHOLDS  (engine.evaluate_position)
# ═══════════════════════════════════════════════════════════════════

class RaceThresholds:
    """Cutoffs for the 'racing / ahead / behind / parity' classification.

    TTK_RACE     — both ttk and ttd ≤ this many turns → 'racing'
    BOARD_POWER_GAP — board_power exceeds opp_power by *more than* this → 'ahead'
    THREAT_GAP   — creature count exceeds opp's by *more than* this → 'ahead'
    """
    TTK_RACE        = 3
    BOARD_POWER_GAP = 2
    THREAT_GAP      = 1


# ═══════════════════════════════════════════════════════════════════
# WASTELAND TARGET PRIORITY  (engine._wl_priority + _wl_pri)
# ═══════════════════════════════════════════════════════════════════

class WastelandPriority:
    """Per-target weights for Wasteland targeting.

    Higher score wins. Used for both BUG's Wasteland (vs combo lands /
    colour-cuts) and the symmetric opponent path. Weights are additive — a
    Dark Depths that also produces a needed colour scores
    COMBO_LAND_WEIGHT + COLOUR_CUT_WEIGHT.
    """
    COMBO_LAND_WEIGHT       = 50  # Dark Depths / Thespian's Stage
    COLOUR_CUT_WEIGHT       = 10  # cuts a colour the opponent needs now
    MANA_RITUAL_LAND_WEIGHT = 5   # Ancient Tomb / City of Traitors
    DUAL_LAND_WEIGHT        = 3   # duals are the hardest to replace
    FETCH_WEIGHT            = 2   # denies future colour fixing


# ═══════════════════════════════════════════════════════════════════
# BURN FACE-LETHAL THRESHOLDS  (engine Mardu/Boros bolt-face plan)
# ═══════════════════════════════════════════════════════════════════

class BurnLethal:
    """Life thresholds at which to point Bolt-class burn at the opponent's
    face (instead of a creature).

    VS_BURN — vs a Burn opponent: race, go-face whenever opp.life ≤ this
    DEFAULT — vs anyone else: go-face when board damage + bolts can finish
    """
    VS_BURN = 17
    DEFAULT = 9


# ═══════════════════════════════════════════════════════════════════
# ELVES SUBROUTINE THRESHOLDS  (decks/elves dispatch via engine)
# ═══════════════════════════════════════════════════════════════════

class Elves:
    """Tribal thresholds for the Elves strategy."""
    # Heritage Druid taps three elves for {GGG}; deploy mana elves until
    # the on-board elf count reaches this number.
    HERITAGE_TARGET_ELVES = 3


# ═══════════════════════════════════════════════════════════════════
# MULLIGAN-TIME TS PRIORITY  (sim._ts_priority — additive scale)
# ═══════════════════════════════════════════════════════════════════

class MulliganTSPriority:
    """Priority weights for the mulligan-time Thoughtseize evaluator
    (`sim._ts_priority`).

    Distinct from `TSTargetPriority` (which uses a 10/100 scale for the
    proactive in-game discard logic). These weights are additive with the
    target's CMC and creature base_power, so they live on a smaller scale.
    """
    WIN_CONDITION = 10
    COMBO_PIECE   = 8
    COUNTER       = 6   # tag in {fow, fon, daze, fluster}
    CREATURE_BASE = 3   # added to base_power for any creature


# Convenience: export everything at module level
CR = CardRoles
IP = InteractionParams
GR = GameRules
CT = CombatThresholds
CL = CounterLogic
TS = TSTargetPriority
TSC = TimeoutScoring
CD = ClockDelta
RT = RaceThresholds
WP = WastelandPriority
BL = BurnLethal
EL = Elves
MTSP = MulliganTSPriority
