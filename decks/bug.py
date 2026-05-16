"""
BUG Tempo — auto-registered deck module.
Uses the standard protagonist_turn → strategy dispatch like all other decks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_bug_deck


# ─── Wrapper functions ────────────────────────────────────────────────────────
# Both `from engine import _strategy_bug` and `from game import bug_keep`
# are deferred to call time. Direct imports fail with a circular-import
# cycle when bug.py is loaded during config.py's MatchupCategory class
# body (via _registry_decks → deck_registry.init() → decks/bug.py).
# engine.py and game.py both pull from config; if config is mid-loading
# (before GameRules / MatchupCategory are defined), those imports fail
# silently and leave BUG unregistered. All other decks already follow this
# deferred-wrapper pattern. See
# docs/design/2026-05-15_post-phase-6-re-architecture.md (PYTHONHASHSEED
# hunt section) for the post-mortem.

def _strategy_bug(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_bug as _engine_strategy_bug
    _engine_strategy_bug(player, opponent, gs, total_mana, log_fn, log_entries)


def _bug_keep(hand, matchup=''):
    from game import bug_keep as _game_bug_keep
    return _game_bug_keep(hand, matchup)


DECK_META = {
    'key':        'bug',
    'name':       'BUG Tempo',
    'make_deck':  make_bug_deck,
    'strategy':   _strategy_bug,
    'keep':       _bug_keep,
    'categories': {'tempo'},
    'meta_share': 0.04,
}
