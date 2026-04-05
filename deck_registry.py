"""
deck_registry.py — Auto-discovery and registration for all deck modules.

Adding a new deck requires ONLY creating a module in decks/ with a DECK_META dict.
No edits needed to engine.py, sim.py, config.py, cards.py, or game.py.

DECK_META schema:
    DECK_META = {
        'key':        str,           # unique ID used everywhere (e.g. 'sneak_a')
        'name':       str,           # display name (e.g. 'Sneak & Show A (rerere)')
        'make_deck':  callable,      # returns List[Card] of 60 cards
        'strategy':   callable,      # strategy(player, opponent, gs, total_mana, log_fn, log_entries)
        'keep':       callable|None, # mulligan keep(hand, matchup) → bool. None = use default.
        'categories': set[str],      # e.g. {'combo', 'land_combo', 'fast_combo'}
        'meta_share': float,         # metagame share (0.0-1.0)
    }

Valid categories:
    combo, mirror, tempo_mirror, aggro, prison, gy_combo, land_combo,
    vial_decks, dimir_only, bowm_decks, fast_combo, tribal
"""

import importlib
import os
import glob

# ── Global registries ────────────────────────────────────────────────────────
_REGISTRY = {}       # key → DECK_META dict
_initialized = False


def _discover_decks():
    """Scan decks/ directory for modules with DECK_META."""
    decks_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'decks')
    results = {}

    for filepath in sorted(glob.glob(os.path.join(decks_dir, '*.py'))):
        modname = os.path.basename(filepath)[:-3]
        if modname.startswith('_') or modname.startswith('test') or modname in ('patch_parallel', 'show_fix'):
            continue

        try:
            mod = importlib.import_module(f'decks.{modname}')
            meta = getattr(mod, 'DECK_META', None)
            if meta and isinstance(meta, dict) and 'key' in meta:
                key = meta['key']
                # Validate required fields
                for field in ('key', 'name', 'make_deck', 'strategy'):
                    if field not in meta:
                        print(f"  [WARN] decks/{modname}.py DECK_META missing '{field}'")
                        continue
                results[key] = meta
        except Exception as e:
            # Module doesn't have DECK_META or failed to import — skip silently
            pass

    return results


def init():
    """Initialize the registry. Safe to call multiple times."""
    global _REGISTRY, _initialized
    if _initialized:
        return _REGISTRY
    _REGISTRY = _discover_decks()
    _initialized = True
    return _REGISTRY


def get_registry():
    """Return the deck registry dict. Initializes if needed."""
    if not _initialized:
        init()
    return _REGISTRY


def get_meta(key):
    """Get DECK_META for a deck key."""
    return get_registry().get(key)


def get_all_keys():
    """Return sorted list of all registered deck keys."""
    return sorted(get_registry().keys())


def get_strategy(key):
    """Get strategy function for a deck key."""
    meta = get_meta(key)
    return meta['strategy'] if meta else None


def get_make_deck(key):
    """Get deck constructor for a deck key."""
    meta = get_meta(key)
    return meta['make_deck'] if meta else None


def get_keep_fn(key):
    """Get mulligan keep function for a deck key. Returns None if using default."""
    meta = get_meta(key)
    return meta.get('keep') if meta else None


def get_categories(key):
    """Get category set for a deck key."""
    meta = get_meta(key)
    return meta.get('categories', set()) if meta else set()


def get_meta_share(key):
    """Get metagame share for a deck key."""
    meta = get_meta(key)
    return meta.get('meta_share', 0.02) if meta else 0.02


def is_in_category(key, category):
    """Check if a deck is in a given category."""
    return category in get_categories(key)


def get_decks_in_category(category):
    """Get all deck keys in a given category."""
    return frozenset(k for k in get_all_keys() if is_in_category(k, category))


# ── Registration into existing systems ────────────────────────────────────────

def register_into_decks_dict(decks_dict):
    """Register all discovered deck constructors into a DECKS dict."""
    for key, meta in get_registry().items():
        if key not in decks_dict:
            decks_dict[key] = meta['make_deck']


def register_into_strategies_dict(strategies_dict):
    """Register all discovered strategies into a STRATEGIES dict."""
    for key, meta in get_registry().items():
        if key not in strategies_dict:
            strategies_dict[key] = meta['strategy']


def build_matchup_meta():
    """Build MATCHUP_META dict from all registered decks."""
    meta = {}
    for key, deck_meta in get_registry().items():
        meta[key] = {
            'name': deck_meta['name'],
            'share': deck_meta.get('meta_share', 0.02),
        }
    return meta
