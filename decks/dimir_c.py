"""
Dimir Tempo C (pepeteam, 5th Place) — Legacy Challenge Top 8.

Dimir Tempo with Barrowgoyf variant. Deploys cheap threats (Tamiyo, Nethergoyf,
Barrowgoyf, Bowmasters) backed by free countermagic (Force of Will, Daze) and
efficient removal (Fatal Push, Snuff Out). Murktide Regent closes games as a
delve-powered finisher. Thoughtseize strips combo pieces and key interaction.

Key differences from dimir_d:
- 1 Barrowgoyf (additional GY-scaling threat alongside 3 Nethergoyf)
- 4 Ponder (vs 3) — more cantrip density
- 4 Fatal Push (vs 3) — heavier removal suite
- 1 Mishra's Bauble (vs 2) — lighter on baubles
- 2 Murktide Regent (vs 3)
- No Kaito, Bane of Nightmares
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import (creature, instant, sorcery, artifact,
                   fetch_land, dual_land, basic_land, utility_land)
from rules import Card, CardType
from typing import List


# ─── Deck construction ────────────────────────────────────────────────────────

def make_dimir_c_deck() -> List[Card]:
    d: List[Card] = []

    # ── Creatures (15) ───────────────────────────────────────────────────────

    # Barrowgoyf: P/T = card types in all GYs (like Tarmogoyf but black)
    d += [creature('Barrowgoyf', 2, {'B': 1, 'generic': 1}, {'B'}, 0, 1,
                   tag='barro')] * 1

    # Brazen Borrower: 3/1 flash flyer, bounces a permanent
    d += [creature('Brazen Borrower', 3, {'U': 1, 'generic': 2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 1

    # Murktide Regent: delve flyer, effectively 2 mana with full GY
    d += [creature('Murktide Regent', 7, {'U': 1, 'generic': 6}, {'U'}, 5, 5,
                   tag='murk', delve=True, flying=True)] * 2

    # Nethergoyf: P/T = card types in all GYs
    d += [creature('Nethergoyf', 2, {'B': 1, 'generic': 1}, {'B'}, 0, 1,
                   tag='nether')] * 3

    # Orcish Bowmasters: flash, triggers on opponent draw
    d += [creature('Orcish Bowmasters', 2, {'B': 1, 'generic': 1}, {'B'}, 1, 1,
                   tag='bowm', flash=True, draw_trigger=True)] * 4

    # Tamiyo, Inquisitive Student: 0/3, flips to planeswalker
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U': 1}, {'U'}, 0, 3,
                   tag='tamiyo')] * 4

    # ── Instants (14) ────────────────────────────────────────────────────────

    # Brainstorm
    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4

    # Daze
    d += [instant('Daze', 1, {'U': 1}, {'U'},
                  tag='daze')] * 3

    # Fatal Push: kills CMC ≤2 (or ≤4 with revolt)
    d += [instant('Fatal Push', 1, {'B': 1}, {'B'}, tag='push',
                  is_removal=True)] * 4

    # Force of Will
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4

    # Snuff Out: free removal, pay 4 life
    d += [instant('Snuff Out', 4, {'B': 1, 'generic': 3}, {'B'}, tag='snuff',
                  is_removal=True, life_cost=4)] * 1

    # ── Sorceries (8) ────────────────────────────────────────────────────────

    # Ponder
    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 4

    # Thoughtseize: discard + pay 2 life
    d += [sorcery('Thoughtseize', 1, {'B': 1}, {'B'}, tag='seize',
                  life_cost=2)] * 4

    # ── Artifacts (1) ────────────────────────────────────────────────────────

    # Mishra's Bauble: free cantrip
    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble',
                   is_cantrip=True)] * 1

    # ── Lands (20) ───────────────────────────────────────────────────────────

    # Fetch lands (10)
    d += [fetch_land('Flooded Strand', ['Island', 'Plains'])] * 2
    d += [fetch_land('Marsh Flats', ['Swamp', 'Plains'])] * 1
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 1
    d += [fetch_land('Polluted Delta', ['Island', 'Swamp'])] * 4
    d += [fetch_land('Scalding Tarn', ['Island', 'Mountain'])] * 1

    # missing one fetch? no, that's 2+1+1+4+1 = 9 fetches

    # Dual lands (4)
    d += [dual_land('Underground Sea', ['U', 'B'], ['Island', 'Swamp'])] * 4

    # Utility lands (5)
    d += [utility_land('Undercity Sewers', ['U', 'B'], 'sewers')] * 1
    d += [utility_land('Wasteland', ['C'], 'wl')] * 4

    # Basic lands (2)
    d += [basic_land('Island', 'U', 'Island')] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1

    assert len(d) == 60, f"Dimir C deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_dimir_c(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Dimir Tempo (pepeteam) strategy.

    Priority:
    1. Thoughtseize T1 to strip combo pieces / key cards
    2. Deploy threats: T1 Tamiyo, T2 Nethergoyf/Barrowgoyf/Bowmasters
    3. Murktide Regent when GY is full (delve reduces cost)
    4. Cantrip: Brainstorm/Ponder (careful about Bowmasters triggers)
    5. Removal: Fatal Push, Snuff Out (free with 4 life)
    6. Combat: attack with all non-summoning-sick creatures
    7. Brazen Borrower as flash threat (3 mana)
    """
    from config import CombatThresholds as CT
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf, cast_spell

    budget = [total_mana]

    # ── 1. Thoughtseize ─────────────────────────────────────────────────────
    seize = player.find_tag('seize')
    if seize and budget[0] >= 1:
        def _resolve_seize(c):
            player.add_to_grave(c)
            player.life -= 2
            log_fn("Thoughtseize (pay 2 life)")
            if opponent.hand:
                target = opponent.hand[0]
                opponent.hand.remove(target)
                opponent.add_to_grave(target)
                log_fn(f"  Thoughtseize takes {target.name}")
                update_goyf(gs)
        cast_spell(player, opponent, gs, seize, budget, log_fn, log_entries,
                   on_resolve=_resolve_seize)
        gs.check_life_totals()
        if gs.game_over:
            return

    # ── 2. Deploy threats ───────────────────────────────────────────────────
    deployed_threat = False

    tamiyo = player.find_tag('tamiyo')
    if tamiyo and budget[0] >= 1:
        def _resolve_tam(c):
            player.put_creature_in_play(c)
            log_fn("Tamiyo, Inquisitive Student (0/3)")
        cast_spell(player, opponent, gs, tamiyo, budget, log_fn, log_entries,
                   on_resolve=_resolve_tam)
        deployed_threat = True

    if not deployed_threat:
        bowm = player.find_tag('bowm')
        if bowm and budget[0] >= 2:
            def _resolve_bowm(c):
                player.put_creature_in_play(c)
                gs.bowmasters_on_board = True
                log_fn("Orcish Bowmasters")
                if opponent.creatures:
                    target = min(opponent.creatures, key=lambda cc: cc.toughness)
                    target.damage_marked += 1
                    log_fn(f"  Bowmasters ETB -> 1 damage to {target.card.name}")
                    gs.state_based_actions()
            cast_spell(player, opponent, gs, bowm, budget, log_fn, log_entries,
                       on_resolve=_resolve_bowm, cost_override=2)
            deployed_threat = True

    if not deployed_threat:
        for goyf_tag in ('nether', 'barro'):
            goyf = player.find_tag(goyf_tag)
            if goyf and budget[0] >= 2:
                def _resolve_goyf(c):
                    player.put_creature_in_play(c)
                    log_fn(f"{c.name}")
                    update_goyf(gs)
                cast_spell(player, opponent, gs, goyf, budget, log_fn, log_entries,
                           on_resolve=_resolve_goyf, cost_override=2)
                deployed_threat = True
                break

    if not deployed_threat:
        murk = player.find_tag('murk')
        if murk:
            gy_count = len(player.graveyard)
            delve_amount = min(gy_count, 6)
            effective_cost = max(2, 7 - delve_amount)
            if budget[0] >= effective_cost:
                exiled = 0
                while exiled < delve_amount and player.graveyard:
                    player.graveyard.pop(0)
                    exiled += 1
                def _resolve_murk(c, _e=exiled, _cost=effective_cost):
                    player.put_creature_in_play(c)
                    log_fn(f"Murktide Regent (delve {_e}, paid {_cost})")
                cast_spell(player, opponent, gs, murk, budget, log_fn, log_entries,
                           on_resolve=_resolve_murk, cost_override=effective_cost)
                deployed_threat = True

    if not deployed_threat:
        borrow = player.find_tag('borrow')
        if borrow and budget[0] >= 3:
            def _resolve_borrow(c):
                player.put_creature_in_play(c)
                log_fn("Brazen Borrower (3/1 flash flyer)")
            cast_spell(player, opponent, gs, borrow, budget, log_fn, log_entries,
                       on_resolve=_resolve_borrow, cost_override=3)

    if gs.game_over:
        return

    # ── 3. Cantrips ─────────────────────────────────────────────────────────
    # Use engine resolve_cantrip so Brainstorm correctly draws 3 + puts 2 back
    # (rather than the prior "draw 1" that halved Brainstorm's dig).
    from engine import resolve_cantrip
    for cantrip_tag in ('bs', 'ponder'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and budget[0] >= 1:
            cast_spell(player, opponent, gs, cantrip, budget, log_fn, log_entries,
                       on_resolve=lambda c: resolve_cantrip(player, c, gs, log_fn, log_entries))
            break

    bauble = player.find_tag('bauble')
    if bauble:
        def _resolve_bauble(c):
            player.add_to_grave(c)
            player.draw(1)
            log_fn("Mishra's Bauble — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            update_goyf(gs)
        cast_spell(player, opponent, gs, bauble, budget, log_fn, log_entries,
                   on_resolve=_resolve_bauble, cost_override=0)

    if gs.game_over:
        return

    # ── 4. Removal ──────────────────────────────────────────────────────────
    snuff = player.find_tag('snuff')
    if snuff and player.life > CT.SNUFF_LIFE_BUFFER:
        targets = [c for c in opponent.creatures if c.toughness <= 4]
        if targets:
            target = targets[0]
            def _resolve_snuff(c, _t=target):
                player.add_to_grave(c)
                player.life -= 4
                if _t in opponent.creatures:
                    opponent.remove_creature(_t)
                    log_fn(f"Snuff Out (pay 4 life) -> {_t.card.name}", True)
                    update_goyf(gs)
            cast_spell(player, opponent, gs, snuff, None, log_fn, log_entries,
                       on_resolve=_resolve_snuff)

    if gs.game_over:
        return

    push = player.find_tag('push')
    if push and budget[0] >= 1 and opponent.creatures:
        revolt = getattr(gs, 'revolt_active', False)
        max_cmc = 4 if revolt else 2
        push_targets = [c for c in opponent.creatures if c.card.cmc <= max_cmc]
        if push_targets:
            target = max(push_targets, key=lambda c: c.power)
            def _resolve_push(c, _t=target):
                player.add_to_grave(c)
                if _t in opponent.creatures:
                    opponent.remove_creature(_t)
                    log_fn(f"Fatal Push -> {_t.card.name}", True)
                    update_goyf(gs)
            cast_spell(player, opponent, gs, push, budget, log_fn, log_entries,
                       on_resolve=_resolve_push)

    if gs.game_over:
        return

    # ── 5. Combat ───────────────────────────────────────────────────────────

    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_dimir_c():
    """Smoke tests for Dimir Tempo C deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_dimir_c_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'barro': 1, 'borrow': 1, 'murk': 2, 'nether': 3,
        'bowm': 4, 'tamiyo': 4,
        'bs': 4, 'ponder': 4,
        'daze': 3, 'fow': 4, 'push': 4, 'snuff': 1,
        'seize': 4,
        'bauble': 1,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 22
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 20, f"Land count {land_count} != 20"
    results.append("OK  Land count = 20")

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

    # Test 9: Strategy function is callable
    assert callable(_strategy_dimir_c), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running Dimir Tempo C (pepeteam) tests...")
    for r in test_dimir_c():
        print(f"  {r}")
    print("All tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_dimir_c(hand, matchup=''):
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
    'key':        'dimir_c',
    'name':       'Dimir Tempo C (Barrowgoyf)',
    'make_deck':  make_dimir_c_deck,
    'strategy':   _strategy_dimir_c,
    'keep':       _keep_dimir_c,
    'categories': {'mirror', 'tempo_mirror', 'dimir_only', 'bowm_decks'},
    'interaction': {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.02,
}
