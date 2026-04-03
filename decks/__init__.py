"""
decks/ — Plugin architecture for new deck additions.

Each deck module is self-contained:
  - make_Xdeck() / make_Xsideboard()  — card lists
  - _strategy_X()                     — direction-agnostic strategy
  - DECK_META                         — name, field%, confidence
  - test_X()                          — mini test suite

Registration via register_decks() — safe, additive, no engine.py changes.
"""

def register_decks():
    """Import all deck modules and register into DECKS/STRATEGIES."""
    from cards import DECKS
    from sim import STRATEGIES
    
    modules = []
    try:
        from decks import eight_cast
        DECKS['eight_cast'] = eight_cast.make_eight_cast_deck
        STRATEGIES['eight_cast'] = eight_cast._strategy_eight_cast
        modules.append('eight_cast')
    except Exception as e:
        print(f"eight_cast not ready: {e}")
    
    try:
        from decks import tes
        DECKS['tes'] = tes.make_tes_deck
        STRATEGIES['tes'] = tes._strategy_tes
        modules.append('tes')
    except Exception as e:
        print(f"tes not ready: {e}")
    
    return modules
