"""
Dimir Flash (Wan Shi Tong) — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_dimir_flash_deck


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_dimir_flash(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _opp_dimir_flash
    def _log(msg, key=False):
        gs.log_event('o', 'main', msg, key)
        log_entries.append(msg)
    _opp_dimir_flash(gs, total_mana, _log, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_dimir_flash(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    return 2 <= lc <= 4 and action >= 2


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'dimir_flash',
    'name':       'Dimir Flash (Wan Shi Tong)',
    'make_deck':  make_dimir_flash_deck,
    'strategy':   _strategy_dimir_flash,
    'keep':       _keep_dimir_flash,
    'categories': {'bowm_decks', 'mirror'},
    'interaction': {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.03,
}
