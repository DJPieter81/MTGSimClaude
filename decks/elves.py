"""
Elves — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_elves_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_elves(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_elves as _engine_strategy_elves
    _engine_strategy_elves(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_elves(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    # Elves has mana dorks — 1 land + elf is fine
    if len(hand) <= 5: return lc >= 1 and threats >= 1
    return lc >= 1 and threats >= 2

# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'elves',
    'name':       'Elves',
    'make_deck':  make_elves_deck,
    'strategy':   _strategy_elves,
    'keep':       _keep_elves,
    'categories': {'aggro', 'tribal'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.02,
}
