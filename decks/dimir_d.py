"""
Dimir Tempo D (Oceansoul92, 8th Place) — Legacy Challenge Top 8.

Dimir Tempo with Kaito variant. Deploys cheap threats (Tamiyo, Nethergoyf,
Bowmasters) backed by free countermagic (Force of Will, Daze) and efficient
removal (Fatal Push, Snuff Out). Kaito, Bane of Nightmares provides card
advantage and token generation. Murktide Regent closes games as a delve-powered
finisher. Thoughtseize strips combo pieces and key interaction.

Key differences from dimir_c:
- 2 Kaito, Bane of Nightmares (vs 0) — card advantage engine
- 3 Murktide Regent (vs 2) — more finishers
- 2 Mishra's Bauble (vs 1) — more free cantrips
- 3 Ponder (vs 4) — slightly less cantrip density
- 3 Fatal Push (vs 4) — slightly lighter removal
- No Barrowgoyf
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import (creature, instant, sorcery, artifact, planeswalker,
                   fetch_land, dual_land, basic_land, utility_land)
from rules import Card, CardType
from typing import List


# ─── Deck construction ────────────────────────────────────────────────────────

def make_dimir_d_deck() -> List[Card]:
    d: List[Card] = []

    # ── Creatures (15) ───────────────────────────────────────────────────────

    # Brazen Borrower: 3/1 flash flyer, bounces a permanent
    d += [creature('Brazen Borrower', 3, {'U': 1, 'generic': 2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 1

    # Murktide Regent: delve flyer, effectively 2 mana with full GY
    d += [creature('Murktide Regent', 7, {'U': 1, 'generic': 6}, {'U'}, 5, 5,
                   tag='murk', delve=True, flying=True)] * 3

    # Nethergoyf: P/T = card types in all GYs
    d += [creature('Nethergoyf', 2, {'B': 1, 'generic': 1}, {'B'}, 0, 1,
                   tag='nether')] * 3

    # Orcish Bowmasters: flash, triggers on opponent draw
    d += [creature('Orcish Bowmasters', 2, {'B': 1, 'generic': 1}, {'B'}, 1, 1,
                   tag='bowm', flash=True, draw_trigger=True)] * 4

    # Tamiyo, Inquisitive Student: 0/3, flips to planeswalker
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U': 1}, {'U'}, 0, 3,
                   tag='tamiyo')] * 4

    # ── Planeswalkers (2) ────────────────────────────────────────────────────

    # Kaito, Bane of Nightmares: draws cards, creates tokens
    d += [planeswalker('Kaito, Bane of Nightmares', 3,
                       {'U': 1, 'B': 1, 'generic': 1}, {'U', 'B'},
                       tag='kaito', engine=True)] * 2

    # ── Instants (14) ────────────────────────────────────────────────────────

    # Brainstorm
    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4

    # Daze
    d += [instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'},
                  tag='daze')] * 3

    # Fatal Push: kills CMC <=2 (or <=4 with revolt)
    d += [instant('Fatal Push', 1, {'B': 1}, {'B'}, tag='push',
                  is_removal=True)] * 3

    # Force of Will
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4

    # Snuff Out: free removal, pay 4 life
    d += [instant('Snuff Out', 4, {'B': 1, 'generic': 3}, {'B'}, tag='snuff',
                  is_removal=True, life_cost=4)] * 1

    # ── Sorceries (7) ────────────────────────────────────────────────────────

    # Ponder
    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 3

    # Thoughtseize: discard + pay 2 life
    d += [sorcery('Thoughtseize', 1, {'B': 1}, {'B'}, tag='seize',
                  life_cost=2)] * 4

    # ── Artifacts (2) ────────────────────────────────────────────────────────

    # Mishra's Bauble: free cantrip
    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble',
                   is_cantrip=True)] * 2

    # ── Lands (19) ───────────────────────────────────────────────────────────

    # Fetch lands (9)
    d += [fetch_land('Flooded Strand', ['Island', 'Plains'])] * 1
    d += [fetch_land('Marsh Flats', ['Swamp', 'Plains'])] * 1
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 1
    d += [fetch_land('Polluted Delta', ['Island', 'Swamp'])] * 4
    d += [fetch_land('Scalding Tarn', ['Island', 'Mountain'])] * 1

    # missing one fetch? no, that's 1+1+1+4+1 = 8 fetches

    # Dual lands (4)
    d += [dual_land('Underground Sea', ['U', 'B'], ['Island', 'Swamp'])] * 4

    # Utility lands (5)
    d += [utility_land('Undercity Sewers', ['U', 'B'], 'sewers')] * 1
    d += [utility_land('Wasteland', [], 'wl')] * 4

    # Basic lands (2)
    d += [basic_land('Island', 'U', 'Island')] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1

    assert len(d) == 60, f"Dimir D deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_dimir_d(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Dimir Tempo (Oceansoul92) strategy.

    Priority:
    1. Thoughtseize T1 to strip combo pieces / key cards
    2. Deploy threats: T1 Tamiyo, T2 Nethergoyf/Bowmasters
    3. Murktide Regent when GY is full (delve reduces cost)
    4. Kaito, Bane of Nightmares (3 mana, card advantage engine)
    5. Cantrip: Brainstorm/Ponder (careful about Bowmasters triggers)
    6. Removal: Fatal Push, Snuff Out (free with 4 life)
    7. Combat: attack with all non-summoning-sick creatures
    8. Brazen Borrower as flash threat (3 mana)
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf

    mana = total_mana

    # ── 1. Thoughtseize — strip key cards from opponent ─────────────────────

    seize = player.find_tag('seize')
    if seize and mana >= 1:
        player.remove_from_hand(seize)
        player.add_to_grave(seize)
        mana -= 1
        player.life -= 2
        log_fn("Thoughtseize (pay 2 life)")
        gs.check_life_totals()
        if gs.game_over:
            return
        # Discard best card from opponent's hand
        if opponent.hand:
            # Prioritize: combo pieces, threats, removal
            target = opponent.hand[0]
            opponent.hand.remove(target)
            opponent.add_to_grave(target)
            log_fn(f"  Thoughtseize takes {target.name}")
            update_goyf(gs)

    if gs.game_over:
        return

    # ── 2. Deploy threats ───────────────────────────────────────────────────

    deployed_threat = False

    # Tamiyo — best T1 play (0/3, flips to planeswalker)
    tamiyo = player.find_tag('tamiyo')
    if tamiyo and mana >= 1:
        player.remove_from_hand(tamiyo)
        if not _try_counter_any(player, opponent, gs, tamiyo, log_entries):
            player.put_creature_in_play(tamiyo)
            mana -= 1
            log_fn("Tamiyo, Inquisitive Student (0/3)")
        else:
            player.add_to_grave(tamiyo)
        deployed_threat = True

    # Orcish Bowmasters — flash, hold for opponent's draw triggers
    if not deployed_threat:
        bowm = player.find_tag('bowm')
        if bowm and mana >= 2:
            player.remove_from_hand(bowm)
            if not _try_counter_any(player, opponent, gs, bowm, log_entries):
                player.put_creature_in_play(bowm)
                gs.bowmasters_on_board = True
                mana -= 2
                log_fn("Orcish Bowmasters")
                # ETB: deal 1 damage, create 1/1 orc army
                if opponent.creatures:
                    target = min(opponent.creatures, key=lambda c: c.toughness)
                    target.damage_marked += 1
                    log_fn(f"  Bowmasters ETB -> 1 damage to {target.card.name}")
                    gs.state_based_actions()
            else:
                player.add_to_grave(bowm)
            deployed_threat = True

    # Nethergoyf — GY-scaling 2-drop
    if not deployed_threat:
        goyf = player.find_tag('nether')
        if goyf and mana >= 2:
            player.remove_from_hand(goyf)
            if not _try_counter_any(player, opponent, gs, goyf, log_entries):
                player.put_creature_in_play(goyf)
                mana -= 2
                log_fn(f"{goyf.name}")
                update_goyf(gs)
            else:
                player.add_to_grave(goyf)
            deployed_threat = True

    # Murktide Regent — delve makes it effectively 2 mana with 5+ cards in GY
    if not deployed_threat:
        murk = player.find_tag('murk')
        if murk:
            gy_count = len(player.graveyard)
            delve_amount = min(gy_count, 6)
            effective_cost = max(2, 7 - delve_amount)
            if mana >= effective_cost:
                player.remove_from_hand(murk)
                if not _try_counter_any(player, opponent, gs, murk, log_entries):
                    exiled = 0
                    while exiled < delve_amount and player.graveyard:
                        player.graveyard.pop(0)
                        exiled += 1
                    player.put_creature_in_play(murk)
                    mana -= effective_cost
                    log_fn(f"Murktide Regent (delve {exiled}, paid {effective_cost})")
                else:
                    player.add_to_grave(murk)
                deployed_threat = True

    # ── 3. Kaito, Bane of Nightmares — card advantage engine ───────────────

    kaito = player.find_tag('kaito')
    if kaito and mana >= 3:
        player.remove_from_hand(kaito)
        if not _try_counter_any(player, opponent, gs, kaito, log_entries):
            mana -= 3
            # Kaito acts as a persistent card advantage engine
            gs.kaito_active = True
            # Model Kaito's immediate impact: draw a card (represents +1 ability)
            drawn = player.draw(1)
            log_fn("Kaito, Bane of Nightmares (card advantage engine)")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
        else:
            player.add_to_grave(kaito)

    if gs.game_over:
        return

    # Brazen Borrower — flash threat, deploy if no other plays
    if not deployed_threat:
        borrow = player.find_tag('borrow')
        if borrow and mana >= 3:
            player.remove_from_hand(borrow)
            if not _try_counter_any(player, opponent, gs, borrow, log_entries):
                player.put_creature_in_play(borrow)
                mana -= 3
                log_fn("Brazen Borrower (3/1 flash flyer)")
            else:
                player.add_to_grave(borrow)

    if gs.game_over:
        return

    # ── 4. Cantrips — find action ───────────────────────────────────────────

    for cantrip_tag in ('bs', 'ponder'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and mana >= 1:
            player.remove_from_hand(cantrip)
            player.add_to_grave(cantrip)
            mana -= 1
            drawn = player.draw(1)
            log_fn(f"{cantrip.name} — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            break  # one cantrip per turn

    # Mishra's Bauble — free cantrip (delayed draw, modeled as immediate)
    bauble = player.find_tag('bauble')
    if bauble:
        player.remove_from_hand(bauble)
        player.add_to_grave(bauble)
        drawn = player.draw(1)
        log_fn("Mishra's Bauble — cantrip")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')
        update_goyf(gs)

    if gs.game_over:
        return

    # ── 5. Removal ──────────────────────────────────────────────────────────

    # Snuff Out — free removal by paying 4 life
    snuff = player.find_tag('snuff')
    if snuff and player.life > 8:
        targets = [c for c in opponent.creatures if c.toughness <= 4]
        if targets:
            target = targets[0]
            player.remove_from_hand(snuff)
            player.add_to_grave(snuff)
            player.life -= 4
            opponent.remove_creature(target)
            log_fn(f"Snuff Out (pay 4 life) -> {target.card.name}", True)
            update_goyf(gs)

    if gs.game_over:
        return

    # Fatal Push — kills CMC <=2 (or <=4 with revolt from fetchlands)
    push = player.find_tag('push')
    if push and mana >= 1 and opponent.creatures:
        # Check for revolt (fetchland cracked this turn)
        revolt = getattr(gs, 'revolt_active', False)
        max_cmc = 4 if revolt else 2
        push_targets = [c for c in opponent.creatures if c.card.cmc <= max_cmc]
        if push_targets:
            target = max(push_targets, key=lambda c: c.power)
            player.remove_from_hand(push)
            player.add_to_grave(push)
            mana -= 1
            opponent.remove_creature(target)
            log_fn(f"Fatal Push -> {target.card.name}", True)
            update_goyf(gs)

    if gs.game_over:
        return

    # ── 6. Combat ───────────────────────────────────────────────────────────

    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_dimir_d():
    """Smoke tests for Dimir Tempo D deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_dimir_d_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'borrow': 1, 'murk': 3, 'nether': 3,
        'bowm': 4, 'tamiyo': 4,
        'kaito': 2,
        'bs': 4, 'ponder': 3,
        'daze': 3, 'fow': 4, 'push': 3, 'snuff': 1,
        'seize': 4,
        'bauble': 2,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 22
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 19, f"Land count {land_count} != 19"
    results.append("OK  Land count = 19")

    # Test 4: Creature count = 15
    creature_count = sum(1 for c in deck if c.card_type == CardType.CREATURE)
    assert creature_count == 15, f"Creature count {creature_count} != 15"
    results.append("OK  Creature count = 15")

    # Test 5: Murktide has delve + flying
    murk = next(c for c in deck if c.tag == 'murk')
    assert getattr(murk, 'delve', False), "Murktide should have delve"
    assert getattr(murk, 'flying', False), "Murktide should have flying"
    results.append("OK  Murktide has delve + flying")

    # Test 6: FoW has free_cast_if_blue
    fow = next(c for c in deck if c.tag == 'fow')
    assert getattr(fow, 'free_cast_if_blue', False), "FoW should have free_cast_if_blue"
    results.append("OK  Force of Will is free-castable")

    # Test 7: Brazen Borrower has flash + flying
    borrow = next(c for c in deck if c.tag == 'borrow')
    assert getattr(borrow, 'flash', False), "Borrower should have flash"
    assert getattr(borrow, 'flying', False), "Borrower should have flying"
    results.append("OK  Brazen Borrower has flash + flying")

    # Test 8: Bowmasters has flash + draw_trigger
    bowm = next(c for c in deck if c.tag == 'bowm')
    assert getattr(bowm, 'flash', False), "Bowmasters should have flash"
    assert getattr(bowm, 'draw_trigger', False), "Bowmasters should have draw_trigger"
    results.append("OK  Bowmasters has flash + draw_trigger")

    # Test 9: Kaito is a planeswalker with engine tag
    kaito = next(c for c in deck if c.tag == 'kaito')
    assert kaito.card_type == CardType.PLANESWALKER, "Kaito should be a planeswalker"
    assert getattr(kaito, 'engine', False), "Kaito should have engine=True"
    results.append("OK  Kaito is a planeswalker with engine")

    # Test 10: Strategy function is callable
    assert callable(_strategy_dimir_d), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running Dimir Tempo D (Oceansoul92) tests...")
    for r in test_dimir_d():
        print(f"  {r}")
    print("All tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_dimir_d(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    blue_access = any('U' in l.produces or l.is_fetch for l in lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
    action = threats + cantrips + counters
    if action == 0: return False
    if lc == 1: return blue_access and cantrips >= 1
    return 2 <= lc <= 4 and action >= 2


DECK_META = {
    'key':        'dimir_d',
    'name':       'Dimir Tempo D (Kaito)',
    'make_deck':  make_dimir_d_deck,
    'strategy':   _strategy_dimir_d,
    'keep':       _keep_dimir_d,
    'categories': {'mirror', 'tempo_mirror', 'dimir_only', 'bowm_decks'},
    'interaction': {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.03,
}
