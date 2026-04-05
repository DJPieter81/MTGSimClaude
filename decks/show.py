"""
Show and Tell — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_show_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_show(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_show as _engine_strategy_show
    _engine_strategy_show(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_show(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    tags = {c.tag for c in hand}
    combo = [c for c in nonlands if c.is_combo_piece or c.win_condition]
    can = [c for c in nonlands if c.tag in ('bs', 'ponder')]
    return 1 <= lc <= 4 and (combo or can)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'show',
    'name':       'Show and Tell',
    'make_deck':  make_show_deck,
    'strategy':   _strategy_show,
    'keep':       _keep_show,
    'categories': {'combo', 'land_combo'},
    'interaction': {'speed': 3, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': True, 'soft_to_wasteland': False, 'creature_based': False, 'opp_threats': 10},
    'meta_share': 0.06,
}
