"""
Reanimator — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_reanimator_deck
from combo_engine import ReanimatePath


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_reanimator(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_reanimator as _engine_strategy_reanimator
    _engine_strategy_reanimator(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_reanimator(hand, matchup=''):
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

# Reanimator's combo-readiness rule (consumed by combo_engine.is_combo_ready_this_turn
# and the shared discard preamble in sim._execute_turn): the deck can fire
# T1-T2 if it has a reanimate-class spell AND a target (in hand or graveyard)
# AND a mana source — either Dark Ritual in hand OR Unmask-pitch with target.
# See combo.assembly_paths below for the two principal lines.

DECK_META = {
    'key':        'reanimator',
    'name':       'Reanimator',
    'make_deck':  make_reanimator_deck,
    'strategy':   _strategy_reanimator,
    'keep':       _keep_reanimator,
    'categories': {'combo', 'gy_combo'},
    'interaction': {'speed': 2, 'resilience': 2, 'uses_graveyard': True, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.02,
    # ── Combo metadata (consumed by combo_engine.py) ─────────────────────────
    # See docs/design/2026-05-09_combo_engine_architecture.md.
    'combo': {
        'pieces': frozenset({
            'reanimate', 'exhume', 'animatedead',                 # reanimate-class
            'gris', 'archon', 'atraxa', 'emrakul',                # targets
            'darkrit', 'petal', 'unmask', 'entomb',               # enablers
        }),
        'protection_tags': frozenset({'fow', 'fon', 'daze'}),
        # Cartesian product: {reanimate, exhume, animatedead} × {darkrit, unmask}
        # — six paths. Phase B2 migrated to ReanimatePath so each path
        # names its `reanimate_tag` and `enabler_tag` directly instead
        # of overloading `required_tags`. Mana_cost=1 throughout: Dark
        # Ritual nets +2 (covers exhume/animatedead's higher base cost)
        # and Unmask is alt-cast for free (chain still needs 1 land to
        # cast the reanimate spell). At least one target must be in
        # hand or graveyard.
        'assembly_paths': tuple(
            ReanimatePath(
                tag=f'{enabler}_{rean}',
                required_tags=frozenset({rean, enabler}),
                mana_cost=1,
                turns_to_kill=1,
                target_tags=frozenset({'gris', 'archon', 'atraxa', 'emrakul'}),
                enabler_tag=enabler,
                reanimate_tag=rean,
            )
            for enabler in ('darkrit', 'unmask')
            for rean    in ('reanimate', 'exhume', 'animatedead')
        ),
    },
}
