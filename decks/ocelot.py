"""
Ocelot Pride Midrange — Mardu energy aggro.
Based on Sorathrix 5th Legacy Showcase Qualifier 2026-04-05.
Most popular deck in the format (~20% meta share).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import (creature, instant, sorcery, enchantment,
                   fetch_land, dual_land, basic_land, utility_land)


def make_ocelot_deck():
    d = []
    # Creatures (24)
    d += [creature('Ocelot Pride', 1, {'W':1}, {'W'}, 1, 1, tag='ocelot')] * 4
    d += [creature('Guide of Souls', 1, {'W':1}, {'W'}, 1, 1, tag='guide')] * 4
    d += [creature('Ajani, Nacatl Pariah', 2, {'W':1,'generic':1}, {'W'}, 2, 1, tag='ajani')] * 4
    d += [creature('Amped Raptor', 2, {'R':1,'generic':1}, {'R'}, 2, 1, tag='raptor')] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm', flash=True)] * 4
    d += [creature('Voice of Victory', 2, {'W':1,'generic':1}, {'W'}, 2, 2, tag='voice')] * 4
    # Spells (13)
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp', is_removal=True)] * 4
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [sorcery('Cabal Therapy', 1, {'B':1}, {'B'}, tag='therapy')] * 3
    d += [enchantment('Goblin Bombardment', 2, {'R':1,'generic':1}, {'R'}, tag='bombardment')] * 2
    # Lands (23)
    d += [fetch_land('Arid Mesa', ['Mountain','Plains'])] * 4
    d += [fetch_land('Marsh Flats', ['Swamp','Plains'])] * 4
    d += [utility_land('Wasteland', ['C'], 'wl')] * 4
    d += [utility_land('Karakas', ['W'], 'karakas')] * 2
    d += [dual_land('Plateau', ['R','W'], ['Mountain','Plains'])] * 2
    d += [dual_land('Scrubland', ['W','B'], ['Plains','Swamp'])] * 2
    d += [dual_land('Badlands', ['B','R'], ['Swamp','Mountain'])] * 1
    d += [basic_land('Plains', 'W', 'Plains')] * 1
    d += [utility_land('Elegant Parlor', ['W','B'], 'parlor')] * 1
    d += [utility_land('Shadowy Backstreet', ['B'], 'backstreet')] * 1
    d += [utility_land('Silent Clearing', ['W','B'], 'clearing')] * 1
    assert len(d) == 60, f"Ocelot deck: {len(d)}"
    return d


def _keep_ocelot(hand, matchup=''):
    lands = sum(1 for c in hand if c.is_land())
    creatures = sum(1 for c in hand if c.is_creature())
    disruption = sum(1 for c in hand if c.tag in ('ts', 'therapy', 'stp'))
    return 1 <= lands <= 4 and creatures >= 1 and (creatures + disruption) >= 2


def _ocelot_strategy_proxy(player, opponent, gs, total_mana, log_fn, log_entries):
    """Thin wrapper that dispatches to the real strategy in engine.py.

    Kept here so engine.py owns the logic (matches storm/mono_black pattern)
    while the deck module stays the registry's source of truth.
    """
    from engine import _strategy_ocelot
    return _strategy_ocelot(player, opponent, gs, total_mana, log_fn, log_entries)


DECK_META = {
    'key':        'ocelot',
    'name':       'Ocelot Pride Midrange',
    'make_deck':  make_ocelot_deck,
    'strategy':   _ocelot_strategy_proxy,
    'keep':       _keep_ocelot,
    'categories': {'aggro'},
    'meta_share': 0.12,
}
