"""
UR Delver — Legacy tempo deck.

Tempo variant of UR Aggro: more Delvers (4x), more Dazes (4x), more cantrips,
fewer burn spells.  Deploy cheap evasive threats T1, protect with free counters
(Daze, FoW), cantrip to flip Delver, Bolt to close.

Key differences from UR Aggro:
- 4 Delver of Secrets (vs 0 in aggro) — the namesake threat
- 4 Daze (vs 2) — tempo-positive on T1–3
- 2 Spell Pierce — catches early noncreature spells
- 2 Preordain — more cantrips to flip Delver
- No Ragavan, no Price of Progress
- 18 lands (vs 20) — lower curve, Daze returns Islands
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import creature, instant, sorcery, artifact, fetch_land, dual_land, basic_land
from rules import Card, CardType
from typing import List


# ─── Deck construction ────────────────────────────────────────────────────────

def make_ur_delver_deck() -> List[Card]:
    d: List[Card] = []

    # ── Creatures (14) ───────────────────────────────────────────────────────
    # Delver of Secrets: 3/2 flyer (represents flipped Insectile Aberration ~60%)
    d += [creature('Delver of Secrets', 1, {'U': 1}, {'U'}, 3, 2,
                   tag='delver', flying=True)] * 4
    # Dragon's Rage Channeler: surveil 1, delirium → 3/3
    d += [creature("Dragon's Rage Channeler", 1, {'R': 1}, {'R'}, 3, 3,
                   tag='drc')] * 4
    # Murktide Regent: delve flyer, effectively 2 mana with full GY
    d += [creature('Murktide Regent', 7, {'U': 1, 'generic': 6}, {'U'}, 5, 5,
                   tag='murk', delve=True, flying=True)] * 4
    # Brazen Borrower: flash flyer, bounces a permanent (Petty Theft)
    d += [creature('Brazen Borrower', 3, {'U': 1, 'generic': 2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 2

    # ── Burn / Removal (6) ───────────────────────────────────────────────────
    d += [instant('Lightning Bolt', 1, {'R': 1}, {'R'}, tag='bolt')] * 4
    d += [instant('Unholy Heat', 1, {'R': 1}, {'R'}, tag='heat')] * 2

    # ── Cantrips (10) ────────────────────────────────────────────────────────
    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 4
    d += [sorcery('Preordain', 1, {'U': 1}, {'U'}, tag='pre',
                  is_cantrip=True)] * 2

    # ── Counterspells (10) ───────────────────────────────────────────────────
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'},
                  tag='daze')] * 4
    d += [instant('Spell Pierce', 1, {'U': 1}, {'U'},
                  tag='pierce')] * 2

    # ── Card Advantage (2) ───────────────────────────────────────────────────
    d += [sorcery('Expressive Iteration', 2, {'U': 1, 'R': 1}, {'U', 'R'},
                  tag='ei')] * 2

    # ── Lands (18) ───────────────────────────────────────────────────────────
    d += [fetch_land('Scalding Tarn', ['Island', 'Mountain'])] * 4
    d += [fetch_land('Polluted Delta', ['Island', 'Swamp'])] * 2
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 2
    d += [dual_land('Volcanic Island', ['U', 'R'], ['Island', 'Mountain'])] * 4
    d += [dual_land('Steam Vents', ['U', 'R'], ['Island', 'Mountain'],
                    tag='dual')] * 2
    d += [basic_land('Island', 'U', 'Island')] * 2
    d += [basic_land('Mountain', 'R', 'Mountain')] * 2

    assert len(d) == 60, f"UR Delver deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_ur_delver(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    UR Delver tempo strategy.

    Priority:
    1. Deploy cheap threats (Delver T1, DRC T1, Murktide T2+ with delve)
    2. Cantrip to flip Delver and find action
    3. Lightning Bolt / Unholy Heat removal or face burn
    4. Expressive Iteration for card advantage mid-game
    5. Combat — attack with all non-summoning-sick creatures
    6. Daze / FoW held reactively (via _try_counter_any)
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare
    from engine import update_goyf, opp_can_cast

    mana = total_mana

    # ── 1. Deploy threats ────────────────────────────────────────────────────

    # Delver of Secrets — best T1 play (3/2 flyer)
    deployed_threat = False
    for tag in ('delver', 'drc'):
        threat = player.find_tag(tag)
        if threat and mana >= 1:
            player.remove_from_hand(threat)
            if not _try_counter_any(player, opponent, gs, threat, log_entries):
                player.put_creature_in_play(threat)
                mana -= 1
                log_fn(f"{threat.name}")
            else:
                player.add_to_grave(threat)
            deployed_threat = True
            break

    # Murktide Regent — delve makes it effectively 2 mana with 5+ cards in GY
    if not deployed_threat:
        murk = player.find_tag('murk')
        if murk:
            gy_count = len(player.graveyard)
            # Delve: exile up to (cmc - U cost) cards from GY to reduce generic cost
            # Murktide is {1}{U} base, but Card has cmc=7; delve exiles up to 6
            delve_amount = min(gy_count, 6)
            effective_cost = max(2, 7 - delve_amount)  # always need at least {1}{U}
            if mana >= effective_cost:
                player.remove_from_hand(murk)
                if not _try_counter_any(player, opponent, gs, murk, log_entries):
                    # Exile cards from GY for delve
                    exiled = 0
                    while exiled < delve_amount and player.graveyard:
                        card = player.graveyard.pop(0)
                        player.exile.append(card) if hasattr(player, 'exile') else None
                        exiled += 1
                    player.put_creature_in_play(murk)
                    mana -= effective_cost
                    log_fn(f"Murktide Regent (delve {exiled}, paid {effective_cost})")
                else:
                    player.add_to_grave(murk)
                deployed_threat = True

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

    # ── 2. Cantrips — flip Delver, find action ──────────────────────────────

    for cantrip_tag in ('bs', 'ponder', 'pre'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and mana >= 1:
            player.remove_from_hand(cantrip)
            player.add_to_grave(cantrip)
            mana -= 1
            drawn = player.draw(1)
            log_fn(f"{cantrip.name} — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            break  # one cantrip per turn is usually enough

    # ── 3. Expressive Iteration — card advantage (T3+) ─────────────────────

    ei = player.find_tag('ei')
    if ei and mana >= 2:
        player.remove_from_hand(ei)
        player.add_to_grave(ei)
        mana -= 2
        drawn = player.draw(1)
        log_fn("Expressive Iteration — draw + exile selection")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')

    # ── 4. Lightning Bolt — removal or face burn ────────────────────────────

    bolt = player.find_tag('bolt')
    if bolt and mana >= 1:
        # Priority targets for removal
        def bolt_priority(c):
            if c.card.tag == 'tamiyo':  return 0   # must kill before flip
            if c.card.tag == 'bowm':    return 1   # shuts down cantrips
            if c.toughness <= 3:        return 2   # Bolt range
            return 99

        candidates = [c for c in opponent.creatures if bolt_priority(c) < 99]
        target = min(candidates, key=bolt_priority) if candidates else None
        go_face = (target is None
                   and opponent.life <= 9
                   and len(player.creatures) > 0)

        if target or go_face:
            player.remove_from_hand(bolt)
            player.add_to_grave(bolt)
            mana -= 1
            if target:
                if target.toughness <= 3:
                    opponent.remove_creature(target)
                    log_fn(f"Lightning Bolt -> {target.card.name}", True)
                    update_goyf(gs)
                else:
                    # 3 damage not enough to kill; go face instead
                    opponent.life -= 3
                    log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                    gs.check_life_totals()
            else:
                opponent.life -= 3
                log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                gs.check_life_totals()

    if gs.game_over:
        return

    # ── 5. Unholy Heat — bigger removal (delirium = 6 dmg) ─────────────────

    heat = player.find_tag('heat')
    if heat and mana >= 1:
        # Count card types in GY for delirium
        gy_types = set()
        for c in player.graveyard:
            gy_types.add(getattr(c, 'gy_type', 'unknown'))
        delirium = len(gy_types) >= 4
        heat_dmg = 6 if delirium else 2

        # Only use Heat on creatures that need it
        heat_targets = [c for c in opponent.creatures if c.toughness <= heat_dmg]
        # Prefer big targets that Bolt can't handle
        heat_targets.sort(key=lambda c: -c.toughness)

        if heat_targets:
            target = heat_targets[0]
            player.remove_from_hand(heat)
            player.add_to_grave(heat)
            mana -= 1
            opponent.remove_creature(target)
            log_fn(f"Unholy Heat ({heat_dmg} dmg) -> {target.card.name}", True)
            update_goyf(gs)

    if gs.game_over:
        return

    # ── 6. Combat ────────────────────────────────────────────────────────────

    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_ur_delver():
    """Smoke tests for UR Delver deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_ur_delver_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'delver': 4, 'drc': 4, 'murk': 4, 'borrow': 2,
        'bolt': 4, 'heat': 2,
        'bs': 4, 'ponder': 4, 'pre': 2,
        'fow': 4, 'daze': 4, 'pierce': 2,
        'ei': 2,
        'fetch': 8, 'dual': 6, 'basic': 4,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 18
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 18, f"Land count {land_count} != 18"
    results.append("OK  Land count = 18")

    # Test 4: Creature count = 14
    creature_count = sum(1 for c in deck if c.card_type == CardType.CREATURE)
    assert creature_count == 14, f"Creature count {creature_count} != 14"
    results.append("OK  Creature count = 14")

    # Test 5: Spell count = 28 (instants + sorceries)
    spell_count = sum(1 for c in deck
                      if c.card_type in (CardType.INSTANT, CardType.SORCERY))
    assert spell_count == 28, f"Spell count {spell_count} != 28"
    results.append("OK  Spell count = 28")

    # Test 6: Delver has flying
    delver = next(c for c in deck if c.tag == 'delver')
    assert getattr(delver, 'flying', False), "Delver should have flying"
    results.append("OK  Delver has flying")

    # Test 7: Murktide has delve + flying
    murk = next(c for c in deck if c.tag == 'murk')
    assert getattr(murk, 'delve', False), "Murktide should have delve"
    assert getattr(murk, 'flying', False), "Murktide should have flying"
    results.append("OK  Murktide has delve + flying")

    # Test 8: FoW has free_cast_if_blue
    fow = next(c for c in deck if c.tag == 'fow')
    assert getattr(fow, 'free_cast_if_blue', False), "FoW should have free_cast_if_blue"
    results.append("OK  Force of Will is free-castable")

    # Test 9: Strategy function is callable
    assert callable(_strategy_ur_delver), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running UR Delver tests...")
    for r in test_ur_delver():
        print(f"  {r}")
    print("All tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_ur_delver(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder', 'pre'))
    return 1 <= lc <= 3 and threats >= 1 and (cantrips >= 1 or len(hand) <= 5)


DECK_META = {
    'key':        'ur_delver',
    'name':       'UR Delver',
    'make_deck':  make_ur_delver_deck,
    'strategy':   _strategy_ur_delver,
    'keep':       _keep_ur_delver,
    'categories': {'aggro', 'tempo_mirror'},
    'interaction': {'speed': 2, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'bug_answers': 8},
    'meta_share': 0.04,
}
