"""
interaction_model.py — Compute interaction rates from deck properties.

Instead of magic numbers (0.75, 0.62, etc.), rates are derived from
game-meaningful properties each deck declares in DECK_META['interaction'].

Properties:
    speed (1-5):       How fast the deck's primary game plan executes.
                       1 = T1-2 kill (Belcher, Oops)
                       2 = T2-3 kill (Infect, Depths, TES)
                       3 = T3-4 threat (Sneak & Show, Storm, Reanimator)
                       4 = T4-5 grind (8-Cast, Cloudpost, Eldrazi)
                       5 = T5+ long game (Lands, Prison, UWx)

    resilience (1-5):  How well the deck recovers after BUG answers its plan.
                       1 = all-in, folds to 1 answer (Belcher, Oops)
                       2 = light redundancy (Depths, Infect)
                       3 = moderate recovery (Storm, TES, Reanimator)
                       4 = good recovery (Sneak, 8-Cast, Dimir mirrors)
                       5 = inevitability (Lands, Cloudpost, UWx)

    uses_graveyard:    True if combo relies on GY (vulnerable to Surgical/Leyline)
    uses_veil:         True if deck runs Veil of Summer (blanks blue counters)
    soft_to_wasteland: True if deck relies on specific lands (vulnerable to Wasteland)
    creature_based:    True if primary game plan is creature combat

Computed outputs:
    bug_save_rate:     P(BUG has the right sideboard answer when OPP would win)
    opp_save_rate:     P(OPP recovers when BUG would win)
    fow_threshold:     CMC below which BUG won't FoW (saves for bigger threats)
    combo_fizzle:      P(combo fizzles even when it resolves, due to hate)
    veil_kill_rate:    P(Veil + combo = lethal, given BUG has no non-blue answers)
"""


def compute_bug_save_rate(interaction):
    """
    How likely BUG stabilizes when OPP would otherwise win.

    Slower decks give BUG more turns to find answers (0.12 per speed level).
    GY-based combos are vulnerable to Surgical Extraction (+0.10).
    Wasteland-soft decks fold to BUG's 4x Wasteland (+0.08).
    Creature-based decks are answerable by Fatal Push/removal (+0.06).
    """
    speed = interaction.get('speed', 3)
    uses_gy = interaction.get('uses_graveyard', False)
    soft_wl = interaction.get('soft_to_wasteland', False)
    creature = interaction.get('creature_based', False)

    rate = 0.20                          # base: BUG always has some chance
    rate += (speed - 1) * 0.14           # slower = more time to find answers
    rate += 0.12 if uses_gy else 0.0     # Surgical / Leyline
    rate += 0.10 if soft_wl else 0.0     # Wasteland
    rate += 0.08 if creature else 0.0    # Fatal Push / removal
    return max(0.0, min(rate, 0.85))     # clamp 0-85%


def compute_opp_save_rate(interaction):
    """
    How likely OPP recovers when BUG would otherwise win.

    Resilient decks can rebuild after BUG's disruption (0.10 per level).
    Fast decks that get slowed can sometimes re-establish (speed bonus).
    """
    resilience = interaction.get('resilience', 3)
    speed = interaction.get('speed', 3)

    rate = 0.0                           # base: BUG's win is usually real
    rate += (resilience - 2) * 0.15      # only resilience 3+ gives comeback chance
    rate += max(0, 3 - speed) * 0.08     # very fast decks sometimes re-combo
    return max(0.0, min(rate, 0.70))     # floor 0, cap 70%


def compute_combo_fizzle_rate(interaction, veil_active=False):
    """
    P(combo fizzles even after resolving, due to BUG's sideboard hate).

    GY combos fizzle to Surgical/Leyline (15% base).
    Veil reduces fizzle (opponent can't interact with blue spells).
    """
    uses_gy = interaction.get('uses_graveyard', False)

    base = 0.15 if uses_gy else 0.05     # GY combos more vulnerable
    if veil_active:
        base *= 0.4                       # Veil blocks most interaction
    return base


def compute_veil_kill_rate(interaction):
    """
    P(Veil + combo = lethal) for storm/combo decks.

    Derived from speed and resilience: fast combos with Veil are very likely
    to kill since BUG's only answers are blue (which Veil blanks).
    """
    if not interaction.get('uses_veil', False):
        return 0.0

    speed = interaction.get('speed', 3)
    # Faster combo + Veil = higher kill rate
    # Speed 1-2: 75-85% kill (very fast, Veil blanks FoW)
    # Speed 3: 60-65% kill (moderate, BUG may have non-blue answers)
    # Speed 4-5: 40-50% kill (slow, BUG recovers even through Veil)
    rate = 0.90 - (speed - 1) * 0.10
    return max(0.35, min(rate, 0.90))


def compute_fow_priority(interaction, spell):
    """
    Whether BUG should use FoW on this spell. Returns True to counter.

    Rules (no magic numbers — based on game logic):
    - Always counter win conditions
    - Always counter lock pieces (Chalice, Blood Moon)
    - Don't counter CMC ≤ 2 creatures vs creature-based decks (use Push instead)
    - Against combo: counter tutors and key spells, let cantrips through
    """
    if spell.win_condition or spell.lock_piece:
        return True                       # always counter these
    if spell.is_combo_piece:
        return True                       # always counter combo pieces

    creature = interaction.get('creature_based', False)
    if creature and spell.cmc <= 2 and not spell.lock_piece:
        return False                      # don't FoW cheap creatures, use Push

    if spell.cmc >= 3:
        return True                       # counter expensive threats

    return False                          # let small stuff through


def get_interaction(matchup):
    """Get interaction profile from deck_registry."""
    try:
        from deck_registry import get_meta
        meta = get_meta(matchup)
        if meta:
            return meta.get('interaction', {})
    except ImportError:
        pass
    return {}


# ── Default interaction profiles for common archetypes ─────────────────────
# These are used as fallbacks when a deck doesn't declare 'interaction'

ARCHETYPE_DEFAULTS = {
    'fast_combo':    {'speed': 2, 'resilience': 1, 'uses_graveyard': False, 'uses_veil': True,
                      'soft_to_wasteland': False, 'creature_based': False},
    'combo':         {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False,
                      'soft_to_wasteland': False, 'creature_based': False},
    'gy_combo':      {'speed': 3, 'resilience': 2, 'uses_graveyard': True, 'uses_veil': False,
                      'soft_to_wasteland': False, 'creature_based': False},
    'aggro':         {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False,
                      'soft_to_wasteland': False, 'creature_based': True},
    'prison':        {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False,
                      'soft_to_wasteland': False, 'creature_based': False},
    'land_combo':    {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False,
                      'soft_to_wasteland': True, 'creature_based': False},
    'mirror':        {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False,
                      'soft_to_wasteland': False, 'creature_based': True},
}


def get_or_infer_interaction(matchup):
    """Get interaction profile, inferring from categories if not declared."""
    profile = get_interaction(matchup)
    if profile:
        return profile

    # Infer from categories
    try:
        from deck_registry import get_categories
        cats = get_categories(matchup)
        # Use most specific matching archetype
        for cat in ('fast_combo', 'gy_combo', 'land_combo', 'combo', 'prison', 'aggro', 'mirror'):
            if cat in cats:
                return dict(ARCHETYPE_DEFAULTS[cat])
    except ImportError:
        pass

    # Ultimate fallback
    return {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False,
            'soft_to_wasteland': False, 'creature_based': False}
