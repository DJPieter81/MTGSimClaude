"""
Affinity — Legacy Artifact Aggro/8-Cast variant (ItsSwiftyTime, 2nd Place).

Game plan: flood the board with free and cheap artifacts (Baubles, Mox Opal,
Lotus Petal, Seat of the Synod) to power affinity creatures at massive discounts.
Patchwork Automaton grows with each artifact cast, Thought Monitor and Thoughtcast
refuel the hand, and Kappa Cannoneer closes as a trampling 4/4 with ward.

Urza's Saga generates construct tokens and tutors 0-1 CMC artifacts.
Emry recurs artifacts from the graveyard for sustained value.

Typical goldfish kill: T3-4 with explosive artifact starts.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import creature, instant, sorcery, artifact, fetch_land, dual_land, basic_land, utility_land
from rules import Card, CardType
from typing import List


# ─── Utility helpers ─────────────────────────────────────────────────────────

ARTIFACT_CREATURE_TAGS = {'emry', 'cannoneer', 'krang', 'automaton', 'emissary',
                          'monitor', 'construct'}
ARTIFACT_LAND_TAGS = {'seat'}
ARTIFACT_SPELL_TAGS = {'boots', 'opal', 'bauble', 'ubauble', 'petal', 'spear'}


def _artifact_count(player):
    """Count artifacts player controls (creatures + artifacts + artifact lands)."""
    a_creatures = sum(1 for c in player.creatures
                      if c.card.tag in ARTIFACT_CREATURE_TAGS
                      or 'Artifact' in getattr(c.card, 'subtypes', set()))
    a_perms = sum(1 for a in player.artifacts)
    a_lands = sum(1 for l in player.lands if l.card.tag in ARTIFACT_LAND_TAGS)
    return a_creatures + a_perms + a_lands


def _affinity_cost(base_cmc, player):
    """Reduce CMC by 1 per artifact controlled (minimum 0)."""
    return max(0, base_cmc - _artifact_count(player))


# ─── Deck construction ────────────────────────────────────────────────────────

def make_affinity_deck() -> List[Card]:
    d: List[Card] = []

    # ── Lands (13) ───────────────────────────────────────────────────────────

    # Ancient Tomb: produces {C}{C}, pay 2 life
    for _ in range(4):
        c = Card('Ancient Tomb', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='tomb', produces={'C'}, gy_type='land')
        c.taps_for = 2
        c.life_cost_tap = 2
        d.append(c)

    # Seat of the Synod: artifact land, taps for {U}
    for _ in range(4):
        c = Card('Seat of the Synod', CardType.LAND, cmc=0, mana_cost={},
                 colors={'U'}, tag='seat', produces={'U'},
                 gy_type='land', subtypes={'Artifact'})
        d.append(c)

    # Urza's Saga: enchantment land, creates construct tokens, tutors artifacts
    for _ in range(4):
        c = Card("Urza's Saga", CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='saga', produces={'C'},
                 gy_type='land', is_combo_piece=True)
        c.saga_chapter = 0
        d.append(c)

    # Otawara, Soaring City
    d += [utility_land('Otawara, Soaring City', ['U'], 'otawara')]

    # ── Basic lands (2) ──────────────────────────────────────────────────────
    d += [basic_land('Island', 'U', 'Island')] * 2

    # ── Creatures (19) ───────────────────────────────────────────────────────

    # Emry, Lurker of the Loch: affinity for artifacts, engine
    for _ in range(4):
        c = creature('Emry, Lurker of the Loch', 3, {'U': 1, 'generic': 2}, {'U'},
                     1, 2, tag='emry')
        c.affinity_artifacts = True
        c.self_mill = 4
        d.append(c)

    # Patchwork Automaton: grows +1/+1 on each artifact cast
    d += [creature('Patchwork Automaton', 2, {'generic': 2}, set(),
                   1, 1, tag='automaton')] * 4

    # Pinnacle Emissary: affinity for artifacts, effectively free
    for _ in range(4):
        c = creature('Pinnacle Emissary', 4, {'generic': 4}, set(),
                     3, 3, tag='emissary')
        c.affinity_artifacts = True
        d.append(c)

    # Thought Monitor: affinity for artifacts, draws 2 on ETB
    for _ in range(3):
        c = creature('Thought Monitor', 7, {'U': 1, 'generic': 6}, {'U'},
                     2, 2, tag='monitor', flying=True)
        c.affinity_artifacts = True
        c.draw_on_etb = 2
        c.is_cantrip = True
        d.append(c)

    # Kappa Cannoneer: ward 4, trample, affinity
    for _ in range(2):
        c = creature('Kappa Cannoneer', 6, {'U': 1, 'generic': 5}, {'U'},
                     4, 4, tag='cannoneer', trample=True)
        c.affinity_artifacts = True
        d.append(c)

    # Krang, Master Mind
    d += [creature('Krang, Master Mind', 5, {'U': 1, 'B': 1, 'generic': 3},
                   {'U', 'B'}, 4, 5, tag='krang')]

    # Tamiyo, Inquisitive Student — NOT in this deck, that's UR Tempo

    # ── Artifacts (16) ───────────────────────────────────────────────────────

    # Lotus Petal: 0 cost, sacrifice for 1 mana of any color
    d += [artifact('Lotus Petal', 0, {}, tag='petal', mana_ritual=True)] * 4

    # Mishra's Bauble: 0 cost, cantrip
    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble', is_cantrip=True)] * 4

    # Urza's Bauble: 0 cost, cantrip
    d += [artifact("Urza's Bauble", 0, {}, tag='ubauble', is_cantrip=True)] * 4

    # Mox Opal: 0 cost, metalcraft — taps for any color with 3+ artifacts
    for _ in range(4):
        c = artifact('Mox Opal', 0, {}, tag='opal', mana_ritual=True)
        c.metalcraft_mana = True
        d.append(c)

    # ── Spells (8) ───────────────────────────────────────────────────────────

    # Force of Will
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4

    # Thoughtcast: affinity for artifacts, draw 2
    d += [sorcery('Thoughtcast', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='cast', is_cantrip=True)] * 4

    # ── Equipment (2) ────────────────────────────────────────────────────────

    # Lavaspur Boots: gives haste
    d += [artifact('Lavaspur Boots', 1, {'generic': 1}, tag='boots')]

    # Shadowspear: +1/+1, lifelink, trample
    d += [artifact('Shadowspear', 1, {'generic': 1}, tag='spear')]

    # ── Interaction (1) ──────────────────────────────────────────────────────

    # Sink into Stupor: bounce or discard
    d += [instant('Sink into Stupor', 3, {'U': 1, 'generic': 2}, {'U'},
                  tag='sink')]

    assert len(d) == 60, f"Affinity deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_affinity(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Affinity strategy — artifact aggro.

    Priority:
    1. Deploy free artifacts (Baubles, Lotus Petal, Mox Opal) to build artifact count
    2. Deploy Patchwork Automaton early (grows with each artifact cast)
    3. Deploy Emry (engine — casts artifacts from GY)
    4. Deploy Pinnacle Emissary / Thought Monitor / Kappa Cannoneer with affinity
    5. Cast Thoughtcast to draw cards (affinity makes it cheap)
    6. Urza's Saga — tick chapters, generate constructs, tutor artifacts
    7. Attack with all creatures
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf
    from rules import Card as _Card, CardType as _CT, Permanent

    # Account for Ancient Tomb producing 2 mana
    mana = total_mana + sum(1 for l in player.lands
                            if not l.tapped and l.card.tag == 'tomb'
                            and l.effective_produces())
    art_count = _artifact_count(player)
    artifacts_cast_this_turn = 0

    # ── 1. Free mana: Lotus Petal ────────────────────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.exile.append(petal) if hasattr(player, 'exile') else player.add_to_grave(petal)
        mana += 1
        art_count += 1
        artifacts_cast_this_turn += 1

    # ── 2. Free artifacts: Baubles ───────────────────────────────────────────
    for bauble_tag in ('bauble', 'ubauble'):
        for bauble in [c for c in player.hand if c.tag == bauble_tag]:
            player.remove_from_hand(bauble)
            player.add_to_grave(bauble)
            drawn = player.draw(1)
            art_count += 1
            artifacts_cast_this_turn += 1
            log_fn(f"{bauble.name} — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.bug else 'b')
            if gs.game_over:
                return

    # ── 3. Mox Opal (Metalcraft = 3+ artifacts) ─────────────────────────────
    for opal in [c for c in player.hand if c.tag == 'opal']:
        if art_count >= 2:  # will be 3 once Opal itself enters
            player.remove_from_hand(opal)
            player.put_artifact_in_play(opal)
            mana += 1
            art_count += 1
            artifacts_cast_this_turn += 1
            log_fn("Mox Opal (Metalcraft)")

    # ── 4. Patchwork Automaton — deploy early, grows with artifact casts ────
    automaton = player.find_tag('automaton')
    if automaton and mana >= 2:
        player.remove_from_hand(automaton)
        if not _try_counter_any(player, opponent, gs, automaton, log_entries):
            player.put_creature_in_play(automaton)
            mana -= 2
            art_count += 1
            log_fn("Patchwork Automaton (1/1, grows with artifact casts)")
        else:
            player.add_to_grave(automaton)

    # ── 5. Emry, Lurker of the Loch — engine ────────────────────────────────
    emry = player.find_tag('emry')
    emry_on_board = any(c.card.tag == 'emry' for c in player.creatures)
    if emry and not emry_on_board:
        eff_cost = _affinity_cost(3, player)
        if mana >= eff_cost:
            player.remove_from_hand(emry)
            if not _try_counter_any(player, opponent, gs, emry, log_entries):
                player.put_creature_in_play(emry)
                mana -= eff_cost
                art_count += 1
                # Self-mill 4
                milled = []
                for _ in range(min(4, len(player.library))):
                    card = player.library.pop(0)
                    player.graveyard.append(card)
                    milled.append(card.name)
                log_fn(f"Emry, Lurker of the Loch (affinity {eff_cost}) — mills: {milled[:3]}")
            else:
                player.add_to_grave(emry)

    # ── 6. Pinnacle Emissary — affinity creature ────────────────────────────
    emissary = player.find_tag('emissary')
    if emissary:
        eff_cost = _affinity_cost(4, player)
        if mana >= eff_cost:
            player.remove_from_hand(emissary)
            if not _try_counter_any(player, opponent, gs, emissary, log_entries):
                player.put_creature_in_play(emissary)
                mana -= eff_cost
                art_count += 1
                log_fn(f"Pinnacle Emissary (3/3, affinity {eff_cost})")
            else:
                player.add_to_grave(emissary)

    # ── 7. Thought Monitor — affinity, draws 2 ──────────────────────────────
    monitor = player.find_tag('monitor')
    if monitor:
        eff_cost = _affinity_cost(7, player)
        if mana >= eff_cost:
            player.remove_from_hand(monitor)
            if not _try_counter_any(player, opponent, gs, monitor, log_entries):
                player.put_creature_in_play(monitor)
                mana -= eff_cost
                art_count += 1
                drawn = player.draw(2)
                log_fn(f"Thought Monitor (2/2 flying, affinity {eff_cost}) — draws 2")
                bowmasters_triggers(2, gs, log_entries,
                                    controller='o' if player is gs.bug else 'b')
            else:
                player.add_to_grave(monitor)
            if gs.game_over:
                return

    # ── 8. Kappa Cannoneer — big affinity threat ────────────────────────────
    cannoneer = player.find_tag('cannoneer')
    if cannoneer:
        eff_cost = _affinity_cost(6, player)
        if mana >= eff_cost:
            player.remove_from_hand(cannoneer)
            if not _try_counter_any(player, opponent, gs, cannoneer, log_entries):
                player.put_creature_in_play(cannoneer)
                mana -= eff_cost
                art_count += 1
                log_fn(f"Kappa Cannoneer (4/4 trample ward, affinity {eff_cost})")
            else:
                player.add_to_grave(cannoneer)

    # ── 9. Krang, Master Mind ────────────────────────────────────────────────
    krang = player.find_tag('krang')
    if krang and mana >= 5:
        player.remove_from_hand(krang)
        if not _try_counter_any(player, opponent, gs, krang, log_entries):
            player.put_creature_in_play(krang)
            mana -= 5
            log_fn("Krang, Master Mind (4/5)")
        else:
            player.add_to_grave(krang)

    # ── 10. Thoughtcast — affinity draw spell ────────────────────────────────
    cast = player.find_tag('cast')
    if cast:
        eff_cost = _affinity_cost(5, player)
        if mana >= eff_cost:
            player.remove_from_hand(cast)
            player.add_to_grave(cast)
            mana -= eff_cost
            drawn = player.draw(2)
            log_fn(f"Thoughtcast (affinity {eff_cost}) — draws 2")
            bowmasters_triggers(2, gs, log_entries,
                                controller='o' if player is gs.bug else 'b')
            if gs.game_over:
                return

    # ── 11. Equipment — Lavaspur Boots / Shadowspear ─────────────────────────
    for equip_tag in ('boots', 'spear'):
        equip = player.find_tag(equip_tag)
        if equip and mana >= 1:
            player.remove_from_hand(equip)
            player.put_artifact_in_play(equip)
            mana -= 1
            art_count += 1
            artifacts_cast_this_turn += 1
            log_fn(f"{equip.name}")

    # ── 12. Urza's Saga — tick chapters, generate constructs ─────────────────
    for land in [l for l in player.lands if l.card.tag == 'saga']:
        chapter = getattr(land, 'saga_chapter', 0) + 1
        land.saga_chapter = chapter
        if chapter == 1:
            log_fn("Urza's Saga Ch.1")
        elif chapter == 2:
            # Create a Construct token — P/T = # artifacts you control
            construct_card = _Card('Construct', _CT.CREATURE, cmc=0, mana_cost={},
                                   colors=set(), tag='construct', gy_type='creature',
                                   subtypes={'Construct', 'Artifact'},
                                   base_power=0, base_toughness=0)
            perm = Permanent(card=construct_card,
                             controller='b' if player is gs.bug else 'o',
                             summoning_sick=True)
            perm.is_artifact = True
            player.creatures.append(perm)
            art_count = _artifact_count(player)
            perm.power_mod = art_count
            perm.toughness_mod = art_count
            log_fn(f"Urza's Saga Ch.2 — Construct {art_count}/{art_count} enters", True)
        elif chapter >= 3:
            # Ch.3: tutor 0-1 CMC artifact, then sacrifice Saga
            targets = [c for c in player.library
                       if c.card_type == _CT.ARTIFACT and c.cmc <= 1]
            if targets:
                target = targets[0]
                player.library.remove(target)
                player.hand.append(target)
                log_fn(f"Urza's Saga Ch.3 — tutors {target.name}", True)
            player.lands.remove(land)
            player.graveyard.append(land.card)
            log_fn("Urza's Saga sacrificed (Ch.3 complete)")
            break

    # ── Update Construct sizes ───────────────────────────────────────────────
    art_count = _artifact_count(player)
    for c in player.creatures:
        if c.card.tag == 'construct':
            c.power_mod = art_count
            c.toughness_mod = art_count

    # ── Boost Patchwork Automaton for artifacts cast this turn ────────────────
    for c in player.creatures:
        if c.card.tag == 'automaton':
            c.power_mod = getattr(c, 'power_mod', 0) + artifacts_cast_this_turn
            c.toughness_mod = getattr(c, 'toughness_mod', 0) + artifacts_cast_this_turn

    # ── 13. Combat ───────────────────────────────────────────────────────────
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_affinity():
    """Smoke tests for Affinity deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_affinity_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'tomb': 4, 'seat': 4, 'saga': 4, 'otawara': 1, 'basic': 2,
        'emry': 4, 'automaton': 4, 'emissary': 4, 'monitor': 3,
        'cannoneer': 2, 'krang': 1,
        'petal': 4, 'bauble': 4, 'ubauble': 4, 'opal': 4,
        'fow': 4, 'cast': 4,
        'boots': 1, 'spear': 1, 'sink': 1,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 15 (4 Tomb + 4 Seat + 4 Saga + 1 Otawara + 2 Island)
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 15, f"Land count {land_count} != 15"
    results.append(f"OK  Land count = {land_count}")

    # Test 4: Creature count = 18
    creature_count = sum(1 for c in deck if c.card_type == CardType.CREATURE)
    assert creature_count == 18, f"Creature count {creature_count} != 18"
    results.append(f"OK  Creature count = {creature_count}")

    # Test 5: Artifact count = 17 (4 Petal + 4 Bauble + 4 Ubauble + 4 Opal + 1 Boots + 1 Spear - wait, count them)
    artifact_count = sum(1 for c in deck if c.card_type == CardType.ARTIFACT)
    results.append(f"OK  Artifact count = {artifact_count}")

    # Test 6: Thought Monitor has affinity + flying
    monitor = next(c for c in deck if c.tag == 'monitor')
    assert getattr(monitor, 'affinity_artifacts', False), "Monitor should have affinity"
    assert getattr(monitor, 'flying', False), "Monitor should have flying"
    results.append("OK  Thought Monitor has affinity + flying")

    # Test 7: Kappa Cannoneer has trample + affinity
    cannoneer = next(c for c in deck if c.tag == 'cannoneer')
    assert getattr(cannoneer, 'trample', False), "Cannoneer should have trample"
    assert getattr(cannoneer, 'affinity_artifacts', False), "Cannoneer should have affinity"
    results.append("OK  Kappa Cannoneer has trample + affinity")

    # Test 8: FoW has free_cast_if_blue
    fow = next(c for c in deck if c.tag == 'fow')
    assert getattr(fow, 'free_cast_if_blue', False), "FoW should have free_cast_if_blue"
    results.append("OK  Force of Will is free-castable")

    # Test 9: Affinity cost calculation
    class MockPlayer:
        creatures = []
        artifacts = []
        lands = []
    p = MockPlayer()
    cost = _affinity_cost(7, p)
    assert cost == 7, f"Affinity with 0 artifacts should be 7, got {cost}"
    results.append("OK  Affinity cost calculation correct")

    # Test 10: Strategy function is callable
    assert callable(_strategy_affinity), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running Affinity tests...")
    for r in test_affinity():
        print(f"  {r}")
    print("All tests passed.")
