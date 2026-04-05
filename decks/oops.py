"""
Oops All Spells — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_oops_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_oops(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_oops
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_oops(gs, total_mana, _log, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_oops(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    combo = [c for c in nonlands if c.is_combo_piece or c.win_condition]
    can = [c for c in nonlands if c.tag in ('bs', 'ponder')]
    return 1 <= lc <= 4 and (combo or can)


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'oops',
    'name':       'Oops All Spells',
    'make_deck':  make_oops_deck,
    'strategy':   _strategy_oops,
    'keep':       _keep_oops,
    'categories': {'combo', 'gy_combo', 'fast_combo'},
    'bug_interaction_rate': {'oops': 0.15},
    'meta_share': 0.04,
}
