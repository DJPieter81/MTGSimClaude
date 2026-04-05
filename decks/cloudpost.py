"""
Cloudpost / 12-Post — Legacy big-mana ramp deck (TrueFuturism, 7th Place).

The deck exploits the Locus subtype shared by Cloudpost, Glimmerpost, and
Planar Nexus.  Each Cloudpost taps for {C} equal to the number of Loci in
play, so with four Loci each Cloudpost produces four mana.  Urza Tron lands
(Mine/Plant/Tower) provide additional bonus mana.

The ramp feeds expensive haymakers:
  - Karn, the Great Creator (lock + wish for artifacts)
  - The One Ring (protection + card draw engine)
  - Ugin, Eye of the Storms (board wipe)
  - Ulamog, the Ceaseless Hunger (exile permanents, 10/10 finisher)

Crop Rotation and Expedition Map tutor for the key lands, while Lotus Petal
accelerates the early turns.  Disruptor Flute and Pithing Needle provide
cheap lock pieces against opposing combo and planeswalkers.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import (creature, instant, sorcery, artifact, enchantment,
                   planeswalker, fetch_land, dual_land, basic_land, utility_land)
from rules import Card, CardType


# ─── Deck construction ────────────────────────────────────────────────────────

def make_cloudpost_deck():
    d = []

    # ── Lands (26) ──────────────────────────────────────────────────────────

    # Cloudpost (4) — Locus, taps for 1 per Locus in play
    for _ in range(4):
        d.append(utility_land('Cloudpost', ['C'], 'post', is_combo_piece=True))

    # Glimmerpost (2) — Locus, ETB gain 1 life per Locus
    for _ in range(2):
        d.append(utility_land('Glimmerpost', ['C'], 'glimmer'))

    # Planar Nexus (4) — counts as every land type (is a Locus)
    for _ in range(4):
        d.append(utility_land('Planar Nexus', ['C'], 'nexus'))

    # Urza's Tower (4) — with Tron: taps for 3
    for _ in range(4):
        d.append(utility_land("Urza's Tower", ['C'], 'tower'))

    # Urza's Mine (2) — with Tron: taps for 2
    for _ in range(2):
        d.append(utility_land("Urza's Mine", ['C'], 'mine'))

    # Urza's Power Plant (2) — with Tron: taps for 2
    for _ in range(2):
        d.append(utility_land("Urza's Power Plant", ['C'], 'plant'))

    # Bojuka Bog (1) — ETB exile target graveyard
    d.append(utility_land('Bojuka Bog', ['B'], 'bog'))

    # Boseiju, Who Endures (2) — channel: destroy artifact/enchantment
    for _ in range(2):
        d.append(utility_land('Boseiju, Who Endures', ['G'], 'boseiju'))

    # Karakas (1) — bounces legendary creatures
    d.append(utility_land('Karakas', ['W'], 'karakas'))

    # Otawara, Soaring City (1) — channel: bounce nonland permanent
    d.append(utility_land('Otawara, Soaring City', ['U'], 'otawara'))

    # Basic lands (2)
    d.append(basic_land('Forest', 'G', 'Forest'))
    d.append(basic_land('Island', 'U', 'Island'))

    # ── Fast Mana (4) ──────────────────────────────────────────────────────
    for _ in range(4):
        d.append(artifact('Lotus Petal', 0, {}, tag='petal', mana_ritual=True))

    # ── Land Tutors (6) ────────────────────────────────────────────────────

    # Crop Rotation (4) — sac a land, tutor any land to play
    for _ in range(4):
        d.append(instant('Crop Rotation', 1, {'G': 1}, {'G'}, tag='crop',
                         is_combo_piece=True))

    # Expedition Map (2) — 1 to cast, 2 to activate: tutor any land
    for _ in range(2):
        d.append(artifact('Expedition Map', 1, {'generic': 1}, tag='map'))

    # ── Lock Pieces (6) ────────────────────────────────────────────────────

    # Disruptor Flute (4) — names a card, opponent can't cast it
    for _ in range(4):
        d.append(artifact('Disruptor Flute', 2, {'generic': 2}, tag='flute'))

    # Pithing Needle (2) — names a card, shuts down activated abilities
    for _ in range(2):
        d.append(artifact('Pithing Needle', 1, {'generic': 1}, tag='needle'))

    # ── Card Draw (4) ──────────────────────────────────────────────────────

    # Stock Up (4) — draw 2
    for _ in range(4):
        d.append(instant('Stock Up', 2, {'U': 1, 'generic': 1}, {'U'},
                         tag='stock', is_cantrip=True))

    # ── Threats / Engines (15) ─────────────────────────────────────────────

    # Karn, the Great Creator (4)
    for _ in range(4):
        d.append(planeswalker('Karn, the Great Creator', 4,
                              {'generic': 4}, set(), tag='karn'))

    # Kozilek's Command (4) — modal instant
    for _ in range(4):
        d.append(instant("Kozilek's Command", 4, {'generic': 4}, set(),
                         tag='koz_cmd'))

    # The One Ring (3) — protection + card draw engine
    for _ in range(3):
        d.append(artifact('The One Ring', 4, {'generic': 4}, tag='ring'))

    # Ugin, Eye of the Storms (3) — board wipe / removal
    for _ in range(3):
        d.append(planeswalker('Ugin, Eye of the Storms', 6,
                              {'generic': 6}, set(), tag='ugin'))

    # Ulamog, the Ceaseless Hunger (1) — 10/10 indestructible finisher
    d.append(creature('Ulamog, the Ceaseless Hunger', 10,
                      {'generic': 10}, set(), 10, 10, tag='ulamog',
                      win_condition=True))

    assert len(d) == 60, f"Cloudpost deck: {len(d)} cards (expected 60)"
    return d


# ─── Mana helpers ────────────────────────────────────────────────────────────

def _calc_effective_mana(player, base_mana):
    """
    Calculate effective mana including Locus and Tron bonuses.

    Cloudpost taps for 1 mana per Locus in play (including itself).
    Tron bonus: Mine +1, Plant +1, Tower +2 above their base of 1.
    """
    locus_count = sum(1 for l in player.lands
                      if l.card.tag in ('post', 'glimmer', 'nexus'))
    cloudpost_extra = sum(max(0, locus_count - 1)
                          for l in player.lands if l.card.tag == 'post')

    has_mine = any(l.card.tag == 'mine' for l in player.lands)
    has_plant = any(l.card.tag == 'plant' for l in player.lands)
    has_tower = any(l.card.tag == 'tower' for l in player.lands)
    tron_active = has_mine and has_plant and has_tower

    tron_extra = 0
    if tron_active:
        tron_extra += sum(1 for l in player.lands if l.card.tag == 'mine')
        tron_extra += sum(1 for l in player.lands if l.card.tag == 'plant')
        tron_extra += sum(2 for l in player.lands if l.card.tag == 'tower')

    return base_mana + cloudpost_extra + tron_extra


# ─── Strategy ────────────────────────────────────────────────────────────────

def _strategy_cloudpost(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Cloudpost / 12-Post strategy — ramp into expensive haymakers.

    Priority:
     1. Lotus Petal for early mana acceleration
     2. Expedition Map (cast early, activate later to find Cloudpost / Tron)
     3. Crop Rotation — instant-speed land tutor for Cloudpost
     4. Lock pieces (Disruptor Flute, Pithing Needle) to slow opponent
     5. Karn, the Great Creator (4 mana) — wish for artifacts
     6. The One Ring (4 mana) — protection + card draw
     7. Stock Up / Kozilek's Command — card draw / interaction
     8. Ugin (6 mana) — board wipe for colored creatures
     9. Ulamog (10 mana) — ultimate finisher, exile 2 permanents
    10. Combat with any creatures
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf

    mana = _calc_effective_mana(player, total_mana)

    # ── Lotus Petal — free ramp ─────────────────────────────────────────────
    petal = player.find_tag('petal')
    if petal:
        player.remove_from_hand(petal)
        player.add_to_grave(petal)
        mana += 1
        log_fn("Lotus Petal → +1 mana")

    # ── Expedition Map (1 mana to cast) ─────────────────────────────────────
    exp_map = player.find_tag('map')
    if exp_map and mana >= 1:
        player.remove_from_hand(exp_map)
        player.add_to_grave(exp_map)
        mana -= 1
        # Simplified: immediate activation (2 mana) if affordable
        if mana >= 2:
            mana -= 2
            # Tutor best land from library
            target = (
                next((c for c in player.library if c.tag == 'post'), None)
                or next((c for c in player.library
                         if c.tag in ('tower', 'mine', 'plant', 'nexus')), None)
            )
            if target:
                player.library.remove(target)
                player.hand.append(target)
                log_fn(f"Expedition Map → {target.name} to hand")
            else:
                log_fn("Expedition Map — no useful land in library")
        else:
            log_fn("Expedition Map cast (will activate later)")

    # ── Lock pieces — Pithing Needle (1 mana), Disruptor Flute (2 mana) ────
    needle = player.find_tag('needle')
    if needle and mana >= 1:
        player.remove_from_hand(needle)
        if not _try_counter_any(player, opponent, gs, needle, log_entries):
            player.add_to_grave(needle)
            mana -= 1
            log_fn("Pithing Needle — naming key card", True)
        else:
            player.add_to_grave(needle)
            mana -= 1

    flute = player.find_tag('flute')
    if flute and mana >= 2:
        player.remove_from_hand(flute)
        if not _try_counter_any(player, opponent, gs, flute, log_entries):
            player.add_to_grave(flute)
            mana -= 2
            log_fn("Disruptor Flute — naming key card", True)
        else:
            player.add_to_grave(flute)
            mana -= 2

    # ── Karn, the Great Creator (4 mana) ────────────────────────────────────
    karn = player.find_tag('karn')
    if karn and mana >= 4:
        player.remove_from_hand(karn)
        if not _try_counter_any(player, opponent, gs, karn, log_entries):
            player.add_to_grave(karn)
            mana -= 4
            log_fn("★ Karn, the Great Creator — wish for artifact", True)
        else:
            player.add_to_grave(karn)
            mana -= 4

    # ── The One Ring (4 mana) — protection + card draw ──────────────────────
    ring = player.find_tag('ring')
    if ring and mana >= 4:
        player.remove_from_hand(ring)
        if not _try_counter_any(player, opponent, gs, ring, log_entries):
            player.add_to_grave(ring)
            mana -= 4
            player.draw(2)
            log_fn("★ The One Ring — protection + draw 2", True)
            if hasattr(gs, 'bowmasters_on_board') and gs.bowmasters_on_board:
                bowmasters_triggers(2, gs, log_entries,
                                    controller='o' if player is gs.bug else 'b')
            gs.check_life_totals()
            if gs.game_over:
                return
        else:
            player.add_to_grave(ring)
            mana -= 4

    # ── Kozilek's Command (4 mana) — modal: 2 damage or draw + mill ────────
    koz = player.find_tag('koz_cmd')
    if koz and mana >= 4:
        player.remove_from_hand(koz)
        if not _try_counter_any(player, opponent, gs, koz, log_entries):
            player.add_to_grave(koz)
            mana -= 4
            # Choose mode: 2 damage to creature + create token,
            # or draw + mill if no creatures to hit
            if opponent.creatures:
                target = max(opponent.creatures, key=lambda c: c.card.base_power)
                if target.card.base_toughness <= 2:
                    opponent.creatures.remove(target)
                    log_fn(f"Kozilek's Command — destroy {target.card.name} + token",
                           True)
                    update_goyf(gs)
                else:
                    player.draw(1)
                    log_fn("Kozilek's Command — draw 1 + mill", True)
                    if hasattr(gs, 'bowmasters_on_board') and gs.bowmasters_on_board:
                        bowmasters_triggers(
                            1, gs, log_entries,
                            controller='o' if player is gs.bug else 'b')
                    gs.check_life_totals()
                    if gs.game_over:
                        return
            else:
                player.draw(1)
                log_fn("Kozilek's Command — draw 1 + mill", True)
                if hasattr(gs, 'bowmasters_on_board') and gs.bowmasters_on_board:
                    bowmasters_triggers(
                        1, gs, log_entries,
                        controller='o' if player is gs.bug else 'b')
                gs.check_life_totals()
                if gs.game_over:
                    return
        else:
            player.add_to_grave(koz)
            mana -= 4

    # ── Stock Up (2 mana) — draw 2 ─────────────────────────────────────────
    stock = player.find_tag('stock')
    if stock and mana >= 2:
        player.remove_from_hand(stock)
        player.add_to_grave(stock)
        mana -= 2
        player.draw(2)
        log_fn("Stock Up — draw 2")
        if hasattr(gs, 'bowmasters_on_board') and gs.bowmasters_on_board:
            bowmasters_triggers(2, gs, log_entries,
                                controller='o' if player is gs.bug else 'b')
        gs.check_life_totals()
        if gs.game_over:
            return

    # ── Ugin, Eye of the Storms (6 mana) — board wipe ──────────────────────
    ugin = player.find_tag('ugin')
    if ugin and mana >= 6 and len(opponent.creatures) >= 2:
        player.remove_from_hand(ugin)
        if not _try_counter_any(player, opponent, gs, ugin, log_entries):
            player.add_to_grave(ugin)
            mana -= 6
            colored = [c for c in opponent.creatures if c.card.colors]
            for c in colored:
                opponent.creatures.remove(c)
            log_fn(f"★ Ugin — exile {len(colored)} colored creatures", True)
            update_goyf(gs)
        else:
            player.add_to_grave(ugin)
            mana -= 6

    # ── Ulamog, the Ceaseless Hunger (10 mana) — finisher ──────────────────
    ulamog = player.find_tag('ulamog')
    if ulamog and mana >= 10:
        player.remove_from_hand(ulamog)
        if not _try_counter_any(player, opponent, gs, ulamog, log_entries):
            player.put_creature_in_play(ulamog)
            mana -= 10
            # On cast trigger: exile up to 2 permanents
            exiled = 0
            while opponent.creatures and exiled < 2:
                target = opponent.creatures[0]
                opponent.creatures.remove(target)
                exiled += 1
            log_fn(f"★ Ulamog — exile {exiled} permanents, 10/10 indestructible",
                   True)
            update_goyf(gs)
        else:
            player.add_to_grave(ulamog)
            mana -= 10
            log_fn("Ulamog countered")

    # ── Crop Rotation — not used as spell here, handled by land tutor above
    #    (In a more detailed sim, would be cast in response to opponent's play)

    # ── Combat ──────────────────────────────────────────────────────────────
    if not gs.game_over:
        attackers = [c for c in player.creatures if not c.summoning_sick]
        if attackers:
            combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_cloudpost():
    results = []

    # Test 1: Deck size
    deck = make_cloudpost_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for req in ['post', 'glimmer', 'nexus', 'tower', 'mine', 'plant',
                'bog', 'boseiju', 'karakas', 'otawara', 'basic',
                'petal', 'crop', 'map', 'flute', 'needle',
                'stock', 'karn', 'koz_cmd', 'ring', 'ugin', 'ulamog']:
        assert req in tags, f"Missing tag: {req}"
    results.append("OK  All key card types present")

    # Test 3: Card counts
    from collections import Counter
    tag_counts = Counter(c.tag for c in deck)
    assert tag_counts['post'] == 4, f"Cloudpost: {tag_counts['post']}"
    assert tag_counts['glimmer'] == 2, f"Glimmerpost: {tag_counts['glimmer']}"
    assert tag_counts['nexus'] == 4, f"Planar Nexus: {tag_counts['nexus']}"
    assert tag_counts['tower'] == 4, f"Tower: {tag_counts['tower']}"
    assert tag_counts['mine'] == 2, f"Mine: {tag_counts['mine']}"
    assert tag_counts['plant'] == 2, f"Plant: {tag_counts['plant']}"
    assert tag_counts['petal'] == 4, f"Petal: {tag_counts['petal']}"
    assert tag_counts['crop'] == 4, f"Crop Rotation: {tag_counts['crop']}"
    assert tag_counts['map'] == 2, f"Expedition Map: {tag_counts['map']}"
    assert tag_counts['flute'] == 4, f"Flute: {tag_counts['flute']}"
    assert tag_counts['needle'] == 2, f"Needle: {tag_counts['needle']}"
    assert tag_counts['stock'] == 4, f"Stock Up: {tag_counts['stock']}"
    assert tag_counts['karn'] == 4, f"Karn: {tag_counts['karn']}"
    assert tag_counts['koz_cmd'] == 4, f"Kozilek's Command: {tag_counts['koz_cmd']}"
    assert tag_counts['ring'] == 3, f"The One Ring: {tag_counts['ring']}"
    assert tag_counts['ugin'] == 3, f"Ugin: {tag_counts['ugin']}"
    assert tag_counts['ulamog'] == 1, f"Ulamog: {tag_counts['ulamog']}"
    results.append("OK  All card counts correct")

    # Test 4: Land count
    lands = [c for c in deck if c.is_land()]
    assert len(lands) == 25, f"Expected 25 lands, got {len(lands)}"
    results.append("OK  Land count = 25")

    # Test 5: Locus lands (Cloudpost + Glimmerpost + Planar Nexus = 10)
    locus_tags = ('post', 'glimmer', 'nexus')
    locus_count = sum(1 for c in deck if c.tag in locus_tags)
    assert locus_count == 10, f"Expected 10 Locus lands, got {locus_count}"
    results.append("OK  Locus count = 10 (4 Post + 2 Glimmer + 4 Nexus)")

    # Test 6: Tron lands (Tower + Mine + Plant = 8)
    tron_tags = ('tower', 'mine', 'plant')
    tron_count = sum(1 for c in deck if c.tag in tron_tags)
    assert tron_count == 8, f"Expected 8 Tron lands, got {tron_count}"
    results.append("OK  Tron count = 8 (4 Tower + 2 Mine + 2 Plant)")

    # Test 7: Mana calculation helper
    # Mock a player with 3 Cloudposts and 1 Glimmerpost (4 Loci)
    class MockLand:
        def __init__(self, tag):
            self.card = type('C', (), {'tag': tag})()

    class MockPlayer:
        def __init__(self):
            self.lands = []

    mp = MockPlayer()
    mp.lands = [MockLand('post'), MockLand('post'), MockLand('post'),
                MockLand('glimmer')]
    # base_mana = 4 (one per land), but each Cloudpost gets +3 extra (4 loci - 1)
    # so extra = 3 * 3 = 9, effective = 4 + 9 = 13
    eff = _calc_effective_mana(mp, 4)
    assert eff == 13, f"Expected 13 effective mana, got {eff}"
    results.append("OK  Mana calc: 3 Posts + 1 Glimmer (4 Loci) = 13 effective mana")

    # Test 8: Tron mana bonus
    mp2 = MockPlayer()
    mp2.lands = [MockLand('mine'), MockLand('plant'), MockLand('tower')]
    # base = 3, tron_extra = 1 (mine) + 1 (plant) + 2 (tower) = 4
    eff2 = _calc_effective_mana(mp2, 3)
    assert eff2 == 7, f"Expected 7 effective mana with Tron, got {eff2}"
    results.append("OK  Mana calc: Tron assembled = 7 effective mana (3 base + 4 bonus)")

    # Test 9: Win condition present
    win_cons = [c for c in deck if c.win_condition]
    assert len(win_cons) >= 1, "No win condition found"
    assert any(c.tag == 'ulamog' for c in win_cons)
    results.append("OK  Win condition: Ulamog, the Ceaseless Hunger")

    # Test 10: Combo pieces marked
    combo_pieces = [c for c in deck if c.is_combo_piece]
    combo_tags = {c.tag for c in combo_pieces}
    assert 'post' in combo_tags, "Cloudpost should be combo piece"
    assert 'crop' in combo_tags, "Crop Rotation should be combo piece"
    results.append("OK  Combo pieces flagged (post, crop)")

    return results


if __name__ == '__main__':
    print("Running Cloudpost / 12-Post tests...")
    for r in test_cloudpost():
        print(f"  {r}")
    print("All Cloudpost tests passed.")
