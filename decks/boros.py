"""
Boros Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_boros_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_boros(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_boros as _engine_strategy_boros
    _engine_strategy_boros(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_boros(hand, matchup=''):
    """Boros aggro mulligan: want 2-4 lands + any turn-1 play.
    Permissive — Boros aggro prefers imperfect 7s over 6-card mulligans."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_t1 = 'vial' in tags or any(c.is_creature() for c in nonlands)
    return 2 <= lc <= 4 and has_t1


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'boros',
    'name':       'Boros Aggro',
    'make_deck':  make_boros_deck,
    'strategy':   _strategy_boros,
    'keep':       _keep_boros,
    'categories': {'aggro', 'prison', 'vial_decks'},
    'interaction': {'speed': 4, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.01,
}
