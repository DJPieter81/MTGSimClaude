"""
Burn — Legacy mono-red aggro.

Game plan: deploy cheap hasty creatures T1-2, then point every burn spell
at the opponent's face.  Price of Progress punishes Legacy manabases
(typically 4-8 damage), and Fireblast closes the game for free.

Typical goldfish kill: T3-4.
"""

import sys
sys.path.insert(0, '/home/claude/mtg_sim')

from cards import creature, instant, sorcery
from rules import Card, CardType


# ─── Deck construction ────────────────────────────────────────────────────────

def make_burn_deck():
    d = []

    # ── Creatures (12) ───────────────────────────────────────────────────────

    # Goblin Guide: 2/2 haste for R — the gold standard T1 play
    for _ in range(4):
        d.append(creature('Goblin Guide', 1, {'R': 1}, {'R'},
                          power=2, toughness=2, tag='guide', haste=True))

    # Monastery Swiftspear: 1/2 haste, prowess (not modelled)
    for _ in range(4):
        d.append(creature('Monastery Swiftspear', 1, {'R': 1}, {'R'},
                          power=1, toughness=2, tag='swiftspear', haste=True))

    # Eidolon of the Great Revel: 2/2, punishes CMC ≤3 spells
    for _ in range(4):
        d.append(creature('Eidolon of the Great Revel', 2, {'R': 2}, {'R'},
                          power=2, toughness=2, tag='eidolon'))

    # ── Burn spells — 3-damage suite (16) ────────────────────────────────────

    # Lightning Bolt: {R} instant, 3 damage
    # All direct-damage burn spells are marked win_condition — the deck wins
    # exclusively by burning the opponent, and each spell is part of the kill
    for _ in range(4):
        d.append(instant('Lightning Bolt', 1, {'R': 1}, {'R'}, tag='bolt',
                         win_condition=True))

    # Chain Lightning: {R} sorcery, 3 damage
    for _ in range(4):
        d.append(sorcery('Chain Lightning', 1, {'R': 1}, {'R'}, tag='chain',
                         win_condition=True))

    # Lava Spike: {R} sorcery, 3 to player only
    for _ in range(4):
        d.append(sorcery('Lava Spike', 1, {'R': 1}, {'R'}, tag='spike',
                         win_condition=True))

    # Rift Bolt: {2R} sorcery, 3 damage — suspend 1 effectively costs R
    for _ in range(4):
        d.append(sorcery('Rift Bolt', 3, {'R': 1, 'generic': 2}, {'R'},
                         tag='rift', win_condition=True))

    # ── Utility burn (12) ────────────────────────────────────────────────────

    # Price of Progress: {1R} instant, 2 damage per nonbasic land opp controls
    # Marked as win_condition — deals 4-8+ damage, the primary burn finisher vs nonbasic decks
    for _ in range(4):
        d.append(instant('Price of Progress', 2, {'R': 1, 'generic': 1}, {'R'},
                         tag='pop', win_condition=True))

    # Fireblast: {4RR} instant, 4 damage — alt cost: sac 2 Mountains
    # Already treated as major (CMC >= 4), but mark win_condition for clarity
    for _ in range(4):
        d.append(instant('Fireblast', 6, {'R': 2, 'generic': 4}, {'R'},
                         tag='fireblast', win_condition=True))

    # Searing Blaze: {RR} instant, 3+3 with landfall
    for _ in range(2):
        d.append(instant('Searing Blaze', 2, {'R': 2}, {'R'}, tag='blaze',
                         win_condition=True))

    # Skullcrack: {1R} instant, 3 damage, opponent can't gain life
    for _ in range(2):
        d.append(instant('Skullcrack', 2, {'R': 1, 'generic': 1}, {'R'},
                         tag='skullcrack', win_condition=True))

    # ── Lands (20) ───────────────────────────────────────────────────────────

    # Mountain (basic)
    for _ in range(10):
        c = Card('Mountain', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='basic', produces={'R'},
                 is_basic=True, gy_type='land')
        d.append(c)

    # Barbarian Ring: threshold — sac, deal 2 damage
    for _ in range(4):
        c = Card('Barbarian Ring', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='ring', produces={'R'}, gy_type='land')
        d.append(c)

    # Fiery Islet: draws a card (not modelled), taps for R
    for _ in range(2):
        c = Card('Fiery Islet', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='islet', produces={'R'}, gy_type='land')
        d.append(c)

    # Inspiring Vantage: taps for R or W
    for _ in range(4):
        c = Card('Inspiring Vantage', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='vantage', produces={'R', 'W'},
                 gy_type='land')
        d.append(c)

    assert len(d) == 60, f"Burn deck: {len(d)} cards (expected 60)"
    return d


# ─── Strategy ────────────────────────────────────────────────────────────────

def _strategy_burn(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Burn strategy — aggressive mono-red.

    Priority:
      1. Deploy creatures (Guide > Swiftspear > Eidolon)
      2. Attack with everything that can attack
      3. Cast burn spells at face, saving Fireblast as finisher
      4. Set eidolon_active when Eidolon is on the battlefield
    """
    from engine import _try_counter_any, combat_declare, cast_spell

    mana = total_mana

    # ── Track whether we played a land this turn (for Searing Blaze) ─────
    landfall = player.land_played_this_turn

    # ── Deploy creatures ─────────────────────────────────────────────────
    # Priority: T1 Guide/Swiftspear, T2 Eidolon — deploy as many as mana allows
    deploy_order = ['guide', 'swiftspear', 'eidolon']

    for tag in deploy_order:
        while True:
            card = player.find_tag(tag)
            if not card or card.cmc > mana:
                break
            budget = [mana]
            if cast_spell(player, opponent, gs, card, budget, log_fn, log_entries,
                          on_resolve=lambda c: player.put_creature_in_play(c)):
                log_fn(f"{card.name} enters the battlefield", True)
                if tag == 'eidolon':
                    gs.eidolon_active = True
                    log_fn("★ Eidolon of the Great Revel — opponent pays 2 life per CMC≤3 spell", True)
            else:
                log_fn(f"{card.name} countered")
            mana = budget[0]
            if gs.game_over:
                return

    # ── Keep eidolon_active in sync ──────────────────────────────────────
    gs.eidolon_active = any(c.card.tag == 'eidolon' for c in player.creatures)

    # ── Eidolon self-damage awareness (needed before pre-combat spells) ──
    own_eidolon = gs.eidolon_active
    eidolon_self_cost = 2 if own_eidolon else 0

    def deal_face_damage(amount, source_name):
        opponent.life -= amount
        log_fn(f"★ {source_name} → {amount} damage (opp at {opponent.life})", True)
        gs.check_life_totals()

    def _worth_casting(spell_damage):
        """Only skip if Eidolon self-damage would kill us AND spell doesn't kill opp."""
        if not own_eidolon:
            return True
        if spell_damage >= opponent.life:
            return True  # lethal — always cast
        if player.life <= eidolon_self_cost:
            return False  # would kill ourselves
        return True  # trust the rules engine — Eidolon damage is self-regulating

    # ── Pre-combat: cast cheap burn spells for prowess triggers ──────────
    # Real Burn casts spells Main Phase 1 to pump Swiftspear before combat.
    swiftspear_in_play = any(c.card.tag == 'swiftspear' for c in player.creatures
                             if not c.summoning_sick)
    if swiftspear_in_play and mana >= 1:
        pre_combat_spell = (player.find_tag('chain') or player.find_tag('spike')
                            or player.find_tag('bolt') or player.find_tag('rift'))
        if pre_combat_spell and _worth_casting(3):
            budget = [mana]
            if cast_spell(player, opponent, gs, pre_combat_spell, budget, log_fn, log_entries,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, f"{c.name} (pre-combat)"))):
                pass  # resolved — on_resolve handled damage + graveyard
            mana = budget[0]

    # ── Prowess: Swiftspear gets +1/+0 per noncreature spell this turn ──
    prowess_count = player.spells_cast_this_turn
    prowess_boosted = []
    if prowess_count > 0:
        for c in player.creatures:
            if c.card.tag == 'swiftspear':
                c.power_mod += prowess_count
                prowess_boosted.append(c)
                if prowess_count > 0:
                    log_fn(f"  Prowess: Swiftspear +{prowess_count}/+0 → {c.power}/{c.toughness}")

    # ── Combat: attack with all non-summoning-sick creatures ─────────────
    attackers = [c for c in player.creatures if c.can_attack()]
    if attackers:
        # Goblin Guide trigger: each attacking Guide reveals defender's top card.
        # If it's a land, defender puts it in their hand (CR 510 — Guide downside).
        import random as _rng
        for atk in attackers:
            if atk.card.tag == 'guide' and opponent.library:
                top = opponent.library[0]
                if top.is_land():
                    opponent.library.pop(0)
                    opponent.hand.append(top)
                    log_fn(f"  Goblin Guide trigger → reveals {top.name} (land) — opponent draws it")

        combat_declare(player, opponent, gs, log_entries, attackers)
        gs.state_based_actions()
        gs.check_life_totals()
        if gs.game_over:
            # Clean up prowess before returning
            for c in prowess_boosted:
                c.power_mod -= prowess_count
            return

    # Reset prowess after combat (it's until end of turn, but more spells
    # will be cast post-combat — we'll re-apply at end if needed)
    for c in prowess_boosted:
        c.power_mod -= prowess_count
    prowess_boosted = []

    # ── Burn spells at face (post-combat) ──────────────────────────────
    # No artificial per-turn cap — mana availability and hand size are the
    # natural constraints, just like real Legacy Burn.

    # --- Price of Progress: best when opp has nonbasic lands ---
    while mana >= 2:
        pop = player.find_tag('pop')
        if not pop:
            break
        nonbasics = sum(1 for l in opponent.lands if not l.card.is_basic)
        pop_damage = nonbasics * 2
        if pop_damage <= 0:
            break  # don't waste it if opp has no nonbasics
        if not _worth_casting(pop_damage):
            break
        budget = [mana]
        if cast_spell(player, opponent, gs, pop, budget, log_fn, log_entries,
                      on_resolve=lambda c, dmg=pop_damage, nb=nonbasics: (
                          player.add_to_grave(c),
                          deal_face_damage(dmg, f"Price of Progress ({nb} nonbasics)"))):
            pass
        else:
            log_fn("Price of Progress countered")
        mana = budget[0]
        if gs.game_over:
            return

    # --- Cheap 3-damage spells: Chain Lightning, Lava Spike, Rift Bolt ---
    cheap_burn_tags = ['chain', 'spike', 'rift']
    for tag in cheap_burn_tags:
        while mana >= 1:
            card = player.find_tag(tag)
            if not card:
                break
            if not _worth_casting(3):
                break
            # Rift Bolt: suspend costs effectively 1 mana (simplified)
            budget = [mana]
            if cast_spell(player, opponent, gs, card, budget, log_fn, log_entries,
                          cost_override=1,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, c.name))):
                pass
            else:
                log_fn(f"{card.name} countered")
            mana = budget[0]
            if gs.game_over:
                return

    # --- Lightning Bolt at face (or at a key creature) ---
    while mana >= 1:
        bolt = player.find_tag('bolt')
        if not bolt:
            break
        if not _worth_casting(3) and not opponent.creatures:
            # Don't bolt face if Eidolon would kill us, but still bolt creatures
            break
        # Check if opponent has a high-value creature worth bolting
        # (Bowmasters, Tamiyo, DRC, etc.)
        priority_targets = [c for c in opponent.creatures
                            if c.card.tag in ('bowmasters', 'tamiyo', 'drc',
                                              'orc_army', 'w6')]
        if priority_targets and opponent.life > 4:
            target = priority_targets[0]
            budget = [mana]
            if cast_spell(player, opponent, gs, bolt, budget, log_fn, log_entries,
                          on_resolve=lambda c, t=target: (
                              player.add_to_grave(c),
                              setattr(t, 'damage_marked', t.damage_marked + 3),
                              log_fn(f"★ Lightning Bolt → {t.card.name} (3 damage)", True),
                              gs.state_based_actions())):
                pass
            else:
                log_fn("Lightning Bolt countered")
            mana = budget[0]
        else:
            # Bolt to face
            budget = [mana]
            if cast_spell(player, opponent, gs, bolt, budget, log_fn, log_entries,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, 'Lightning Bolt'))):
                pass
            else:
                log_fn("Lightning Bolt countered")
            mana = budget[0]
        if gs.game_over:
            return

    # --- Skullcrack: 3 damage, opponent can't gain life ---
    while mana >= 2:
        crack = player.find_tag('skullcrack')
        if not crack:
            break
        if not _worth_casting(3):
            break
        budget = [mana]
        if cast_spell(player, opponent, gs, crack, budget, log_fn, log_entries,
                      on_resolve=lambda c: (player.add_to_grave(c),
                                            deal_face_damage(3, 'Skullcrack'))):
            pass
        else:
            log_fn("Skullcrack countered")
        mana = budget[0]
        if gs.game_over:
            return

    # --- Searing Blaze: 3 to creature + 3 to player (needs landfall) ---
    if landfall:
        while mana >= 2:
            blaze = player.find_tag('blaze')
            if not blaze:
                break
            targets = list(opponent.creatures)
            if not targets:
                break  # needs a creature target
            target = targets[0]
            budget = [mana]
            if cast_spell(player, opponent, gs, blaze, budget, log_fn, log_entries,
                          on_resolve=lambda c, t=target: (
                              player.add_to_grave(c),
                              setattr(t, 'damage_marked', t.damage_marked + 3),
                              deal_face_damage(3, f"Searing Blaze ({t.card.name} takes 3)"),
                              gs.state_based_actions())):
                pass
            else:
                log_fn("Searing Blaze countered")
            mana = budget[0]
            if gs.game_over:
                return

    # --- Fireblast: 4 damage, alt cost = sacrifice 2 Mountains (free!) ---
    # Use as a finisher when opponent is at ≤7 life or when we're desperate
    fireblast = player.find_tag('fireblast')
    if fireblast and not gs.game_over:
        mtns = [l for l in player.lands
                if l.card.name == 'Mountain']
        can_fireblast = len(mtns) >= 2
        # Fire when: opponent is low enough that 4 finishes or nearly finishes
        # Real Burn saves Fireblast for lethal — sac'ing 2 lands is a huge cost
        should_fireblast = (opponent.life <= 4 or
                            (opponent.life <= 8 and gs.turn >= 4))
        if can_fireblast and should_fireblast:
            # Sacrifice 2 Mountains as alternate cost (paid on cast, before counters)
            m0, m1 = mtns[0], mtns[1]
            player.lands.remove(m0)
            player.lands.remove(m1)
            if cast_spell(player, opponent, gs, fireblast, None, log_fn, log_entries,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(4, "Fireblast (sac 2 Mountains)"))):
                pass
            else:
                log_fn("Fireblast countered")
            if gs.game_over:
                return

    # --- Barbarian Ring: threshold (7+ cards in GY), sac for 2 damage ---
    if len(player.graveyard) >= 7 and not gs.game_over:
        ring_lands = [l for l in player.lands if l.card.tag == 'ring']
        for ring in ring_lands:
            if opponent.life <= 2 or gs.turn >= 4:
                player.lands.remove(ring)
                player.add_to_grave(ring.card)
                deal_face_damage(2, "Barbarian Ring (threshold)")
                if gs.game_over:
                    return
                break  # only sac one per turn

    gs.state_based_actions()


# ─── Test ────────────────────────────────────────────────────────────────────

def test_burn():
    results = []

    # Test 1: Deck size
    deck = make_burn_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Card counts by tag
    from collections import Counter
    tags = Counter(c.tag for c in deck)
    expected = {
        'guide': 4, 'swiftspear': 4, 'eidolon': 4,
        'bolt': 4, 'chain': 4, 'spike': 4, 'rift': 4,
        'pop': 4, 'fireblast': 4, 'blaze': 2, 'skullcrack': 2,
        'basic': 10, 'ring': 4, 'islet': 2, 'vantage': 4,
    }
    for tag, count in expected.items():
        assert tags[tag] == count, f"{tag}: got {tags[tag]}, expected {count}"
    results.append("OK  All card counts correct")

    # Test 3: Creature stats
    creatures = [c for c in deck if c.is_creature()]
    assert len(creatures) == 12, f"Creatures: {len(creatures)}"
    guides = [c for c in creatures if c.tag == 'guide']
    assert all(c.base_power == 2 and c.base_toughness == 1 and c.haste
               for c in guides), "Guide stats wrong"
    swifts = [c for c in creatures if c.tag == 'swiftspear']
    assert all(c.base_power == 1 and c.base_toughness == 2 and c.haste
               for c in swifts), "Swiftspear stats wrong"
    eidolons = [c for c in creatures if c.tag == 'eidolon']
    assert all(c.base_power == 2 and c.base_toughness == 2 and not c.haste
               for c in eidolons), "Eidolon stats wrong"
    results.append("OK  Creature stats correct")

    # Test 4: Land count and types
    lands = [c for c in deck if c.is_land()]
    assert len(lands) == 20, f"Lands: {len(lands)}"
    basics = [c for c in lands if c.is_basic]
    assert len(basics) == 10, f"Basics: {len(basics)}"
    results.append("OK  20 lands (10 basic)")

    # Test 5: All burn spells are R-colored
    spells = [c for c in deck if not c.is_land() and not c.is_creature()]
    assert all('R' in c.colors for c in spells), "Non-red spell found"
    results.append("OK  All spells are red")

    # Test 6: Mana curve — burn is very low to the ground
    nonland = [c for c in deck if not c.is_land()]
    avg_cmc = sum(c.cmc for c in nonland) / len(nonland)
    assert avg_cmc < 3.0, f"Average CMC too high: {avg_cmc:.2f}"
    results.append(f"OK  Average nonland CMC = {avg_cmc:.2f}")

    return results


if __name__ == '__main__':
    print("Running Burn tests...")
    for r in test_burn():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_burn(hand, matchup=''):
    """Burn keeps any hand with 1-3 lands."""
    lands = [c for c in hand if c.is_land()]
    return 1 <= len(lands) <= 3


DECK_META = {
    'key':        'burn',
    'name':       'Burn',
    'make_deck':  make_burn_deck,
    'strategy':   _strategy_burn,
    'keep':       _keep_burn,
    'categories': {'aggro'},
    'interaction': {'speed': 1, 'resilience': 2, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'bug_answers': 10},
    'meta_share': 0.02,
}
