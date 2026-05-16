"""
Painter — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_painter_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_painter(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_painter as _engine_strategy_painter
    _engine_strategy_painter(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_painter(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    fast_mana = sum(1 for c in nonlands if c.mana_ritual)
    action = sum(1 for c in nonlands if c.tag in ('karn', 'tezzeret', 'ring', 'painter', 'monolith'))
    return (lc + fast_mana) >= 2 and action >= 1


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'painter',
    'name':       'Painter',
    'make_deck':  make_painter_deck,
    'strategy':   _strategy_painter,
    'keep':       _keep_painter,
    'categories': {'control'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.03,
}
