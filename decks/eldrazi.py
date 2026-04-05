"""
Eldrazi Aggro — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_eldrazi_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_eldrazi(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_eldrazi
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_eldrazi(gs, total_mana, _log, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_eldrazi(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    lock = any(t in tags for t in ('chalice', 'bridge', 'trini'))
    thr = sum(1 for c in nonlands if c.is_creature())
    fast = any(c.tag in ('tomb', 'city', 'temple') for c in lands)
    # Eldrazi wants fast mana + lock or threat
    if len(hand) <= 5: return lc >= 1 and (lock or thr >= 1)
    return 1 <= lc <= 4 and (lock or (fast and thr >= 1) or thr >= 2)

# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'eldrazi',
    'name':       'Eldrazi Aggro',
    'make_deck':  make_eldrazi_deck,
    'strategy':   _strategy_eldrazi,
    'keep':       _keep_eldrazi,
    'categories': {'aggro'},
    'opp_interaction_rate': {'eldrazi': 0.73},
    'meta_share': 0.03,
}
