"""
BUG Tempo — auto-registered deck module.
Uses the standard protagonist_turn → strategy dispatch like all other decks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_bug_deck
from game import bug_keep
from engine import _strategy_bug


DECK_META = {
    'key':        'bug',
    'name':       'BUG Tempo',
    'make_deck':  make_bug_deck,
    'strategy':   _strategy_bug,
    'keep':       bug_keep,
    'categories': {'tempo'},
    'meta_share': 0.04,
}
