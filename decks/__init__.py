"""
decks/ — Plugin architecture for new deck additions.

Each deck module is self-contained:
  - make_Xdeck() / make_Xsideboard()  — card lists
  - _strategy_X()                     — direction-agnostic strategy
  - DECK_META                         — name, field%, confidence
  - test_X()                          — mini test suite

Registration via register_decks() — safe, additive, no engine.py changes.
"""

# Module → (deck_key, make_fn_name, strategy_fn_name)
_DECK_MODULES = {
    'eight_cast': ('eight_cast', 'make_eight_cast_deck', '_strategy_eight_cast'),
    'tes':        ('tes',        'make_tes_deck',        '_strategy_tes'),
    'depths':     ('depths',     'make_depths_deck',     '_strategy_depths'),
    'burn':       ('burn',       'make_burn_deck',       '_strategy_burn'),
    'infect':     ('infect',     'make_infect_deck',     '_strategy_infect'),
    'goblins':    ('goblins',    'make_goblins_deck',    '_strategy_goblins'),
    'belcher':    ('belcher',    'make_belcher_deck',    '_strategy_belcher'),
    'ur_delver':  ('ur_delver',  'make_ur_delver_deck',  '_strategy_ur_delver'),
    'sneak_a':    ('sneak_a',    'make_sneak_a_deck',    '_strategy_sneak_a'),
    'sneak_b':    ('sneak_b',    'make_sneak_b_deck',    '_strategy_sneak_b'),
    'affinity':   ('affinity',   'make_affinity_deck',   '_strategy_affinity'),
    'ur_tempo':   ('ur_tempo',   'make_ur_tempo_deck',   '_strategy_ur_tempo'),
    'dimir_c':    ('dimir_c',    'make_dimir_c_deck',    '_strategy_dimir_c'),
    'dimir_d':    ('dimir_d',    'make_dimir_d_deck',    '_strategy_dimir_d'),
    'cephalid':   ('cephalid',   'make_cephalid_deck',   '_strategy_cephalid'),
    'cloudpost':  ('cloudpost',  'make_cloudpost_deck',  '_strategy_cloudpost'),
}


def register_decks():
    """Import all deck modules and register into DECKS/STRATEGIES."""
    from cards import DECKS
    from sim import STRATEGIES

    modules = []
    for mod_name, (key, make_fn, strat_fn) in _DECK_MODULES.items():
        try:
            mod = __import__(f'decks.{mod_name}', fromlist=[make_fn, strat_fn])
            DECKS[key] = getattr(mod, make_fn)
            STRATEGIES[key] = getattr(mod, strat_fn)
            modules.append(key)
        except Exception as e:
            print(f"{key} not ready: {e}")

    return modules
