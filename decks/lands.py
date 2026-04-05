"""
Lands — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_lands_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_lands(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_lands
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_lands(gs, total_mana, _log, log_entries, gs.turn)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_lands(hand, matchup=''):
    """Lands keeps most hands — 45 lands in deck means 5+ land hands are normal."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    # Lands wants: combo pieces (Depths/Stage) OR utility lands + a spell
    combo_lands = sum(1 for c in lands if c.is_combo_piece)
    has_spell = len(nonlands) >= 1
    has_combo = combo_lands >= 1
    has_engine = any(c.tag in ('loam', 'crop', 'reclaimer') for c in nonlands)
    # Keep almost any hand with lands + something to do
    if len(hand) <= 5:
        return lc >= 2  # just need lands
    return lc >= 2 and (has_combo or has_engine or has_spell)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'lands',
    'name':       'Lands',
    'make_deck':  make_lands_deck,
    'strategy':   _strategy_lands,
    'keep':       _keep_lands,
    'categories': {'land_combo'},
    'interaction': {'speed': 5, 'resilience': 5, 'uses_graveyard': True, 'uses_veil': False, 'soft_to_wasteland': True, 'creature_based': False, 'opp_calibration': 0.6},
    'meta_share': 0.04,
}
