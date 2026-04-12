"""
Death and Taxes — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_dnt_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_dnt(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_dnt as _engine_strategy_dnt
    _engine_strategy_dnt(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_dnt(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_vial = 'vial' in tags
    has_thalia = 'thalia' in tags
    has_stp = 'stp' in tags
    has_solitude = 'solitude' in tags
    has_removal = has_stp or has_solitude
    creatures = [c for c in nonlands if c.is_creature()]
    action = len(creatures) + (1 if has_vial else 0) + (1 if has_stp else 0)

    # Need 2-4 lands + some action
    if not (2 <= lc <= 4):
        return False
    # Auto-keep strong hands
    if has_vial:
        return True  # Vial = engine, always keep
    if has_thalia and action >= 2:
        return True  # Thalia + backup
    if has_removal and creatures:
        return True  # interaction + clock
    # Acceptable: 2+ action cards including at least 1 creature
    return action >= 2 and len(creatures) >= 1


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'dnt',
    'name':       'Death and Taxes',
    'make_deck':  make_dnt_deck,
    'strategy':   _strategy_dnt,
    'keep':       _keep_dnt,
    'categories': {'prison', 'vial_decks'},
    'interaction': {'speed': 3, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'opp_threats': 8},
    'meta_share': 0.02,
}
