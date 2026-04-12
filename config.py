"""
config.py — Single source of truth for all card roles, matchup categories,
and tunable interaction parameters.

Design principles:
  - No tag string or matchup name appears more than ONCE across the codebase.
  - engine.py, interaction.py, gameplan.py import from here.
  - Tunable parameters are named constants — change here, propagates everywhere.
  - Card role sets use frozenset for O(1) membership testing.
"""
from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════
# CARD ROLE SETS  (tag → role mapping)
# ═══════════════════════════════════════════════════════════════════

class CardRoles:
    """Named frozensets of card tags grouped by strategic role."""

    # ── BUG's own cards ─────────────────────────────────────────────
    BUG_COUNTERS    = frozenset({'fow', 'fon', 'daze', 'fluster'})
    BUG_REMOVAL     = frozenset({'push', 'ad', 'dismember', 'snuff'})
    BUG_DISCARD     = frozenset({'ts', 'hymn'})
    BUG_THREATS     = frozenset({'tamiyo', 'goyf', 'nether', 'bowm', 'murk',
                                  'borrow', 'barrow', 'strix', 'kaito'})
    BUG_CANTRIPS    = frozenset({'bs', 'ponder', 'bauble'})
    OPP_CANTRIPS    = frozenset({'bs', 'ponder', 'pre', 'consider', 'bauble'})  # all cantrips opp may run
    BUG_GY_HATE     = frozenset({'surgical', 'endurance', 'leyline', 'nihil',
                                  'voidwalker', 'spellbomb'})
    BUG_FREE_SPELLS = frozenset({'fow', 'fon', 'fov', 'surgical', 'mindbreak',
                                  'snuff', 'endurance'})  # cast for free/alternate cost
    BUG_PITCH_BLUE  = frozenset({'fow', 'fon', 'bs', 'ponder', 'murk', 'borrow',
                                  'tamiyo', 'fluster', 'daze', 'bauble'})  # exileable as blue pitch

    # ── Opp combo pieces / win conditions ──────────────────────────
    COMBO_PIECES    = frozenset({'show', 'sneak', 'omni', 'dd', 'oops',
                                  'led', 'entomb', 'gris', 'itutor', 'gsz',
                                  'tendrils', 'pact', 'sat', 'labman', 'oracle',
                                  'archon', 'atraxa', 'emrakul', 'belcher',
                                  'necropotence', 'depths', 'marit', 'stage',
                                  'muxus', 'lackey', 'glistener', 'blighted'})

    # ── Lock pieces (halt BUG's ability to function) ───────────────
    MASS_REMOVAL    = frozenset({'terminus', 'wrath', 'verdict', 'massacre',
                                  'damnation', 'anger'})  # board wipes — HIGH threat

    LOCK_PIECES     = frozenset({'chalice', 'bridge', 'moon', 'b2b', 'trini',
                                  'karn', 'narset', 'leyline_opp', 'rip',
                                  'grafcage', 'sphereann'})

    # ── Permanent engines (if they stick, snowball fast) ──────────
    ENGINES         = frozenset({'vial', 'kaito', 'wst', 'sfm', 'loam',
                                  'crop', 'saga', 'workshop', 'cradle',
                                  'painter', 'grind'})  # painter+grind = Painter-Grindstone combo

    # ── Haste / immediate-impact creatures ────────────────────────
    HASTE_THREATS   = frozenset({'ragavan', 'drc', 'grief', 'fury',
                                  'solitude', 'endurance_opp'})

    # ── High-value CMC2 creatures (always worth hard countering) ──
    HIGH_VALUE_CMC2 = frozenset({'murk', 'sfm', 'solitude', 'karn', 'snap',
                                  'bowm', 'thalia', 'phelia', 'skyclave',
                                  'recruiter', 'eidolon', 'narset'})

    # ── Burn / direct damage noncreatures ─────────────────────────
    BURN_SPELLS     = frozenset({'bolt', 'pop', 'heat', 'lball', 'fireblast',
                                  'price', 'chain'})

    # ── Card advantage spells (not combos, but develop resources) ──
    CARD_ADVANTAGE  = frozenset({'ei', 'hymn', 'stock', 'bs_opp', 'ponder_opp',
                                  'consider', 'preordain'})

    # ── DnT / Boros specific must-counter creatures ───────────────
    DnT_MUST_COUNTER = frozenset({'solitude', 'sfm', 'vial', 'bowm', 'kaito', 'wst'})
    DnT_LOW_COST     = frozenset({'phelia', 'thalia', 'flickerwisp', 'skyclave', 'sfm',
                                   'orchid', 'eidolon', 'dungeoneer', 'bowm', 'minsc',
                                   'recruiter', 'mom'})  # Recruiter tutor + Vial deploy pool

    # ── Reanimator / GY targets ────────────────────────────────────
    GY_TARGETS      = frozenset({'gris', 'archon', 'atraxa', 'emrakul', 'tidespout',
                                  'elesh', 'jin', 'iona'})

    # ── Deathtouch permanents (blocks everything) ─────────────────
    DEATHTOUCH      = frozenset({'strix', 'barrow', 'bowm'})

    # ── Nonbasic land types BUG's Wasteland can target ─────────────
    NONBASIC_LANDS  = frozenset({'dual', 'fetch', 'tomb', 'cot', 'temple',
                                  'ulab', 'depths', 'stage', 'eye', 'nexus',
                                  'cradle', 'port', 'karakas', 'workshop'})

    # ── Eldrazi threat suite ───────────────────────────────────────
    ELDRAZI_THREATS = frozenset({'tks', 'fleshraker', 'linebreaker', 'battlemage',
                                  'reshaper', 'endless', 'smasher', 'mimic',
                                  'thought-knot', 'matter-reshaper'})

    # ── Storm / ritual enablers ───────────────────────────────────
    # ── Pact of Negation — only these spells are worth protecting with Pact ──
    PACT_PROTECTED  = frozenset({'sat', 'sneak', 'omni', 'gris'})  # OmniTell / Sneak Show

    RITUALS         = frozenset({'ritual', 'darkrit', 'cabalrit', 'petal',
                                  'seething', 'culling'})

    # ── Bowmasters synergy / graveyard hate creatures ─────────────
    BOWM_SYNERGY    = frozenset({'bowm', 'dauthi', 'carnage', 'braids'})  # Mono Black creature suite

    # ── BUG pitch-blue cards (can exile as FoW/FoN pitch cost) ────
    # Already defined above as BUG_PITCH_BLUE — alias for clarity
    BLUE_PITCHABLE  = frozenset({'fow', 'fon', 'bs', 'ponder', 'murk', 'borrow',
                                  'tamiyo', 'fluster', 'daze', 'bauble', 'brainstorm',
                                  'preordain', 'consider', 'veil'})

    # ── Specific 2-tag pairs (too small for their own set but still named) ──
    RITUAL_PAIR     = frozenset({'darkrit', 'cabalrit'})   # Cabal + Dark Ritual (used in Storm)
    EQUIPMENT_SET   = frozenset({'equipment', 'kaldra'})   # DnT equipment cards
    DnT_CMC3        = frozenset({'skyclave', 'solitude'})  # DnT high-priority CMC3 targets
    LAND_PAIR_BWDS  = frozenset({'tomb', 'cot'})           # Ancient Tomb / City of Traitors


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
    _BUILTIN_PRISON  = frozenset({'prison', 'dnt', 'boros'})
    _BUILTIN_GY      = frozenset({'reanimator', 'oops', 'doomsday'})
    _BUILTIN_LAND    = frozenset({'lands', 'show'})
    _BUILTIN_VIAL    = frozenset({'dnt', 'boros'})
    _BUILTIN_DIMIR   = frozenset({'dimir', 'dimir_b'})
    _BUILTIN_BOWM    = frozenset({'dimir', 'dimir_b', 'dimir_flash', 'ur_aggro',
                                   'mardu', 'mono_black', 'uwx'})
    _BUILTIN_FAST    = frozenset({'oops'})
    _BUILTIN_TRIBAL  = frozenset({'elves'})
    _BUILTIN_TEMPO   = frozenset({'dimir', 'dimir_b', 'dimir_flash'})

    # Merged sets: built-in + auto-discovered from deck_registry
    COMBO        = _BUILTIN_COMBO   | _registry_decks('combo')
    MIRROR       = _BUILTIN_MIRROR  | _registry_decks('mirror')
    TEMPO_MIRROR = _BUILTIN_TEMPO   | _registry_decks('tempo_mirror')
    AGGRO        = _BUILTIN_AGGRO   | _registry_decks('aggro')
    PRISON       = _BUILTIN_PRISON  | _registry_decks('prison')
    GY_COMBO     = _BUILTIN_GY      | _registry_decks('gy_combo')
    LAND_COMBO   = _BUILTIN_LAND    | _registry_decks('land_combo')
    VIAL_DECKS   = _BUILTIN_VIAL    | _registry_decks('vial_decks')
    DIMIR_ONLY   = _BUILTIN_DIMIR   | _registry_decks('dimir_only')
    BOWM_DECKS   = _BUILTIN_BOWM    | _registry_decks('bowm_decks')
    FAST_COMBO   = _BUILTIN_FAST    | _registry_decks('fast_combo')
    TRIBAL       = _BUILTIN_TRIBAL  | _registry_decks('tribal')

    # Utility predicates
    @staticmethod
    def is_combo(gs)    -> bool: return gs.matchup in MatchupCategory.COMBO
    @staticmethod
    def is_mirror(gs)   -> bool: return gs.matchup in MatchupCategory.MIRROR
    @staticmethod
    def is_aggro(gs)    -> bool: return gs.matchup in MatchupCategory.AGGRO
    @staticmethod
    def is_vial(gs)     -> bool: return gs.matchup in MatchupCategory.VIAL_DECKS
    @staticmethod
    def is_gy_combo(gs) -> bool: return gs.matchup in MatchupCategory.GY_COMBO
    @staticmethod
    def opp_has_bowm(gs)-> bool: return gs.matchup in MatchupCategory.BOWM_DECKS


MC = MatchupCategory  # short alias


# ═══════════════════════════════════════════════════════════════════
# INTERACTION PARAMETERS  (tunable)
# ═══════════════════════════════════════════════════════════════════

class InteractionParams:
    """Tunable thresholds for BUG's interaction decisions."""

    # Thoughtseize: how many turns to cast in each context
    TS_TURN_CAP_COMBO  = 3   # extend to T3 vs combo (strip LED, combo piece)
    TS_TURN_CAP_FAIR   = 2   # cap at T2 vs fair (preserve mana for threats)

    # FoW hand-depth gate: don't spend FoW when hand is thin (too depleting)
    FOW_HAND_GATE      = 3   # need 3+ cards to spend FoW freely
    FOW_HAND_GATE_DnT  = 2   # lower gate vs DnT/Boros — creature flood is urgent

    # FoW threshold for noncreature spells (threat level required)
    FOW_NONCREATURE_THRESHOLD = 3   # HIGH+ for noncreatures (FoN handles MEDIUM)

    # Daze: stop using past this turn (opp has enough mana to pay)
    DAZE_TURN_CAP      = 4   # use up to T4 in exceptional cases, T3 normally

    # Brainstorm: min threats in hand to hold without shuffle
    BS_HOLD_THRESHOLD  = 2   # hold blind BS if 2+ threats in hand

    # Bowmasters: hold in mirror when opp has this many cantrips in hand
    BOWM_HOLD_MIRROR   = 1   # hold if opp has ≥1 cantrip

    # Push pre-filter: max CMC handled by removal (pre-engine shortcut)
    PUSH_PREFILTER_CMC = 2   # handle CMC≤2 with Push; CMC3+ → engine

    # Flood-risk gate: back off deploying 2nd threat when opp has this much mana
    FLOOD_RISK_MANA    = 3   # opp has 3+ mana + FoW → hold 2nd threat

    # Life total triggers
    CRITICAL_LIFE      = 6   # below this, lower all thresholds (desperate)

    # Murktide: min graveyard spells to cast
    MURKTIDE_DELVE_MIN = 4


# ═══════════════════════════════════════════════════════════════════
# THREAT CONFIG  (drives classify_threat in interaction.py)
# ═══════════════════════════════════════════════════════════════════

class ThreatConfig:
    """
    Data-driven threat classification.
    Maps tag → base ThreatLevel (can be overridden by matchup context).
    """

    # ThreatLevel constants (mirrors interaction.py)
    MUST   = 4
    HIGH   = 3
    MEDIUM = 2
    LOW    = 1

    # Per-tag overrides: {tag: level}
    # Tags not listed fall through to type-based defaults
    TAG_LEVELS = {
        # Must-answer combo
        'show':   MUST, 'sneak': MUST, 'omni':  MUST, 'dd':     MUST,
        'oops':   MUST, 'led':   MUST, 'entomb':MUST, 'gris':   MUST,
        'itutor': MUST, 'gsz':   MUST, 'tendrils':MUST,'pact':  MUST,
        'sat':    MUST, 'labman':MUST, 'oracle':MUST, 'marit':  MUST,

        # Lock pieces / engines — always HIGH
        'vial':    HIGH, 'chalice': HIGH, 'bridge': HIGH, 'moon':   HIGH,
        'b2b':     HIGH, 'trini':   HIGH, 'karn':   HIGH, 'narset': HIGH,
        'kaito':   HIGH, 'sfm':     HIGH, 'wst':    HIGH, 'loam':   HIGH,
        'crop':    HIGH, 'saga':    HIGH,

        # High-value creatures
        'ragavan': HIGH, 'drc':  HIGH, 'grief':  HIGH, 'fury':   HIGH,
        'bowm':    HIGH, 'thalia':HIGH,'phelia': HIGH, 'skyclave':HIGH,
        'solitude':HIGH, 'eidolon':HIGH,'recruiter':HIGH,'snap': HIGH,

        # Burn / damage (MEDIUM — Daze/Fluster should stop)
        'bolt':   MEDIUM, 'pop':  MEDIUM, 'heat':  MEDIUM, 'lball': MEDIUM,
        'price':  MEDIUM, 'chain':MEDIUM,

        # Card advantage (MEDIUM)
        'ei': MEDIUM, 'hymn': MEDIUM, 'stock': MEDIUM,

        # Targeted removal — MEDIUM: worth Dazing but not FoWing
        'stp': 2, 'path': 2,   # Swords to Plowshares, Path to Exile

        # Mass removal — HIGH threat (wipes BUG's entire board)
        'terminus': 3, 'wrath': 3, 'verdict': 3,
        'massacre': 3, 'damnation': 3, 'anger': 3,

        # New archetypes — combo pieces
        'belcher': MUST, 'stage': MUST, 'glistener': MUST, 'blighted': MUST,
        'muxus': MUST, 'lackey': HIGH, 'guide': HIGH, 'swiftspear': HIGH,
        'reclaimer': HIGH, 'invigorate': HIGH, 'berserk': HIGH,
        'fireblast': MEDIUM, 'spike': MEDIUM, 'delver': HIGH,

        # Low — cantrips / rituals / misc
        'bs':  LOW, 'ponder': LOW, 'preordain': LOW, 'consider': LOW,
        'dr':  LOW, 'ritual': LOW, 'petal':     LOW, 'bauble':   LOW,
    }

    @classmethod
    def base_level(cls, tag: str) -> int:
        """Return configured threat level for a tag, or None if not configured."""
        return cls.TAG_LEVELS.get(tag)


# ═══════════════════════════════════════════════════════════════════
# SIDEBOARD ROLE TAGS
# ═══════════════════════════════════════════════════════════════════

class SBRoles:
    """Tags of sideboard cards grouped by what they answer."""

    GY_HATE   = frozenset({'leyline', 'surgical', 'endurance', 'nihil',
                            'spellbomb', 'voidwalker'})
    ART_HATE  = frozenset({'fov', 'meltdown', 'ee'})
    SWEEPERS  = frozenset({'deluge', 'ppath', 'wrath', 'verdict'})
    COMBO_COUNTER = frozenset({'mindbreak', 'fluster', 'pyroblast'})
    MIRROR    = frozenset({'pyro', 'vos', 'deluge'})


# ═══════════════════════════════════════════════════════════════════
# GAME RULES  (immutable constants from MTG Comprehensive Rules)
# ═══════════════════════════════════════════════════════════════════

class GameRules:
    """Game-wide constants from the MTG Comprehensive Rules."""
    MAX_TURNS = 15             # simulation turn limit
    STARTING_LIFE = 20         # CR 103.4
    MAX_MULLIGANS = 3          # London mulligan: 0-3 mulligans
    FORCED_KEEP_SIZE = 4       # auto-keep at 4 cards remaining
    BO3_WINS_NEEDED = 2        # best-of-3 match
    BO3_MAX_GAMES = 3


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


# ═══════════════════════════════════════════════════════════════════
# COUNTER LOGIC  (tunable decision parameters)
# ═══════════════════════════════════════════════════════════════════

class CounterLogic:
    """Parameters for try_reactive_counter spell evaluation."""
    COUNTER_TAGS = frozenset({'fow', 'fon', 'daze', 'consign', 'counter',
                               'fluster', 'pyro', 'reb'})
    NEVER_COUNTER_TAGS = frozenset({'bs', 'ponder', 'bauble'})  # cantrips — not worth a counter
    MINOR_THREAT_TAGS = frozenset({'tamiyo', 'borrow'})          # low CMC, expendable
    TEMPO_THREAT_TAGS = frozenset({'drc', 'cutter', 'ragavan', 'delver'})
    INFECT_PUMP_TAGS = frozenset({'invigorate', 'mutagenic', 'berserk', 'vines', 'defense'})
    BURN_TAGS = frozenset({'bolt', 'pop', 'chain', 'spike', 'fireblast', 'rift',
                            'blaze', 'skullcrack', 'heat', 'lball', 'price'})
    DAZE_PAY_PROB_COMBO = 0.55   # probability combo opponent pays for Daze
    DAZE_PAY_PROB_FAIR = 0.30    # probability fair opponent pays for Daze
    BURN_DAMAGE_DEFAULT = 3      # default damage for a burn spell


# ═══════════════════════════════════════════════════════════════════
# MULLIGAN SCORING  (tunable card evaluation weights)
# ═══════════════════════════════════════════════════════════════════

class MulliganScoring:
    """Card-keep priority weights for London mulligan best-N selection."""
    SCORE_FOW_FON = 5        # Force of Will / Force of Negation
    SCORE_CREATURE = 4       # any creature
    SCORE_CANTRIP = 3        # Brainstorm, Ponder
    SCORE_REMOVAL = 3        # Thoughtseize, Push, Abrupt Decay
    SCORE_SOFT_COUNTER = 2   # Daze, Flusterstorm
    SCORE_LAND = 3           # any land
    SCORE_OTHER = 1          # everything else


# Convenience: export everything at module level
CR = CardRoles
IP = InteractionParams
TC = ThreatConfig
SB = SBRoles
GR = GameRules
CT = CombatThresholds
CL = CounterLogic
MS = MulliganScoring
