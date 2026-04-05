"""
UR Tempo — Legacy Delver/Tempo variant (wakarock, 4th Place).

Aggressive tempo shell built around cheap threats (DRC, Tamiyo, Cori-Steel Cutter)
backed by free countermagic (Force of Will, Daze) and efficient burn (Lightning Bolt,
Unholy Heat).  Murktide Regent closes games as a 5/5 flyer cast cheaply via delve.

Key differences from standard UR Delver:
- 4 Cori-Steel Cutter (3/1 haste) — more aggressive 2-drop
- 4 Tamiyo, Inquisitive Student — flips into planeswalker value
- No Delver of Secrets — replaced by Tamiyo + Cutter
- 4 Wasteland — mana denial tempo plan
- 3 Murktide Regent (vs 4)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import creature, instant, sorcery, artifact, fetch_land, dual_land, basic_land, utility_land
from rules import Card, CardType
from typing import List


# ─── Deck construction ────────────────────────────────────────────────────────

def make_ur_tempo_deck() -> List[Card]:
    d: List[Card] = []

    # ── Creatures (15) ───────────────────────────────────────────────────────

    # Dragon's Rage Channeler: delirium 3/3, surveil
    d += [creature("Dragon's Rage Channeler", 1, {'R': 1}, {'R'}, 3, 3,
                   tag='drc')] * 4

    # Tamiyo, Inquisitive Student: 0/3, flips into planeswalker
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U': 1}, {'U'}, 0, 3,
                   tag='tamiyo')] * 4

    # Cori-Steel Cutter: 3/1 haste, aggressive 2-drop
    d += [creature('Cori-Steel Cutter', 2, {'R': 1, 'generic': 1}, {'R'}, 3, 1,
                   tag='cutter', haste=True)] * 4

    # Murktide Regent: delve 5/5 flyer
    d += [creature('Murktide Regent', 7, {'U': 1, 'generic': 6}, {'U'}, 5, 5,
                   tag='murk', delve=True, flying=True)] * 3

    # ── Cantrips (12) ────────────────────────────────────────────────────────

    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4

    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 4

    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble',
                   is_cantrip=True)] * 4

    # ── Burn / Removal (10) ──────────────────────────────────────────────────

    d += [instant('Lightning Bolt', 1, {'R': 1}, {'R'}, tag='bolt')] * 4

    d += [instant('Unholy Heat', 1, {'R': 1}, {'R'}, tag='heat')] * 2

    # ── Counterspells (8) ────────────────────────────────────────────────────

    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4

    d += [instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'},
                  tag='daze')] * 4

    # ── Lands (19) ───────────────────────────────────────────────────────────

    d += [fetch_land('Polluted Delta', ['Island', 'Swamp'])] * 3
    d += [fetch_land('Flooded Strand', ['Island', 'Plains'])] * 2
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 2
    d += [fetch_land('Scalding Tarn', ['Island', 'Mountain'])] * 2

    d += [dual_land('Volcanic Island', ['U', 'R'], ['Island', 'Mountain'])] * 4

    d += [utility_land('Wasteland', [], 'wl')] * 4

    d += [utility_land('Thundering Falls', ['U', 'R'], 'tfall')]

    d += [basic_land('Island', 'U', 'Island')]

    assert len(d) == 60, f"UR Tempo deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_ur_tempo(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    UR Tempo strategy.

    Priority:
    1. Deploy cheap threats: T1 DRC/Tamiyo, T2 Cori-Steel Cutter (haste)
    2. Murktide Regent with delve (exile GY to reduce cost)
    3. Cantrip (Brainstorm/Ponder/Bauble) to find action
    4. Lightning Bolt — remove key creatures or burn face
    5. Unholy Heat — bigger removal (6 damage with delirium)
    6. Combat — attack with all non-summoning-sick creatures
    7. Daze / FoW held reactively (via _try_counter_any)
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf

    mana = total_mana

    # ── 1. Deploy cheap threats ──────────────────────────────────────────────

    deployed_threat = False

    # T1: DRC or Tamiyo (both 1 mana)
    for tag in ('drc', 'tamiyo'):
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

    # T2: Cori-Steel Cutter (3/1 haste — attacks immediately)
    if not deployed_threat:
        cutter = player.find_tag('cutter')
        if cutter and mana >= 2:
            player.remove_from_hand(cutter)
            if not _try_counter_any(player, opponent, gs, cutter, log_entries):
                player.put_creature_in_play(cutter)
                mana -= 2
                log_fn("Cori-Steel Cutter (3/1 haste)")
            else:
                player.add_to_grave(cutter)
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
                        card = player.graveyard.pop(0)
                        if hasattr(player, 'exile'):
                            player.exile.append(card)
                        exiled += 1
                    player.put_creature_in_play(murk)
                    mana -= effective_cost
                    log_fn(f"Murktide Regent (delve {exiled}, paid {effective_cost})")
                else:
                    player.add_to_grave(murk)
                deployed_threat = True

    # ── 2. Cantrips — find action ────────────────────────────────────────────

    # Mishra's Bauble first (free)
    bauble = player.find_tag('bauble')
    if bauble:
        player.remove_from_hand(bauble)
        player.add_to_grave(bauble)
        drawn = player.draw(1)
        log_fn("Mishra's Bauble — cantrip")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.bug else 'b')
        if gs.game_over:
            return

    for cantrip_tag in ('bs', 'ponder'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and mana >= 1:
            player.remove_from_hand(cantrip)
            player.add_to_grave(cantrip)
            mana -= 1
            drawn = player.draw(1)
            log_fn(f"{cantrip.name} — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.bug else 'b')
            if gs.game_over:
                return
            break  # one cantrip per turn

    # ── 3. Lightning Bolt — removal or face burn ─────────────────────────────

    bolt = player.find_tag('bolt')
    if bolt and mana >= 1:
        def bolt_priority(c):
            if c.card.tag == 'tamiyo':  return 0
            if c.card.tag == 'bowm':    return 1
            if c.toughness <= 3:        return 2
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
                    opponent.life -= 3
                    log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                    gs.check_life_totals()
            else:
                opponent.life -= 3
                log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                gs.check_life_totals()

    if gs.game_over:
        return

    # ── 4. Unholy Heat — bigger removal (delirium = 6 dmg) ──────────────────

    heat = player.find_tag('heat')
    if heat and mana >= 1:
        gy_types = set()
        for c in player.graveyard:
            gy_types.add(getattr(c, 'gy_type', 'unknown'))
        delirium = len(gy_types) >= 4
        heat_dmg = 6 if delirium else 2

        heat_targets = [c for c in opponent.creatures if c.toughness <= heat_dmg]
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

    # ── 5. Combat ────────────────────────────────────────────────────────────

    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_ur_tempo():
    """Smoke tests for UR Tempo deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_ur_tempo_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'drc': 4, 'tamiyo': 4, 'cutter': 4, 'murk': 3,
        'bs': 4, 'ponder': 4, 'bauble': 4,
        'bolt': 4, 'heat': 2,
        'fow': 4, 'daze': 4,
        'fetch': 9, 'dual': 4, 'wl': 4, 'tfall': 1, 'basic': 1,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 19
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 19, f"Land count {land_count} != 19"
    results.append("OK  Land count = 19")

    # Test 4: Creature count = 15
    creature_count = sum(1 for c in deck if c.card_type == CardType.CREATURE)
    assert creature_count == 15, f"Creature count {creature_count} != 15"
    results.append("OK  Creature count = 15")

    # Test 5: Spell count = 22 (instants + sorceries)
    spell_count = sum(1 for c in deck
                      if c.card_type in (CardType.INSTANT, CardType.SORCERY))
    assert spell_count == 22, f"Spell count {spell_count} != 22"
    results.append("OK  Spell count = 22")

    # Test 6: Cori-Steel Cutter has haste
    cutter = next(c for c in deck if c.tag == 'cutter')
    assert getattr(cutter, 'haste', False), "Cutter should have haste"
    results.append("OK  Cori-Steel Cutter has haste")

    # Test 7: Murktide has delve + flying
    murk = next(c for c in deck if c.tag == 'murk')
    assert getattr(murk, 'delve', False), "Murktide should have delve"
    assert getattr(murk, 'flying', False), "Murktide should have flying"
    results.append("OK  Murktide has delve + flying")

    # Test 8: FoW has free_cast_if_blue
    fow = next(c for c in deck if c.tag == 'fow')
    assert getattr(fow, 'free_cast_if_blue', False), "FoW should have free_cast_if_blue"
    results.append("OK  Force of Will is free-castable")

    # Test 9: DRC is 3/3 (delirium statline)
    drc = next(c for c in deck if c.tag == 'drc')
    assert drc.base_power == 3 and drc.base_toughness == 3, "DRC should be 3/3"
    results.append("OK  DRC is 3/3 (delirium)")

    # Test 10: Strategy function is callable
    assert callable(_strategy_ur_tempo), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running UR Tempo tests...")
    for r in test_ur_tempo():
        print(f"  {r}")
    print("All tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_ur_tempo(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder', 'bauble'))
    return 1 <= lc <= 3 and threats >= 1 and (cantrips >= 1 or len(hand) <= 5)


DECK_META = {
    'key':        'ur_tempo',
    'name':       'UR Tempo (Cori-Steel)',
    'make_deck':  make_ur_tempo_deck,
    'strategy':   _strategy_ur_tempo,
    'keep':       _keep_ur_tempo,
    'categories': {'aggro', 'tempo_mirror'},
    'meta_share': 0.03,
}
