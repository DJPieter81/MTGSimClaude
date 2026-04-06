"""
Artifacts Prison — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_prison_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_prison(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_prison as _engine_strategy_prison
    _engine_strategy_prison(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_prison(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    lock = [c for c in nonlands if c.tag in ('chalice', 'bridge', 'trini')]
    thr = [c for c in nonlands if c.is_creature()]
    return 2 <= lc <= 4 and (lock or thr)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'prison',
    'name':       'Artifacts Prison',
    'make_deck':  make_prison_deck,
    'strategy':   _strategy_prison,
    'keep':       _keep_prison,
    'categories': {'prison'},
    'interaction': {'speed': 3, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False, 'opp_threats': 12},
    'meta_share': 0.06,
}
