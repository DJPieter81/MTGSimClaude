"""
UR Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_ur_aggro_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_ur_aggro(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_ur_aggro
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_ur_aggro(gs, total_mana, _log, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_ur_aggro(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    # UR Aggro wants land + threat
    if len(hand) <= 5: return lc >= 1 and threats >= 1
    return 1 <= lc <= 3 and (threats >= 1 or cantrips >= 2)

# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'ur_aggro',
    'name':       'UR Aggro',
    'make_deck':  make_ur_aggro_deck,
    'strategy':   _strategy_ur_aggro,
    'keep':       _keep_ur_aggro,
    'categories': {'aggro', 'bowm_decks'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'opp_calibration': 0.45},
    'meta_share': 0.03,
}
