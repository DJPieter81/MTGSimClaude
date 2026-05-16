"""
Storm (ANT) — auto-registered wrapper for built-in deck.
Deck constructor in cards.py, strategy in engine.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_storm_deck
from combo_engine import StormPath


# ─── Strategy wrapper ────────────────────────────────────────────────────────

def _strategy_storm(player, opponent, gs, total_mana, log_fn, log_entries):
    from engine import _strategy_storm as _engine_strategy_storm
    _engine_strategy_storm(player, opponent, gs, total_mana, log_fn, log_entries)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_storm(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    rituals = [c for c in nonlands if c.mana_ritual or c.tag in ('darkrit', 'cabalrit')]
    led = any(c.tag == 'led' for c in nonlands)
    has_mana = len(rituals) >= 1 or led
    effective_lands = lc + (1 if led else 0)
    if len(hand) == 7: return 1 <= effective_lands <= 4 and has_mana and lc < 5
    if len(hand) == 6: return 0 <= effective_lands <= 3 and has_mana
    if len(hand) == 5: return (has_mana and lc >= 1) or (led and len(nonlands) >= 2)
    return True


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'storm',
    'name':       'Storm (ANT)',
    'make_deck':  make_storm_deck,
    'strategy':   _strategy_storm,
    'keep':       _keep_storm,
    'categories': {'combo'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': True, 'uses_veil': True, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.01,
    # ── Combo metadata (consumed by combo_engine.py) ─────────────────────────
    # See docs/design/2026-05-09_combo_engine_architecture.md.
    'combo': {
        'pieces': frozenset({
            'tendrils', 'itutor', 'adnauseam', 'pif',          # win conditions
            'ritual', 'darkrit', 'cabalrit', 'petal', 'led',   # mana engines
        }),
        'protection_tags': frozenset({'fow', 'fon', 'daze', 'fluster', 'veil'}),
        # Phase B2 migrated to StormPath subtype. `mana_cost` is the
        # literal mana floor to start the chain; `needed_storm_count`
        # names the storm count Tendrils must hit on resolution
        # (ANT's standard ~10 spells for lethal at 20 life).
        'assembly_paths': (
            StormPath(
                tag='ritual_chain_tendrils',
                required_tags=frozenset({'tendrils'}),
                mana_cost=4,            # storm count + Tendrils cost
                turns_to_kill=1,
                needed_storm_count=10,  # ANT lethal storm count at 20 life
            ),
        ),
    },
}
