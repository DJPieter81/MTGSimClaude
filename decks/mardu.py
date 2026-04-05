"""
Mardu Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_mardu_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_mardu(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_mardu as _engine_strategy_mardu
    _engine_strategy_mardu(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_mardu(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    disruption = sum(1 for c in nonlands if c.tag in ('seize', 'grief'))
    # Mardu wants land + threats or disruption
    if len(hand) <= 5: return lc >= 1 and (threats >= 1 or disruption >= 1)
    return 1 <= lc <= 4 and threats >= 1

# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'mardu',
    'name':       'Mardu Aggro',
    'make_deck':  make_mardu_deck,
    'strategy':   _strategy_mardu,
    'keep':       _keep_mardu,
    'categories': {'aggro', 'bowm_decks'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.03,
}
