"""
Dimir Tempo B (Barrowgoyf) — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_dimir_b_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_dimir_b(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_dimir as _engine_strategy_dimir
    _engine_strategy_dimir(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_dimir_b(hand, matchup=''):
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
    'key':        'dimir_b',
    'name':       'Dimir Tempo B (Barrowgoyf)',
    'make_deck':  make_dimir_b_deck,
    'strategy':   _strategy_dimir_b,
    'keep':       _keep_dimir_b,
    'categories': {'dimir_only', 'mirror', 'bowm_decks'},
    'interaction': {'speed': 3, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'opp_threats': 8},
    'meta_share': 0.05,
}
