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
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    return 2 <= lc <= 5 and any(c.is_combo_piece for c in nonlands)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'lands',
    'name':       'Lands',
    'make_deck':  make_lands_deck,
    'strategy':   _strategy_lands,
    'keep':       _keep_lands,
    'categories': {'land_combo'},
    'meta_share': 0.04,
}
