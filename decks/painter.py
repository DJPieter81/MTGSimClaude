"""
Painter — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_painter_deck
from combo_engine import AssemblyPath


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_painter(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_painter as _engine_strategy_painter
    _engine_strategy_painter(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_painter(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    fast_mana = sum(1 for c in nonlands if c.mana_ritual)
    action = sum(1 for c in nonlands if c.tag in ('karn', 'tezzeret', 'ring', 'painter', 'monolith'))
    return (lc + fast_mana) >= 2 and action >= 1


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'painter',
    'name':       'Painter',
    'make_deck':  make_painter_deck,
    'strategy':   _strategy_painter,
    'keep':       _keep_painter,
    'categories': {'combo'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.03,
    # ── Combo metadata (consumed by combo_engine.py) ─────────────────────────
    # Painter's Servant ({2}, names a color) + Grindstone ({1}, activate {3})
    # mills the opponent's library — Grindstone targets two cards sharing a
    # color, and Painter makes every card share blue, so the activation loops
    # the entire library into the graveyard.
    #
    # Painter runs zero counters / Veil — Defer is the only protection
    # response (Hold(card) returns None from _check_protection). The audit's
    # "add Veil of Summer" decklist recommendation is a separate change.
    'combo': {
        'pieces': frozenset({
            'painter', 'grind',                  # combo pieces
            'karn',                              # tutor (wishboard)
            'monolith', 'opal', 'petal',         # fast mana
            'ring',                              # engine + protection
        }),
        'protection_tags': frozenset(),
        'assembly_paths': (
            AssemblyPath(
                tag='painter_plus_grindstone',
                required_tags=frozenset({'painter', 'grind'}),
                mana_cost=4,        # Painter(2) + Grindstone(1) + activate(1)
                turns_to_kill=1,
            ),
            AssemblyPath(
                tag='karn_tutors_grindstone',
                required_tags=frozenset({'karn', 'painter'}),
                mana_cost=4,        # cast Karn, wish for Grindstone next turn
                turns_to_kill=2,
            ),
            AssemblyPath(
                tag='karn_tutors_painter',
                required_tags=frozenset({'karn', 'grind'}),
                mana_cost=4,        # cast Karn, wish for Painter next turn
                turns_to_kill=2,
            ),
        ),
    },
}
