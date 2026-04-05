"""
Mardu Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_mardu_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_mardu(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_mardu
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_mardu(gs, total_mana, _log, log_entries, gs.turn)


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
    'meta_share': 0.03,
}
