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
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    tags = {c.tag for c in hand}
    has_t1 = 'vial' in tags or any(c.is_creature() for c in nonlands)
    return 2 <= lc <= 4 and has_t1


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
