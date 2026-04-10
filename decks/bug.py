"""
BUG Tempo — auto-registered deck module.
Deck constructor in cards.py, strategy in engine.py (bug_turn handles full turn).

NOTE: Unlike other decks, BUG's strategy is a full turn function (bug_turn)
that handles untap/draw/land/mana/strategy/combat inline. It is NOT called
via the standard protagonist_turn → strategy_fn dispatch. play_turn()
routes directly to bug_turn when p1_deck == 'bug'.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_bug_deck
from game import bug_keep


DECK_META = {
    'key':        'bug',
    'name':       'BUG Tempo',
    'make_deck':  make_bug_deck,
    'strategy':   None,  # BUG uses bug_turn directly, not strategy dispatch
    'keep':       bug_keep,
    'categories': set(),
    'meta_share': 0.04,
}
