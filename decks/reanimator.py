"""
Reanimator — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_reanimator_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_reanimator(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_reanimator as _engine_strategy_reanimator
    _engine_strategy_reanimator(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_reanimator(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    combo = [c for c in nonlands if c.is_combo_piece or c.win_condition]
    can = [c for c in nonlands if c.tag in ('bs', 'ponder')]
    return 1 <= lc <= 4 and (combo or can)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'reanimator',
    'name':       'Reanimator',
    'make_deck':  make_reanimator_deck,
    'strategy':   _strategy_reanimator,
    'keep':       _keep_reanimator,
    'categories': {'combo', 'gy_combo'},
    'interaction': {'speed': 2, 'resilience': 2, 'uses_graveyard': True, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.03,
}
