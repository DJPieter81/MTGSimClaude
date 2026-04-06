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
     1. Crop Rotation — sac a land to tutor Cloudpost/Nexus to battlefield
     2. Lotus Petal for mana acceleration
     3. Expedition Map — tutor key lands
     4. Deploy haymakers: Karn (4), The One Ring (4), Ugin (6), Ulamog (10)
     5. Kozilek's Command for interaction / card advantage
     6. Lock pieces (Flute, Needle) in spare mana slots
     7. Stock Up for card draw
     8. Combat with creatures
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf
    from rules import Card as _Card, CardType as _CT, LandPermanent

    mana = _calc_effective_mana(player, total_mana)

    # ── Helper: trigger bowmasters on draw ──────────────────────────────────
    def _bowm_check(n):
        if getattr(gs, 'bowmasters_on_board', False):
            bowmasters_triggers(n, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')

    # ── Track persistent effects ────────────────────────────────────────────
    if not hasattr(gs, 'cloudpost_ring_counters'):
        gs.cloudpost_ring_counters = 0
    if not hasattr(gs, 'cloudpost_karn_active'):
        gs.cloudpost_karn_active = False
    if not hasattr(gs, 'cloudpost_ugin_active'):
        gs.cloudpost_ugin_active = False

    # ── The One Ring ongoing draw (if deployed on prior turn) ───────────────
    if gs.cloudpost_ring_counters > 0:
        gs.cloudpost_ring_counters += 1
        draws = gs.cloudpost_ring_counters
        player.draw(draws)
        player.life -= draws  # burden counter damage
        log_fn(f"The One Ring — draw {draws}, lose {draws} life ({player.life})")
        _bowm_check(draws)
        gs.check_life_totals()
        if gs.game_over:
            return

    # ── Karn ongoing effect: opponent's artifacts are disabled ─────────���─────
    # (Simplified: Karn creates a 4/4 construct each turn it's active)
    if gs.cloudpost_karn_active and gs.turn >= 6:
        # Karn + Mycosynth Lattice = hard lock. Opponent's lands don't work.
        log_fn("★ Karn + Mycosynth Lattice lock — opponent locked out", True)
        gs.game_over = True
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = "Cloudpost: Karn Lattice lock"
        gs.kill_turn = gs.turn
        return
    elif gs.cloudpost_karn_active:
        # Before T6 lock solidifies, Karn creates constructs
        from cards import creature as _creature
        construct = _creature('Karn Construct', 0, {}, set(), 4, 4, tag='karn_token')
        player.put_creature_in_play(construct)
        log_fn("Karn +1 — create 4/4 Construct")

    # ── Ugin ongoing effect: exile-based card advantage ─────────────────────
    if gs.cloudpost_ugin_active:
        # Ugin draws a card equivalent each turn
        player.draw(1)
        log_fn("Ugin — card advantage (draw 1)")
        _bowm_check(1)
        gs.check_life_totals()
        if gs.game_over:
            return

    # ── Crop Rotation (1 green mana) — the key ramp spell ──────────────────
    # Sac a land, tutor any land directly to battlefield
    crop = player.find_tag('crop')
    if crop and mana >= 1:
        # Need a land to sacrifice and a target to find
        sac_land = None
        for l in player.lands:
            if l.card.tag not in ('post', 'nexus'):  # don't sac our best lands
                sac_land = l
                break
        if not sac_land and player.lands:
            sac_land = player.lands[-1]  # sac worst land if needed

        target_land = (
            next((c for c in player.library if c.tag == 'post'), None)
            or next((c for c in player.library if c.tag == 'nexus'), None)
            or next((c for c in player.library
                     if c.tag in ('tower', 'mine', 'plant')), None)
        )

        if sac_land and target_land:
            player.remove_from_hand(crop)
            if not _try_counter_any(player, opponent, gs, crop, log_entries):
                player.add_to_grave(crop)
                # Sacrifice the land
                player.lands.remove(sac_land)
                player.add_to_grave(sac_land.card)
                # Put target land directly onto battlefield
                player.library.remove(target_land)
                new_land = LandPermanent(target_land, controller='o' if player is gs.p2 else 'b')
                player.lands.append(new_land)
                mana -= 1
                # Recalculate mana with new land
                mana = _calc_effective_mana(player,
                    player.available_mana_count())
                log_fn(f"★ Crop Rotation — sac {sac_land.card.name} → {target_land.name}",
                       True)
            else:
                player.add_to_grave(crop)
                # Still sacrifice the land (cost)
                player.lands.remove(sac_land)
                player.add_to_grave(sac_land.card)
                mana = _calc_effective_mana(player,
                    player.available_mana_count())
                log_fn("Crop Rotation countered (land still sacrificed)")

    # ── Lotus Petal — free ramp ─────────────────────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.add_to_grave(petal)
        mana += 1
        log_fn("Lotus Petal → +1 mana")

    # ── Expedition Map (1 to cast + 2 to activate = 3 total) ───────────────
    exp_map = player.find_tag('map')
    if exp_map and mana >= 3:
        player.remove_from_hand(exp_map)
        player.add_to_grave(exp_map)
        mana -= 3
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
    elif exp_map and mana >= 1:
        # Just cast it, activate later
        player.remove_from_hand(exp_map)
        player.add_to_grave(exp_map)
        mana -= 1
        log_fn("Expedition Map cast (will activate later)")

    # ── Deploy haymakers by mana threshold ──────────────────────────────────

    # Ulamog (10 mana) — ultimate finisher, try first
    ulamog = player.find_tag('ulamog')
    if ulamog and mana >= 10:
        player.remove_from_hand(ulamog)
        if not _try_counter_any(player, opponent, gs, ulamog, log_entries):
            player.put_creature_in_play(ulamog)
            mana -= 10
            exiled = 0
            for c in list(opponent.creatures[:2]):
                opponent.creatures.remove(c)
                exiled += 1
            # Also exile lands
            while exiled < 2 and opponent.lands:
                lnd = opponent.lands[-1]
                opponent.lands.remove(lnd)
                exiled += 1
            log_fn(f"★ Ulamog — exile {exiled} permanents, 10/10 indestructible",
                   True)
            update_goyf(gs)
        else:
            player.add_to_grave(ulamog)
            mana -= 10
            log_fn("Ulamog countered")

    # Ugin (6 mana) — board wipe, fires when opponent has creatures
    ugin = player.find_tag('ugin')
    if ugin and mana >= 6 and opponent.creatures:
        player.remove_from_hand(ugin)
        if not _try_counter_any(player, opponent, gs, ugin, log_entries):
            player.add_to_grave(ugin)
            mana -= 6
            colored = [c for c in opponent.creatures if c.card.colors]
            for c in list(colored):
                opponent.creatures.remove(c)
            gs.cloudpost_ugin_active = True
            log_fn(f"★ Ugin — exile {len(colored)} colored creatures + ongoing value",
                   True)
            update_goyf(gs)
        else:
            player.add_to_grave(ugin)
            mana -= 6

    # The One Ring (4 mana) — protection this turn + draw engine
    ring = player.find_tag('ring')
    if ring and mana >= 4 and gs.cloudpost_ring_counters == 0:
        player.remove_from_hand(ring)
        if not _try_counter_any(player, opponent, gs, ring, log_entries):
            player.add_to_grave(ring)
            mana -= 4
            gs.cloudpost_ring_counters = 1  # starts drawing next turn
            player.life += 8  # proxy for protection-from-everything (BUG can't attack)
            log_fn(f"★ The One Ring — protection (life→{player.life}), draw engine on",
                   True)
        else:
            player.add_to_grave(ring)
            mana -= 4

    # Karn (4 mana) — persistent threat factory
    karn = player.find_tag('karn')
    if karn and mana >= 4 and not gs.cloudpost_karn_active:
        player.remove_from_hand(karn)
        if not _try_counter_any(player, opponent, gs, karn, log_entries):
            player.add_to_grave(karn)
            mana -= 4
            gs.cloudpost_karn_active = True
            log_fn("★ Karn, the Great Creator — creates 4/4 each turn", True)
        else:
            player.add_to_grave(karn)
            mana -= 4

    # Kozilek's Command (4 mana) — removal + token or draw
    koz = player.find_tag('koz_cmd')
    if koz and mana >= 4:
        player.remove_from_hand(koz)
        if not _try_counter_any(player, opponent, gs, koz, log_entries):
            player.add_to_grave(koz)
            mana -= 4
            # Mode 1: kill a small creature + create spawn token
            small = [c for c in opponent.creatures if c.card.base_toughness <= 3]
            if small:
                target = max(small, key=lambda c: c.card.base_power)
                opponent.creatures.remove(target)
                # Create a 1/1 Eldrazi Spawn token
                from cards import creature as _creature
                spawn = _creature('Eldrazi Spawn', 0, {}, set(), 1, 1, tag='spawn')
                player.put_creature_in_play(spawn)
                log_fn(f"Kozilek's Command — kill {target.card.name} + Spawn token",
                       True)
                update_goyf(gs)
            else:
                # Mode 2: draw 2 cards
                player.draw(2)
                log_fn("Kozilek's Command — draw 2", True)
                _bowm_check(2)
                gs.check_life_totals()
                if gs.game_over:
                    return
        else:
            player.add_to_grave(koz)
            mana -= 4

    # ── Lock pieces in spare mana slots ─────────────────────────────────────
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

    # ── Stock Up (2 mana) — draw 2 ─────────────────────────────────────────
    stock = player.find_tag('stock')
    if stock and mana >= 2:
        player.remove_from_hand(stock)
        player.add_to_grave(stock)
        mana -= 2
        player.draw(2)
        log_fn("Stock Up — draw 2")
        _bowm_check(2)
        gs.check_life_totals()
        if gs.game_over:
            return

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


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_cloudpost(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    locus = sum(1 for c in lands if c.tag in ('post', 'glimmer', 'nexus'))
    tron = sum(1 for c in lands if c.tag in ('tower', 'mine', 'plant'))
    has_ramp = any(t in tags for t in ('crop', 'map', 'petal'))
    has_payoff = any(t in tags for t in ('karn', 'ring', 'ugin', 'ulamog', 'koz_cmd'))
    if len(hand) <= 5: return lc >= 1 and (has_ramp or has_payoff)
    return lc >= 2 and (locus >= 1 or tron >= 1 or has_ramp) and (has_payoff or has_ramp)


DECK_META = {
    'key':        'cloudpost',
    'name':       'Cloudpost (12-Post)',
    'make_deck':  make_cloudpost_deck,
    'strategy':   _strategy_cloudpost,
    'keep':       _keep_cloudpost,
    'categories': {'prison', 'land_combo'},
    'interaction': {'speed': 4, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': True, 'creature_based': False},
    'meta_share': 0.01,
}
