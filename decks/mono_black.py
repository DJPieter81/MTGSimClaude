"""
Mono Black Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_mono_black_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_mono_black(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_mono_black as _engine_strategy_mono_black
    _engine_strategy_mono_black(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_mono_black(hand, matchup=''):
    """Mono Black: keep 2-4 lands with at least 1 creature OR 2+ disruption spells."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    disruption = sum(1 for c in nonlands if c.tag in ('ts', 'hymn', 'push', 'snuffout'))
    return 2 <= lc <= 4 and (threats >= 1 or disruption >= 2)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'mono_black',
    'name':       'Mono Black Aggro',
    'make_deck':  make_mono_black_deck,
    'strategy':   _strategy_mono_black,
    'keep':       _keep_mono_black,
    'categories': {'aggro', 'bowm_decks'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.01,
}
