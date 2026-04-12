"""
Burn — Legacy mono-red aggro.

Game plan: deploy cheap hasty creatures T1-2, then point every burn spell
at the opponent's face.  Price of Progress punishes Legacy manabases
(typically 4-8 damage), and Fireblast closes the game for free.

Typical goldfish kill: T3-4.
"""

import sys
sys.path.insert(0, '/home/claude/mtg_sim')

from cards import creature, instant, sorcery, basic_land, fetch_land
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

    # Rift Bolt: suspend {R}, deals 3 — modeled as CMC 1 (always suspended)
    for _ in range(4):
        d.append(sorcery('Rift Bolt', 1, {'R': 1}, {'R'},
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

    # Mountain (basic) — must have subtypes={'Mountain'} for fetchlands to find them
    for _ in range(8):
        d.append(basic_land('Mountain', 'R', 'Mountain'))

    # Wooded Foothills (fetch → Mountain or Forest) — enables Fireblast + Searing Blaze landfall
    for _ in range(4):
        d.append(fetch_land('Wooded Foothills', ['Mountain', 'Forest']))

    # Bloodstained Mire (fetch → Swamp or Mountain)
    for _ in range(2):
        d.append(fetch_land('Bloodstained Mire', ['Swamp', 'Mountain']))

    # Barbarian Ring: threshold — sac, deal 2 damage
    for _ in range(4):
        c = Card('Barbarian Ring', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='ring', produces={'R'}, gy_type='land')
        d.append(c)

    # Fiery Islet: pay 1 life, sac → draw a card; taps for R
    for _ in range(2):
        c = Card('Fiery Islet', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='islet', produces={'R'}, gy_type='land')
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
    # Hand-aware priority: Swiftspear first when burn spells available for prowess,
    # Guide first when no burn (2/2 haste > 1/2 haste without prowess triggers).
    # Eidolon: skip T1 (no haste), skip late game, skip spell-heavy hands.
    has_burn_for_prowess = any(c.tag in ('bolt', 'chain', 'spike', 'rift', 'skullcrack', 'pop')
                               for c in player.hand)
    deploy_order = (['swiftspear', 'guide', 'eidolon'] if has_burn_for_prowess
                    else ['guide', 'swiftspear', 'eidolon'])
    creatures_cast = 0  # track creature spells for prowess (prowess is noncreature only)

    for tag in deploy_order:
        while True:
            card = player.find_tag(tag)
            if not card or card.cmc > mana:
                break
            # Eidolon gating: skip when self-tax exceeds value
            if tag == 'eidolon':
                if gs.turn <= 1:
                    break  # T1 Eidolon is a waste — no haste, no damage
                # Late game: prefer casting a 3-damage burn spell over a no-haste 2/2
                if gs.turn >= 6 and any(c.tag in ('bolt', 'chain', 'spike', 'rift')
                                        for c in player.hand):
                    break
                # Hand-density check: skip if 3+ cheap spells remain (self-tax
                # would cost 6+ life vs 0 opponent damage in many matchups)
                cheap_in_hand = sum(1 for c in player.hand
                                    if c.cmc <= 3 and not c.is_land() and c.tag != 'eidolon')
                if cheap_in_hand >= 4:
                    break
            budget = [mana]
            if cast_spell(player, opponent, gs, card, budget, log_fn, log_entries,
                          on_resolve=lambda c: player.put_creature_in_play(c)):
                log_fn(f"{card.name} enters the battlefield", True)
                creatures_cast += 1
                if tag == 'eidolon':
                    gs.eidolon_active = True
                    log_fn("★ Eidolon of the Great Revel — opponent pays 2 life per CMC≤3 spell", True)
            else:
                log_fn(f"{card.name} countered")
                creatures_cast += 1  # countered creature still incremented spells_cast
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

    # ── Pre-combat: bolt DRC while it's still 1/1 (before delirium) ───────
    # DRC is 1/1 without delirium but becomes 3/3 with delirium. Once 3/3
    # it still dies to bolt, but has already gotten surveil value. Bolt it
    # now while it's small — this also triggers prowess for Swiftspear.
    if mana >= 1 and not gs.game_over:
        bolt_for_drc = player.find_tag('bolt')
        if bolt_for_drc:
            drc_targets = [c for c in opponent.creatures
                           if c.card.tag == 'drc' and c.power <= 1
                           and (c.toughness - c.damage_marked) <= 3]
            # Only bolt DRC if opponent isn't already in lethal range
            burn_in_hand_count = sum(1 for c in player.hand if c.tag in
                                     ('bolt', 'chain', 'spike', 'rift', 'skullcrack', 'fireblast'))
            if drc_targets and opponent.life > 3 * burn_in_hand_count:
                target = drc_targets[0]
                budget = [mana]
                if cast_spell(player, opponent, gs, bolt_for_drc, budget, log_fn, log_entries,
                              on_resolve=lambda c, t=target: (
                                  player.add_to_grave(c),
                                  setattr(t, 'damage_marked', t.damage_marked + 3),
                                  log_fn(f"★ Lightning Bolt → {t.card.name} (pre-combat, deny delirium)", True),
                                  gs.state_based_actions())):
                    pass
                else:
                    log_fn("Lightning Bolt countered")
                mana = budget[0]

    # ── Pre-combat: cast face-only burn spells for prowess triggers ──────
    # Cast spike/rift/chain (R) pre-combat to maximize Swiftspear prowess,
    # then Price of Progress (1R), then skullcrack (1R).
    # Lightning Bolt is saved for post-combat — it's the only instant and
    # can target creatures, so we preserve that flexibility. Face-only
    # sorceries (spike/rift/chain) are better counter-bait: if opponent
    # has FoW, they waste it on an inflexible spell instead of bolt.
    # Searing Blaze is also cast pre-combat when landfall + opponent has creatures.
    swiftspear_in_play = any(c.card.tag == 'swiftspear' for c in player.creatures
                             if not c.summoning_sick)
    if swiftspear_in_play:
        # Cast face-only R-cost burn spells pre-combat (bolt saved for post-combat)
        while mana >= 1 and not gs.game_over:
            pre_combat_spell = (player.find_tag('spike')
                                or player.find_tag('chain'))
            if not pre_combat_spell or not _worth_casting(3):
                break
            budget = [mana]
            if cast_spell(player, opponent, gs, pre_combat_spell, budget, log_fn, log_entries,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, f"{c.name} (pre-combat)"))):
                pass  # resolved — on_resolve handled damage + graveyard
            mana = budget[0]
        # Cast Price of Progress pre-combat (1R, 2 per nonbasic)
        # Opponent's nonbasic count doesn't change during our turn, so no
        # reason to delay — casting now gives an extra prowess trigger.
        while mana >= 2 and not gs.game_over:
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
                              deal_face_damage(dmg, f"Price of Progress ({nb} nonbasics, pre-combat)"))):
                pass
            else:
                log_fn("Price of Progress countered")
            mana = budget[0]
            if gs.game_over:
                # Clean up and return (prowess cleanup happens below)
                break
        # Cast Searing Blaze pre-combat (RR, 3 creature + 3 face) for prowess
        if landfall:
            while mana >= 2 and not gs.game_over:
                blaze = player.find_tag('blaze')
                if not blaze:
                    break
                targets = list(opponent.creatures)
                if not targets:
                    break  # needs a creature target
                # Smart targeting: prefer creatures that die to 3 damage,
                # picking highest power among those; else target highest power.
                _killable = [c for c in targets if (c.toughness - c.damage_marked) <= 3]
                target = max(_killable, key=lambda c: c.power) if _killable else max(targets, key=lambda c: c.power)
                budget = [mana]
                if cast_spell(player, opponent, gs, blaze, budget, log_fn, log_entries,
                              on_resolve=lambda c, t=target: (
                                  player.add_to_grave(c),
                                  setattr(t, 'damage_marked', t.damage_marked + 3),
                                  deal_face_damage(3, f"Searing Blaze pre-combat ({t.card.name} takes 3)"),
                                  gs.state_based_actions())):
                    pass
                else:
                    log_fn("Searing Blaze countered")
                mana = budget[0]
        # Cast Skullcrack pre-combat too (1R, 3 damage)
        while mana >= 2 and not gs.game_over:
            crack = player.find_tag('skullcrack')
            if not crack or not _worth_casting(3):
                break
            budget = [mana]
            if cast_spell(player, opponent, gs, crack, budget, log_fn, log_entries,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, f"Skullcrack (pre-combat)"))):
                pass
            mana = budget[0]

    # ── Prowess: Swiftspear gets +1/+0 per NONCREATURE spell this turn ──
    prowess_count = player.spells_cast_this_turn - creatures_cast
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
                else:
                    log_fn(f"  Goblin Guide trigger → reveals {top.name} (nonland) — stays on top")

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

    # --- Price of Progress: cast post-combat if not already cast pre-combat ---
    # (Pre-combat PoP is gated on swiftspear_in_play; this catches the rest.)
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

    # --- Cheap 3-damage spells: Lava Spike first (face-only, no flexibility
    # to waste), then Rift Bolt (SUSPEND), then Chain Lightning ---
    # Rift Bolt: suspend for R — exile it, deals 3 damage at next upkeep.
    # Suspending is a special action (not a spell), so no counter window now.
    while mana >= 1 and not gs.game_over:
        rift = player.find_tag('rift')
        if not rift:
            break
        if not _worth_casting(3):
            break
        # Hard-cast for 3 mana if opponent is at ≤3 life (need lethal NOW)
        if opponent.life <= 3 and mana >= 3:
            budget = [mana]
            if cast_spell(player, opponent, gs, rift, budget, log_fn, log_entries,
                          cost_override=3,
                          on_resolve=lambda c: (player.add_to_grave(c),
                                                deal_face_damage(3, "Rift Bolt (hard cast)"))):
                log_fn(f"★ Rift Bolt (hard cast 2R) → 3 damage (opp at {opponent.life})")
            else:
                log_fn("Rift Bolt countered")
            mana = budget[0]
        else:
            # Suspend for R — exile, resolve next upkeep
            player.remove_from_hand(rift)
            player.exile.append(rift)
            mana -= 1
            player.suspended.append((rift, 1))
            log_fn(f"Rift Bolt suspended (−1 mana) — deals 3 next upkeep")
            # Prowess triggers from noncreature spells — suspend IS casting? No.
            # CR 702.62: "Suspend is a keyword that represents three abilities...
            # The first is a static ability that functions while the card is in hand."
            # Suspending is a SPECIAL ACTION, not casting a spell. No prowess.
        if gs.game_over:
            return

    # Spike and Chain: cast immediately as before
    cheap_burn_tags = ['spike', 'chain']
    for tag in cheap_burn_tags:
        while mana >= 1:
            card = player.find_tag(tag)
            if not card:
                break
            if not _worth_casting(3):
                break
            budget = [mana]
            if cast_spell(player, opponent, gs, card, budget, log_fn, log_entries,
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
        if not _worth_casting(3):
            # Don't bolt if Eidolon self-damage would kill us
            break
        # Check if opponent has a high-value creature worth bolting.
        # Only target creatures that bolt actually kills (toughness - damage <= 3).
        _bolt_kills = lambda c: (c.toughness - c.damage_marked) <= 3
        # High-priority tags: engines, evasive clocks, mana producers, tax pieces
        _high_priority_tags = (
            'bowmasters', 'bowm',        # Orcish Bowmasters — pings + army
            'orc_army',                  # the army token itself
            'tamiyo',                    # Tamiyo — card advantage engine
            'drc',                       # Dragon's Rage Channeler — surveil + clock
            'sfm',                       # Stoneforge Mystic — fetches equipment
            'delver',                    # Delver of Secrets — evasive 3/2
            'ragavan',                   # Ragavan — mana + card advantage
            'heritage',                  # Heritage Druid — elf mana engine
            'nettle',                    # Nettle Sentinel — elf clock
            'shepherd',                  # Allosaurus Shepherd — uncounterable
            'lackey',                    # Goblin Lackey — free goblins
            'thalia',                    # Thalia — taxes burn spells
            'dauthi',                    # Dauthi Voidwalker — unblockable clock
            'mentor',                    # Monastery Mentor — token engine
            'ocelot',                    # Ocelot Pride — token engine
            'guide',                     # Guide of Souls — lifegain engine (not Goblin Guide)
        )
        priority_targets = [c for c in opponent.creatures
                            if c.card.tag in _high_priority_tags and _bolt_kills(c)]
        # Fallback: any creature with power >= 2 that blocks our attackers and dies to bolt
        if not priority_targets:
            priority_targets = [c for c in opponent.creatures
                                if _bolt_kills(c) and c.power >= 2]
        # Only bolt creatures if NOT in lethal range (bolt+fireblast or bolt+bolt etc.)
        burn_in_hand = sum(1 for c in player.hand if c.tag in
                           ('bolt', 'chain', 'spike', 'rift', 'skullcrack', 'fireblast'))
        lethal_range = 3 * burn_in_hand  # rough estimate
        if priority_targets and opponent.life > lethal_range:
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
            # Smart targeting: prefer creatures that die to 3 damage,
            # picking highest power among those; else target highest power.
            _killable = [c for c in targets if (c.toughness - c.damage_marked) <= 3]
            target = max(_killable, key=lambda c: c.power) if _killable else max(targets, key=lambda c: c.power)
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
    # Use aggressively: combined lethal, late-game desperation, or chain two.
    # Loop to cast multiple Fireblasts if we have them and enough Mountains.
    while not gs.game_over:
        fireblast = player.find_tag('fireblast')
        if not fireblast:
            break
        mtns = [l for l in player.lands
                if l.card.name == 'Mountain']
        if len(mtns) < 2:
            break
        # Calculate remaining burn damage in hand (excluding this Fireblast)
        burn_tags = {'bolt': 3, 'chain': 3, 'spike': 3, 'rift': 3,
                     'skullcrack': 3, 'pop': 3, 'fireblast': 4}
        remaining_burn = sum(burn_tags.get(c.tag, 0) for c in player.hand
                            if c is not fireblast)
        has_second_fireblast = sum(1 for c in player.hand
                                  if c.tag == 'fireblast' and c is not fireblast) > 0
        should_fireblast = (
            opponent.life <= 4 + remaining_burn    # combined lethal with other burn
            or (gs.turn >= 4 and opponent.life <= 10)  # aggressive: T4+ and opp hurting
            or has_second_fireblast                    # chain both Fireblasts
        )
        if not should_fireblast:
            break
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
    # Each Ring activation is an activated ability (not a spell), so it's
    # uncounterable. Sac as many Rings as we have when threshold is met.
    if len(player.graveyard) >= 7 and not gs.game_over:
        ring_lands = [l for l in player.lands if l.card.tag == 'ring']
        for ring in ring_lands:
            if opponent.life <= 2 or gs.turn >= 4:
                player.lands.remove(ring)
                player.add_to_grave(ring.card)
                deal_face_damage(2, "Barbarian Ring (threshold)")
                if gs.game_over:
                    return

    # --- Fiery Islet: topdeck mode — sac for 1 life, draw a card ---
    # Activate when no castable burn spells remain in hand. Hand might still
    # have Fireblast (needs Mountains) or Eidolon (gated), but those aren't
    # the damage sources we're digging for.
    if not gs.game_over:
        _burn_tags = ('bolt', 'chain', 'spike', 'rift', 'skullcrack', 'pop', 'blaze')
        has_castable_burn = any(c.tag in _burn_tags and c.cmc <= mana
                                for c in player.hand)
        if not has_castable_burn and player.life >= 2:
            islet_lands = [l for l in player.lands if l.card.tag == 'islet']
            if islet_lands:
                islet = islet_lands[0]
                player.lands.remove(islet)
                player.add_to_grave(islet.card)
                player.life -= 1
                log_fn(f"★ Fiery Islet sacrificed — pay 1 life ({player.life}), draw a card", True)
                if player.library:
                    drawn = player.library.pop(0)
                    player.hand.append(drawn)
                    log_fn(f"  Drew: {drawn.name}")
                    # Try to cast the drawn card if it's a burn spell
                    if not gs.game_over and drawn.tag in ('bolt', 'chain', 'spike', 'rift') and mana >= 1:
                        if _worth_casting(3):
                            budget = [mana]
                            if cast_spell(player, opponent, gs, drawn, budget, log_fn, log_entries,
                                          on_resolve=lambda c: (player.add_to_grave(c),
                                                                deal_face_damage(3, f"{c.name} (off Islet)"))):
                                pass
                            mana = budget[0]
                    elif not gs.game_over and drawn.tag == 'skullcrack' and mana >= 2:
                        if _worth_casting(3):
                            budget = [mana]
                            if cast_spell(player, opponent, gs, drawn, budget, log_fn, log_entries,
                                          on_resolve=lambda c: (player.add_to_grave(c),
                                                                deal_face_damage(3, f"Skullcrack (off Islet)"))):
                                pass
                            mana = budget[0]
                    elif not gs.game_over and drawn.tag == 'pop' and mana >= 2:
                        nonbasics = sum(1 for l in opponent.lands if not l.card.is_basic)
                        pop_damage = nonbasics * 2
                        if pop_damage > 0 and _worth_casting(pop_damage):
                            budget = [mana]
                            if cast_spell(player, opponent, gs, drawn, budget, log_fn, log_entries,
                                          on_resolve=lambda c, dmg=pop_damage: (
                                              player.add_to_grave(c),
                                              deal_face_damage(dmg, f"Price of Progress (off Islet)"))):
                                pass
                            mana = budget[0]

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
    assert all(c.base_power == 2 and c.base_toughness == 2 and c.haste
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
    """Burn keeps hands with 1-3 lands AND at least one 1-CMC spell."""
    lands = [c for c in hand if c.is_land()]
    has_one_drop = any(c.cmc == 1 and not c.is_land() for c in hand)
    return 1 <= len(lands) <= 3 and has_one_drop


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
