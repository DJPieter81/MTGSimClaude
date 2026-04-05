"""
UWx Control — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_uwx_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_uwx(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_uwx
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_uwx(gs, total_mana, _log, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_uwx(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    return 2 <= lc <= 4 and action >= 2


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'uwx',
    'name':       'UWx Control',
    'make_deck':  make_uwx_deck,
    'strategy':   _strategy_uwx,
    'keep':       _keep_uwx,
    'categories': {'mirror'},
    'interaction': {'speed': 5, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.04,
}
