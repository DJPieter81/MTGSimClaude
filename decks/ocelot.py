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
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm')] * 4
    d += [creature('Voice of Victory', 2, {'W':1,'generic':1}, {'W'}, 2, 2, tag='voice')] * 4
    # Spells (13)
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp', is_removal=True)] * 4
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [sorcery('Cabal Therapy', 1, {'B':1}, {'B'}, tag='therapy')] * 3
    d += [enchantment('Goblin Bombardment', 2, {'R':1,'generic':1}, {'R'}, tag='bombardment')] * 2
    # Lands (23)
    d += [fetch_land('Arid Mesa', ['Mountain','Plains'])] * 4
    d += [fetch_land('Marsh Flats', ['Swamp','Plains'])] * 4
    d += [utility_land('Wasteland', [], 'wl')] * 4
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


def _strategy_ocelot(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Ocelot Pride Midrange — creature-based aggro with disruption.
    Plan: T1 Ocelot/Guide → T2 Bowmasters/Ajani/Raptor → attack and disrupt.
    Thoughtseize strips key cards. Swords removes blockers. Therapy for combo.
    """
    from engine import opp_can_cast, _try_counter_any, combat_declare, update_goyf

    # Thoughtseize: strip best card early
    ts = player.find_tag('ts')
    if ts and total_mana >= 1:
        player.remove_from_hand(ts); player.add_to_grave(ts)
        total_mana -= 1
        player.life -= 2
        if opponent.hand:
            nonlands = [c for c in opponent.hand if not c.is_land()]
            if nonlands:
                # Priority: combo > FoW > threats
                best = next((c for c in nonlands if c.win_condition or c.is_combo_piece),
                       next((c for c in nonlands if c.tag in ('fow', 'fon')),
                       next((c for c in nonlands if c.tag in ('bowm', 'murk', 'dd')),
                            nonlands[0])))
                opponent.hand.remove(best); opponent.add_to_grave(best)
                log_fn(f"Thoughtseize — strips {best.name} (life → {player.life})", True)

    # Cabal Therapy
    therapy = player.find_tag('therapy')
    if therapy and total_mana >= 1:
        player.remove_from_hand(therapy); player.add_to_grave(therapy)
        total_mana -= 1
        if opponent.hand:
            nonlands = [c for c in opponent.hand if not c.is_land()]
            if nonlands:
                tgt = nonlands[0]
                # Remove all copies
                to_remove = [c for c in opponent.hand if c.name == tgt.name]
                for c in to_remove:
                    opponent.hand.remove(c); opponent.add_to_grave(c)
                log_fn(f"Cabal Therapy naming {tgt.name} — hits {len(to_remove)}")

    # Deploy creatures by CMC (cheapest first)
    deploy_order = ['ocelot', 'guide', 'ajani', 'bowm', 'voice', 'raptor']
    for tag in deploy_order:
        card = player.find_tag(tag)
        if card and total_mana >= card.cmc:
            player.remove_from_hand(card)
            if not _try_counter_any(player, opponent, gs, card, log_entries):
                player.put_creature_in_play(card)
                total_mana -= card.cmc
                log_fn(f"{card.name}")
                if tag == 'bowm':
                    gs.bowmasters_on_board = True
            else:
                player.add_to_grave(card)

    # Swords to Plowshares: remove biggest blocker
    stp = player.find_tag('stp')
    if stp and total_mana >= 1 and opponent.creatures:
        biggest = max(opponent.creatures, key=lambda c: c.power + c.toughness)
        if biggest.power >= 2:  # worth removing
            player.remove_from_hand(stp); player.add_to_grave(stp)
            total_mana -= 1
            opponent.remove_creature(biggest)
            opponent.life += biggest.toughness  # STP gains life
            log_fn(f"Swords to Plowshares → exiles {biggest.name}")
            update_goyf(gs)

    # Combat: attack with everything not summoning-sick
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


def _keep_ocelot(hand, matchup=''):
    lands = sum(1 for c in hand if c.is_land())
    creatures = sum(1 for c in hand if c.is_creature())
    disruption = sum(1 for c in hand if c.tag in ('ts', 'therapy', 'stp'))
    return 1 <= lands <= 4 and creatures >= 1 and (creatures + disruption) >= 2


DECK_META = {
    'key':        'ocelot',
    'name':       'Ocelot Pride Midrange',
    'make_deck':  make_ocelot_deck,
    'strategy':   _strategy_ocelot,
    'keep':       _keep_ocelot,
    'categories': {'aggro'},
    'meta_share': 0.12,
}
