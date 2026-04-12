"""
Oops All Spells — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_oops_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_oops(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_oops as _engine_strategy_oops
    _engine_strategy_oops(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_oops(hand, matchup=''):
    # Oops needs: combo piece (spy/informer) + enough mana to cast it (4 mana)
    # Mana sources: MDFC lands, Petals, Spirit Guides, Rituals, Chrome Mox
    combo = any(c.tag in ('spy', 'informer') for c in hand)
    spact = any(c.tag == 'spact' for c in hand)  # Summoner's Pact finds spy
    has_combo_access = combo or spact
    mana_sources = sum(1 for c in hand if c.mana_ritual or getattr(c, 'is_mdfc_land', False))
    return has_combo_access and mana_sources >= 2


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'oops',
    'name':       'Oops All Spells',
    'make_deck':  make_oops_deck,
    'strategy':   _strategy_oops,
    'keep':       _keep_oops,
    'categories': {'combo', 'gy_combo', 'fast_combo'},
    'interaction': {'speed': 1, 'resilience': 1, 'uses_graveyard': True, 'uses_veil': True, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.06,
}
