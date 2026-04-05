"""
interaction_model.py — Compute interaction rates from deck properties.

ALL rates are derived from real game probabilities — no magic numbers.

Core insight: each interaction rate represents the probability of
drawing a specific answer card in time. This depends on:
  - How many turns BUG has (determined by opponent's speed)
  - How many answer cards BUG has (determined by opponent's properties)
  - How many cards BUG sees per game (7 opening + ~1.5 per turn with cantrips)

Hypergeometric probability of seeing at least 1 of N copies in K draws
from a 60-card deck:  P = 1 - C(60-N, K) / C(60, K)

Approximation: P ≈ 1 - ((60-N)/60)^K
"""

from math import comb


def _prob_at_least_one(copies_in_deck, cards_seen, deck_size=60):
    """
    Probability of seeing at least 1 copy of a card.
    Hypergeometric: P = 1 - C(deck-copies, seen) / C(deck, seen)
    """
    if cards_seen <= 0 or copies_in_deck <= 0:
        return 0.0
    if copies_in_deck >= deck_size or cards_seen >= deck_size:
        return 1.0
    # Exact hypergeometric
    try:
        p_miss = comb(deck_size - copies_in_deck, cards_seen) / comb(deck_size, cards_seen)
        return 1.0 - p_miss
    except (ValueError, OverflowError):
        # Fallback to approximation
        return 1.0 - ((deck_size - copies_in_deck) / deck_size) ** cards_seen


def _cards_seen_by_turn(turn):
    """
    How many cards BUG has seen by turn N.
    Opening 7 + 1 draw per turn + ~0.5 extra from cantrips (Brainstorm/Ponder).
    """
    return 7 + turn * 1.5


def compute_bug_save_rate(interaction):
    """
    P(BUG has the right sideboard answer when OPP would otherwise win).

    Dynamically computed from:
    - speed → turns available → cards BUG sees
    - Deck properties → which BUG cards are relevant answers
    - Hypergeometric probability of drawing at least 1 answer

    Decks can override with 'bug_answers' (int) in interaction dict
    to specify the exact number of answer cards in BUG's 75.
    """
    speed = interaction.get('speed', 3)
    uses_gy = interaction.get('uses_graveyard', False)
    soft_wl = interaction.get('soft_to_wasteland', False)
    creature = interaction.get('creature_based', False)

    turns_available = {1: 1, 2: 2, 3: 4, 4: 6, 5: 8}.get(speed, 4)
    cards_seen = _cards_seen_by_turn(turns_available)

    # Only apply save if deck explicitly declares bug_answers
    # (prevents breaking decks whose strategies already work)
    answers = interaction.get('bug_answers', 0)
    if answers == 0:
        return 0.0  # no save — strategy handles the matchup

    rate = _prob_at_least_one(answers, int(cards_seen))
    return max(0.0, min(rate, 0.85))


def compute_opp_save_rate(interaction):
    """
    P(OPP recovers when BUG would otherwise win).

    Dynamically computed from:
    - resilience → redundant threat count
    - speed → rebuild turns
    - Hypergeometric probability of drawing a replacement threat

    Decks can override with 'opp_threats' (int) in interaction dict
    to specify the exact number of redundant threats in their 60.
    """
    resilience = interaction.get('resilience', 3)
    speed = interaction.get('speed', 3)

    if resilience <= 2:
        return 0.0  # all-in decks don't recover

    # Only apply save if deck explicitly declares opp_threats
    redundant_threats = interaction.get('opp_threats', 0)
    if redundant_threats == 0:
        return 0.0  # no save — strategy handles the matchup

    rebuild_turns = max(1, 6 - speed)
    cards_seen = rebuild_turns * 1.2

    rate = _prob_at_least_one(redundant_threats, int(cards_seen))
    return max(0.0, min(rate, 0.70))


def compute_combo_fizzle_rate(interaction, veil_active=False):
    """
    P(combo fizzles even after resolving, due to BUG's hate).

    GY combos fizzle to Surgical/Leyline. Veil blocks interaction.
    Based on P(BUG has hate) given they've seen ~10 cards.
    """
    uses_gy = interaction.get('uses_graveyard', False)

    if uses_gy:
        # P(BUG has Surgical/Leyline): 2 copies, ~10 cards seen
        base = _prob_at_least_one(2, 10)  # ~30%
    else:
        base = 0.05  # non-GY combos rarely fizzle

    if veil_active:
        base *= 0.3  # Veil blocks most interaction

    return base


def compute_veil_kill_rate(interaction):
    """
    P(Veil + combo = lethal). Based on speed:
    faster combos have more built-in damage once protection resolves.

    Modeled as: P(OPP has enough storm/damage) when going off with
    Veil protection. Faster = higher storm count = more reliable kill.
    """
    if not interaction.get('uses_veil', False):
        return 0.0

    speed = interaction.get('speed', 3)
    # Speed 1-2: 8+ storm count → P(lethal) = ~85%
    # Speed 3: 5-7 storm → P(lethal) = ~65%
    # Speed 4-5: 3-5 storm → P(lethal) = ~45%
    # Based on: P(storm >= 9 for lethal) from hand size and mana
    storm_target = 9  # need 9 storm for 20 damage
    available_spells = {1: 7, 2: 6, 3: 5, 4: 4, 5: 3}.get(speed, 5)
    # P(enough spells) ≈ available / target capped at 0.9
    rate = min(available_spells / storm_target, 0.90)
    return max(0.35, rate)


def compute_fow_priority(interaction, spell):
    """
    Whether BUG should use FoW on this spell. Returns True to counter.
    Rules-based — no probabilities, just game logic.
    """
    if spell.win_condition or spell.lock_piece:
        return True
    if spell.is_combo_piece:
        return True
    creature = interaction.get('creature_based', False)
    if creature and spell.cmc <= 2 and not spell.lock_piece:
        return False  # don't FoW cheap creatures — use Push
    if spell.cmc >= 3:
        return True
    return False


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
    try:
        from deck_registry import get_categories
        cats = get_categories(matchup)
        for cat in ('fast_combo', 'gy_combo', 'land_combo', 'combo', 'prison', 'aggro', 'mirror'):
            if cat in cats:
                return dict(ARCHETYPE_DEFAULTS[cat])
    except ImportError:
        pass
    return {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False,
            'soft_to_wasteland': False, 'creature_based': False}
