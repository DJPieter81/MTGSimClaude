"""
Infect — Legacy combo-aggro deck.

Key mechanics:
- Infect creatures deal damage as poison counters (10 poison = death)
- Free pump spells enable T2 kills from 0 poison
- Invigorate: free (alt cost: opp gains 3 life — irrelevant with infect), +4/+4
- Mutagenic Growth: free (pay 2 life), +2/+2
- Berserk: doubles creature's power (creature dies EOT, but damage already dealt)
- Noble Hierarch: exalted gives +1/+1 to a lone attacker

Typical kill line:
  T1: Glistener Elf
  T2: Attack, Invigorate (+4), Mutagenic Growth (+2, pay 2 life), Berserk (double)
      = (1+4+2)*2 = 14 poison from 0 — lethal!
"""

import sys
sys.path.insert(0, '/home/user/MTGSimClaude')

import random
from cards import creature, instant, sorcery, artifact
from cards import fetch_land, dual_land, basic_land, utility_land
from rules import Card, CardType

# ─── Deck construction ────────────────────────────────────────────────────────

def make_infect_deck():
    d = []

    # ── Creatures (12) ───────────────────────────────────────────────────────
    # Glistener Elf: 1/1 infect for {G}
    d += [creature('Glistener Elf', 1, {'G': 1}, {'G'}, power=1, toughness=1,
                   tag='glistener')] * 4

    # Blighted Agent: 1/1 infect unblockable for {1U}
    d += [creature('Blighted Agent', 2, {'U': 1, 'generic': 1}, {'U'}, power=1,
                   toughness=1, tag='blighted')] * 4

    # Noble Hierarch: 0/1 exalted for {G}
    d += [creature('Noble Hierarch', 1, {'G': 1}, {'G'}, power=0, toughness=1,
                   tag='hierarch')] * 4

    # ── Pump Spells (14) ─────────────────────────────────────────────────────
    # Invigorate: {2G} but free (alt cost: opp gains 3 life), +4/+4
    d += [instant('Invigorate', 3, {'G': 1, 'generic': 2}, {'G'},
                  tag='invigorate')] * 4

    # Mutagenic Growth: {G/P} — pay 2 life instead of {G}, +2/+2
    d += [instant('Mutagenic Growth', 1, {'G': 1}, {'G'},
                  tag='mutagenic', life_cost=2)] * 4

    # Berserk: {G}, double power, creature dies EOT
    d += [instant('Berserk', 1, {'G': 1}, {'G'}, tag='berserk')] * 4

    # Vines of Vastwood: {G} kicked {G}, +4/+4 and hexproof
    d += [instant('Vines of Vastwood', 1, {'G': 1}, {'G'}, tag='vines')] * 2

    # Blossoming Defense: {G}, +2/+2 and hexproof
    d += [instant('Blossoming Defense', 1, {'G': 1}, {'G'}, tag='defense')] * 2

    # ── Cantrips (6) ─────────────────────────────────────────────────────────
    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 2

    # ── Countermagic (4) ─────────────────────────────────────────────────────
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 2
    d += [instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'},
                  tag='daze')] * 2

    # ── Utility (2) ──────────────────────────────────────────────────────────
    # Crop Rotation: {G}, sac a land, tutor any land (Inkmoth Nexus)
    d += [instant('Crop Rotation', 1, {'G': 1}, {'G'}, tag='crop')] * 2

    # ── Lands (16) ───────────────────────────────────────────────────────────
    # Inkmoth Nexus: utility land, becomes 1/1 infect flyer
    d += [utility_land('Inkmoth Nexus', {'C'}, tag='inkmoth')] * 4

    # Tropical Island: U/G dual
    d += [dual_land('Tropical Island', ['U', 'G'], ['Island', 'Forest'])] * 4

    # Breeding Pool: U/G dual (shock land, modelled as dual)
    d += [dual_land('Breeding Pool', ['U', 'G'], ['Island', 'Forest'])] * 2

    # Windswept Heath: fetch
    d += [fetch_land('Windswept Heath', ['Forest', 'Plains'])] * 4

    # Misty Rainforest: fetch
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 2

    # Forest: basic
    d += [basic_land('Forest', 'G', 'Forest')] * 2

    # Pendelhaven: utility land, {T}: target 1/1 gets +1/+2
    d += [utility_land('Pendelhaven', {'G'}, tag='pendel')] * 2

    assert len(d) == 60, f"Infect deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

INFECT_TAGS = {'glistener', 'blighted', 'inkmoth'}

def _strategy_infect(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Infect strategy — combo-aggro that wins via 10 poison counters.

    Priority:
    1. Play mana dork (Noble Hierarch) for exalted
    2. Deploy infect creature (Glistener Elf T1, Blighted Agent T2)
    3. Activate Inkmoth Nexus if no creature in play
    4. Cast cantrips to dig for pump
    5. Attack with infect creature + all free pump spells
    6. Track poison counters — 10 = lethal
    """
    from engine import _try_counter_any, bowmasters_triggers
    from rules import Permanent

    mana = total_mana

    # ── Initialize poison tracking ───────────────────────────────────────────
    if not hasattr(gs, 'opp_poison'):
        gs.opp_poison = 0

    if gs.game_over:
        return

    # ── Phase 1: Play a land (handled by engine) ────────────────────────────
    # Prioritize Inkmoth Nexus if we have an infect creature but no green mana,
    # otherwise prioritize color-producing lands.

    # ── Phase 2: Cast Noble Hierarch (exalted mana dork) ────────────────────
    hierarch = player.find_tag('hierarch')
    if hierarch and mana >= 1:
        player.remove_from_hand(hierarch)
        if not _try_counter_any(player, opponent, gs, hierarch, log_entries):
            player.put_creature_in_play(hierarch)
            log_fn("Noble Hierarch (exalted)")
        else:
            player.add_to_grave(hierarch)
        mana -= 1

    if gs.game_over:
        return

    # ── Phase 3: Deploy infect creature ─────────────────────────────────────
    # Prefer Glistener Elf (1 mana) over Blighted Agent (2 mana)
    glistener = player.find_tag('glistener')
    blighted = player.find_tag('blighted')

    if glistener and mana >= 1:
        player.remove_from_hand(glistener)
        if not _try_counter_any(player, opponent, gs, glistener, log_entries):
            player.put_creature_in_play(glistener)
            log_fn("Glistener Elf (infect)")
        else:
            player.add_to_grave(glistener)
        mana -= 1
    elif blighted and mana >= 2:
        player.remove_from_hand(blighted)
        if not _try_counter_any(player, opponent, gs, blighted, log_entries):
            player.put_creature_in_play(blighted)
            log_fn("Blighted Agent (infect, unblockable)")
        else:
            player.add_to_grave(blighted)
        mana -= 2

    if gs.game_over:
        return

    # ── Phase 4: Cantrips — dig for pump spells ─────────────────────────────
    for _ in range(4):
        cantrip = player.find_tag('bs') or player.find_tag('ponder')
        if cantrip and mana >= 1:
            player.remove_from_hand(cantrip)
            if not _try_counter_any(player, opponent, gs, cantrip, log_entries):
                # Draw a card
                if player.library:
                    drawn = player.library.pop(0)
                    player.hand.append(drawn)
                    log_fn(f"{cantrip.name} — draw")
                    bowmasters_triggers(1, gs, log_entries, controller='o' if player is gs.p1 else 'b')
                else:
                    log_fn(f"{cantrip.name} — library empty")
            else:
                player.add_to_grave(cantrip)
            mana -= 1
        else:
            break

    if gs.game_over:
        return

    # ── Phase 5: Crop Rotation — tutor Inkmoth Nexus ────────────────────────
    # Use Crop Rotation if we have no infect creature in play and have a land to sac
    infect_on_board = [c for c in player.creatures
                       if c.card.tag in INFECT_TAGS and not c.summoning_sick]
    crop = player.find_tag('crop')
    if crop and not infect_on_board and mana >= 1 and player.lands:
        player.remove_from_hand(crop)
        if not _try_counter_any(player, opponent, gs, crop, log_entries):
            # Sacrifice a land
            sac_land = player.lands[-1]
            player.lands.remove(sac_land)
            player.graveyard.append(sac_land.card)
            # Tutor Inkmoth Nexus from library
            inkmoth_cards = [c for c in player.library if c.tag == 'inkmoth']
            if inkmoth_cards:
                found = inkmoth_cards[0]
                player.library.remove(found)
                # Put directly into play as a land
                from rules import LandPermanent
                lp = LandPermanent(card=found,
                                   controller='b' if player is gs.p1 else 'o')
                player.lands.append(lp)
                log_fn(f"Crop Rotation — sac {sac_land.card.name}, tutor Inkmoth Nexus", True)
            else:
                log_fn("Crop Rotation — no Inkmoth in library")
        else:
            player.add_to_grave(crop)
        mana -= 1

    if gs.game_over:
        return

    # ── Phase 6: Activate Inkmoth Nexus ─────────────────────────────────────
    # If no non-summoning-sick infect creature in play, animate Inkmoth Nexus
    infect_creatures = [c for c in player.creatures
                        if c.card.tag in INFECT_TAGS and not c.summoning_sick]
    inkmoth_lands = [l for l in player.lands
                     if l.card.tag == 'inkmoth' and not l.tapped]

    if not infect_creatures and inkmoth_lands and mana >= 1:
        # Animate Inkmoth Nexus — costs 1 mana, becomes 1/1 infect flyer
        ink_land = inkmoth_lands[0]
        ink_land.tapped = True
        mana -= 1
        # Create creature permanent for the Inkmoth
        ink_creature_card = Card('Inkmoth Nexus', CardType.CREATURE, cmc=0,
                                 mana_cost={}, colors=set(), tag='inkmoth',
                                 base_power=1, base_toughness=1, gy_type='land')
        ink_creature_card.flying = True
        perm = Permanent(card=ink_creature_card,
                         controller='b' if player is gs.p1 else 'o',
                         summoning_sick=False)  # lands don't have summoning sickness
        perm._is_animated_land = True
        player.creatures.append(perm)
        infect_creatures = [perm]
        log_fn("Inkmoth Nexus activates — 1/1 infect flyer")

    if gs.game_over:
        return

    # ── Phase 7: Combat with pump spells ─────────────────────────────────────
    # Re-check infect creatures (may have animated Inkmoth)
    infect_creatures = [c for c in player.creatures
                        if c.card.tag in INFECT_TAGS and not c.summoning_sick]

    if not infect_creatures:
        return

    # Pick the best attacker: prefer unblockable (Blighted Agent), then flyer (Inkmoth)
    attacker = None
    for preferred_tag in ('blighted', 'inkmoth', 'glistener'):
        candidates = [c for c in infect_creatures if c.card.tag == preferred_tag]
        if candidates:
            attacker = candidates[0]
            break
    if not attacker:
        attacker = infect_creatures[0]

    # Calculate base power
    base_power = getattr(attacker, 'power', attacker.card.base_power)
    pump_bonus = 0

    # Exalted bonus: +1/+1 per Noble Hierarch on the battlefield (attacking alone)
    exalted_count = sum(1 for c in player.creatures if c.card.tag == 'hierarch')
    pump_bonus += exalted_count

    # Pendelhaven bonus: if attacker is 1/1, +1/+2
    pendel_lands = [l for l in player.lands
                    if l.card.tag == 'pendel' and not l.tapped]
    if pendel_lands and base_power <= 1:
        pendel_lands[0].tapped = True
        pump_bonus += 1  # +1 power (+2 toughness not tracked for damage)
        log_fn("Pendelhaven — target 1/1 gets +1/+2")

    # ── Cast free pump spells ────────────────────────────────────────────────
    # Invigorate: free (alt cost: opp gains 3 life), +4/+4
    for _ in range(4):
        inv = player.find_tag('invigorate')
        if inv:
            player.remove_from_hand(inv)
            if not _try_counter_any(player, opponent, gs, inv, log_entries):
                pump_bonus += 4
                # Opponent gains 3 life (irrelevant — infect doesn't care about life)
                opponent.life += 3
                log_fn("Invigorate (free) — +4/+4, opp gains 3 life")
            else:
                player.add_to_grave(inv)
        else:
            break

    if gs.game_over:
        return

    # Mutagenic Growth: free (pay 2 life), +2/+2
    for _ in range(4):
        mut = player.find_tag('mutagenic')
        if mut:
            player.remove_from_hand(mut)
            if not _try_counter_any(player, opponent, gs, mut, log_entries):
                pump_bonus += 2
                player.life -= 2
                log_fn("Mutagenic Growth (pay 2 life) — +2/+2")
                gs.check_life_totals()
            else:
                player.add_to_grave(mut)
        else:
            break

    if gs.game_over:
        return

    # Vines of Vastwood (kicked): +4/+4 + hexproof — costs {G}{G} (2 mana)
    for _ in range(2):
        vines = player.find_tag('vines')
        if vines and mana >= 2:
            player.remove_from_hand(vines)
            if not _try_counter_any(player, opponent, gs, vines, log_entries):
                pump_bonus += 4
                log_fn("Vines of Vastwood (kicked) — +4/+4, hexproof")
            else:
                player.add_to_grave(vines)
            mana -= 2
        else:
            break

    if gs.game_over:
        return

    # Blossoming Defense: +2/+2 + hexproof — costs {G} (1 mana)
    for _ in range(2):
        defense = player.find_tag('defense')
        if defense and mana >= 1:
            player.remove_from_hand(defense)
            if not _try_counter_any(player, opponent, gs, defense, log_entries):
                pump_bonus += 2
                log_fn("Blossoming Defense — +2/+2, hexproof")
            else:
                player.add_to_grave(defense)
            mana -= 1
        else:
            break

    if gs.game_over:
        return

    # Berserk: doubles power — costs {G} (1 mana). Cast LAST (after all other pumps).
    total_before_berserk = base_power + pump_bonus
    berserk_count = 0
    for _ in range(4):
        bsk = player.find_tag('berserk')
        if bsk and mana >= 1:
            player.remove_from_hand(bsk)
            if not _try_counter_any(player, opponent, gs, bsk, log_entries):
                berserk_count += 1
                log_fn("Berserk — double power (creature dies EOT)")
            else:
                player.add_to_grave(bsk)
            mana -= 1
        else:
            break

    if gs.game_over:
        return

    # Calculate total infect damage
    total_power = total_before_berserk
    for _ in range(berserk_count):
        total_power *= 2

    # ── Check if blocked ─────────────────────────────────────────────────────
    # Blighted Agent is unblockable; Inkmoth Nexus has flying
    blocked = False
    if attacker.card.tag == 'blighted':
        blocked = False  # unblockable
    elif attacker.card.tag == 'inkmoth':
        # Flying — blocked only by flyers/reach
        blocked = any(not c.summoning_sick and
                      (getattr(c.card, 'flying', False) or
                       getattr(c.card, 'reach', False))
                      for c in opponent.creatures)
    else:
        # Glistener Elf — can be blocked by any untapped creature
        blocked = any(not c.tapped for c in opponent.creatures)

    # ── Apply poison damage ──────────────────────────────────────────────────
    if not blocked and total_power > 0:
        poison = getattr(gs, 'opp_poison', 0)
        poison += total_power
        gs.opp_poison = poison
        log_fn(f"★ {attacker.card.name} deals {total_power} poison "
               f"({poison}/10)", True)

        # Berserk kills the creature at end of turn
        if berserk_count > 0:
            if attacker in player.creatures:
                player.creatures.remove(attacker)
                player.graveyard.append(attacker.card)
                log_fn(f"  {attacker.card.name} dies to Berserk EOT")

        # Clean up animated Inkmoth
        if getattr(attacker, '_is_animated_land', False):
            if attacker in player.creatures:
                player.creatures.remove(attacker)

        if poison >= 10:
            gs.game_over = True
            gs.winner = 'p1' if player is gs.p1 else 'p2'
            gs.win_reason = f"Infect: {poison} poison counters"
            gs.kill_turn = gs.turn
            log_fn(f"★★★ LETHAL — {poison} poison counters on turn {gs.turn}!", True)
    elif blocked:
        log_fn(f"  {attacker.card.name} blocked — no poison damage")
        # Berserk still kills the creature
        if berserk_count > 0:
            if attacker in player.creatures:
                player.creatures.remove(attacker)
                player.graveyard.append(attacker.card)
                log_fn(f"  {attacker.card.name} dies to Berserk EOT")
        # Clean up animated Inkmoth
        if getattr(attacker, '_is_animated_land', False):
            if attacker in player.creatures:
                player.creatures.remove(attacker)
    else:
        log_fn(f"  {attacker.card.name} — no damage (0 power)")

    gs.state_based_actions()


# ─── Test ─────────────────────────────────────────────────────────────────────

def test_infect():
    deck = make_infect_deck()
    assert len(deck) == 60, f"Deck has {len(deck)} cards, expected 60"

    # Verify card type counts
    from rules import CardType
    creatures = [c for c in deck if c.card_type == CardType.CREATURE]
    instants = [c for c in deck if c.card_type == CardType.INSTANT]
    sorceries = [c for c in deck if c.card_type == CardType.SORCERY]
    lands = [c for c in deck if c.card_type == CardType.LAND]

    assert len(creatures) == 12, f"Creatures: {len(creatures)} (expected 12)"
    assert len(instants) == 26, f"Instants: {len(instants)} (expected 26)"
    assert len(sorceries) == 2, f"Sorceries: {len(sorceries)} (expected 2)"
    assert len(lands) == 20, f"Lands: {len(lands)} (expected 20)"
    # 4 Inkmoth + 4 Tropical + 2 Breeding Pool + 4 Windswept + 2 Misty + 2 Forest + 2 Pendelhaven = 20

    # Verify specific card counts by tag
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    assert tag_counts.get('glistener', 0) == 4, "Expected 4 Glistener Elf"
    assert tag_counts.get('blighted', 0) == 4, "Expected 4 Blighted Agent"
    assert tag_counts.get('hierarch', 0) == 4, "Expected 4 Noble Hierarch"
    assert tag_counts.get('inkmoth', 0) == 4, "Expected 4 Inkmoth Nexus"
    assert tag_counts.get('invigorate', 0) == 4, "Expected 4 Invigorate"
    assert tag_counts.get('mutagenic', 0) == 4, "Expected 4 Mutagenic Growth"
    assert tag_counts.get('berserk', 0) == 4, "Expected 4 Berserk"
    assert tag_counts.get('vines', 0) == 2, "Expected 2 Vines of Vastwood"
    assert tag_counts.get('defense', 0) == 2, "Expected 2 Blossoming Defense"
    assert tag_counts.get('bs', 0) == 4, "Expected 4 Brainstorm"
    assert tag_counts.get('ponder', 0) == 2, "Expected 2 Ponder"
    assert tag_counts.get('fow', 0) == 2, "Expected 2 Force of Will"
    assert tag_counts.get('daze', 0) == 2, "Expected 2 Daze"
    assert tag_counts.get('crop', 0) == 2, "Expected 2 Crop Rotation"
    assert tag_counts.get('pendel', 0) == 2, "Expected 2 Pendelhaven"

    print("✓ Infect deck: 60 cards, all counts verified")
    print(f"  Creatures: {len(creatures)}, Instants: {len(instants)}, "
          f"Sorceries: {len(sorceries)}, Lands: {len(lands)}")


if __name__ == '__main__':
    test_infect()


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_infect(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_infect = any(t in tags for t in ('glistener', 'blighted', 'inkmoth'))
    has_pump = any(t in tags for t in ('invigorate', 'mutagenic', 'berserk', 'vines', 'defense'))
    if len(hand) <= 5: return has_infect and lc >= 1
    return has_infect and lc >= 1 and (has_pump or any(c.is_cantrip for c in nonlands))


DECK_META = {
    'key':        'infect',
    'name':       'Infect',
    'make_deck':  make_infect_deck,
    'strategy':   _strategy_infect,
    'keep':       _keep_infect,
    'categories': {'combo', 'fast_combo'},
    'interaction': {'speed': 1, 'resilience': 2, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'bug_answers': 6},
    'meta_share': 0.02,
}
