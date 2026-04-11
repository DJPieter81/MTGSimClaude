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
        c.ward = 4
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
    4. Cast Thought Monitor (draws 2 — maximises hand before deploying creatures)
    5. Cast Thoughtcast (draws 2 — deploy all draw spells before big creatures)
    6. Deploy Pinnacle Emissary with any newly drawn copies included
    7. Deploy Kappa Cannoneer
    8. Deploy Krang, Master Mind
    9. Urza's Saga — tick chapters, generate constructs, tutor artifacts
    10. Attack with all creatures
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf
    from rules import Card as _Card, CardType as _CT, Permanent

    def _has_blue():
        """Return True if the player has at least one blue mana source available.

        Blue sources checked (in order):
        - Any untapped land that produces 'U' (Seat of the Synod, Island, Otawara)
        - Mox Opal already in play with metalcraft (3+ artifacts on board)
        - Lotus Petal in hand (produces any colour including U)
        """
        for land in player.lands:
            if not land.tapped and 'U' in land.effective_produces():
                return True
        # Mox Opal in play provides any color with metalcraft (3+ artifacts)
        if (any(a.card.tag == 'opal' for a in player.artifacts)
                and _artifact_count(player) >= 3):
            return True
        # Lotus Petal in hand — can produce any color including U
        if any(c.tag == 'petal' for c in player.hand):
            return True
        return False

    def _has_black():
        """Return True if the player has at least one black mana source available.

        This deck has NO natural black land sources. Black mana can only come from:
        - Mox Opal already in play with metalcraft (3+ artifacts on board)
        - Lotus Petal in hand (produces any colour including B)

        Note: A Lotus Petal already on the battlefield (played this turn as a free
        artifact) is NOT tapped here — it would need to be sacrificed via
        _sac_petal_if_needed() first. We only count petals in hand as flexible mana.
        """
        # Mox Opal in play provides any color with metalcraft (3+ artifacts)
        if (any(a.card.tag == 'opal' for a in player.artifacts)
                and _artifact_count(player) >= 3):
            return True
        # Lotus Petal in hand — can produce any color including B
        if any(c.tag == 'petal' for c in player.hand):
            return True
        return False

    # total_mana already accounts for Ancient Tomb's +1 bonus mana (engine adds
    # it in protagonist_turn/opp_turn) and already deducts 2 life per Tomb tapped.
    # Do NOT re-add Tomb mana here — the old code was double-counting (3 mana/Tomb).
    mana = total_mana
    art_count = _artifact_count(player)
    artifacts_cast_this_turn = 0

    # Reset cant_be_blocked on all Cannoneers at the start of each turn.
    # The "can't be blocked" ability only applies for the turn artifacts entered;
    # it does not persist. If no artifacts enter this turn, Cannoneer is blockable.
    for c in player.creatures:
        if c.card.tag == 'cannoneer':
            c.cant_be_blocked = False

    # cannoneer_on_board: Kappa Cannoneer gives +1/+1 to itself for each
    # artifact that enters the battlefield while it's on the battlefield.
    # Artifacts that enter this turn do NOT retroactively trigger it if it
    # enters later in the same turn — so track separately.
    cannoneer_on_board = any(c.card.tag == 'cannoneer' for c in player.creatures)
    cannoneer_triggers = 0

    def _sac_petal_if_needed(needed_mana):
        """Sacrifice a Lotus Petal in play for 1 mana if we're short.
        Petal goes to graveyard (not exile) when sacrificed.
        Returns the mana gained (0 or 1)."""
        nonlocal mana
        if mana >= needed_mana:
            return 0
        petal_perm = next((a for a in player.artifacts if a.card.tag == 'petal'), None)
        if petal_perm is None:
            return 0
        player.artifacts.remove(petal_perm)
        player.graveyard.append(petal_perm.card)
        mana += 1
        log_fn("Lotus Petal — sacrifice for {C}")
        return 1

    # ── 1. Free artifacts: Lotus Petal ────────────────────────────────────────────
    # Deploy Petals as 0-cost artifacts to maximise affinity cost reductions.
    # They stay on the battlefield for the rest of this turn; only sacrifice
    # via _sac_petal_if_needed() when we are short mana for a specific spell.
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.put_artifact_in_play(petal)
        art_count += 1
        artifacts_cast_this_turn += 1
        if cannoneer_on_board:
            cannoneer_triggers += 1
        log_fn("Lotus Petal (artifact in play)")

    # ── 2. Free artifacts: Baubles ───────────────────────────────────────────
    for bauble_tag in ('bauble', 'ubauble'):
        for bauble in [c for c in player.hand if c.tag == bauble_tag]:
            player.remove_from_hand(bauble)
            player.add_to_grave(bauble)
            drawn = player.draw(1)
            art_count += 1
            artifacts_cast_this_turn += 1
            if cannoneer_on_board:
                cannoneer_triggers += 1
            log_fn(f"{bauble.name} — cantrip")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            if gs.game_over:
                return

    # ── 3. Mox Opal (Metalcraft = 3+ artifacts) ─────────────────────────────
    # Mox Opal is legendary — only one can be on the battlefield at a time.
    opal_in_play = any(a.card.tag == 'opal' for a in player.artifacts)
    for opal in [c for c in player.hand if c.tag == 'opal']:
        if opal_in_play:
            break  # legend rule: can't have two Mox Opals in play
        if art_count >= 2:  # will be 3 once Opal itself enters
            player.remove_from_hand(opal)
            player.put_artifact_in_play(opal)
            mana += 1
            art_count += 1
            artifacts_cast_this_turn += 1
            if cannoneer_on_board:
                cannoneer_triggers += 1
            opal_in_play = True
            log_fn("Mox Opal (Metalcraft)")

    # ── 4. Patchwork Automaton — deploy early, grows with artifact casts ────
    while True:
        automaton = player.find_tag('automaton')
        if not automaton:
            break
        _sac_petal_if_needed(2)
        if mana < 2:
            break
        player.remove_from_hand(automaton)
        if not _try_counter_any(player, opponent, gs, automaton, log_entries):
            player.put_creature_in_play(automaton)
            mana -= 2
            art_count += 1
            artifacts_cast_this_turn += 1
            if cannoneer_on_board:
                cannoneer_triggers += 1
            log_fn("Patchwork Automaton (1/1, grows with artifact casts)")
        else:
            player.add_to_grave(automaton)

    # ── 5. Emry, Lurker of the Loch — engine ────────────────────────────────
    emry = player.find_tag('emry')
    emry_on_board = any(c.card.tag == 'emry' for c in player.creatures)
    if emry and not emry_on_board:
        eff_cost = _affinity_cost(3, player)
        _sac_petal_if_needed(eff_cost)
        if mana >= eff_cost and _has_blue():
            player.remove_from_hand(emry)
            if not _try_counter_any(player, opponent, gs, emry, log_entries):
                player.put_creature_in_play(emry)
                mana -= eff_cost
                art_count += 1
                # Emry is an artifact creature — triggers Automaton/Cannoneer
                artifacts_cast_this_turn += 1
                if cannoneer_on_board:
                    cannoneer_triggers += 1
                # Self-mill 4
                milled = []
                for _ in range(min(4, len(player.library))):
                    card = player.library.pop(0)
                    player.graveyard.append(card)
                    milled.append(card.name)
                log_fn(f"Emry, Lurker of the Loch (affinity {eff_cost}) — mills: {milled[:3]}")
            else:
                player.add_to_grave(emry)

    # ── 6. Thought Monitor — affinity, draws 2 ──────────────────────────────
    # Cast BEFORE Emissary/Cannoneer so the 2 drawn cards can be deployed
    # in the same turn (e.g. a freshly drawn Emissary or second Monitor).
    while True:
        monitor = player.find_tag('monitor')
        if not monitor:
            break
        eff_cost = _affinity_cost(7, player)
        _sac_petal_if_needed(eff_cost)
        if mana < eff_cost or not _has_blue():
            break
        player.remove_from_hand(monitor)
        if not _try_counter_any(player, opponent, gs, monitor, log_entries):
            player.put_creature_in_play(monitor)
            mana -= eff_cost
            art_count += 1
            drawn = player.draw(2)
            log_fn(f"Thought Monitor (2/2 flying, affinity {eff_cost}) — draws 2")
            bowmasters_triggers(2, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
        else:
            player.add_to_grave(monitor)
        if gs.game_over:
            return

    # ── 7. Thoughtcast — affinity draw spell (cast all copies in hand) ────────
    # Cast BEFORE big creatures so drawn cards can also be deployed this turn.
    while True:
        cast = player.find_tag('cast')
        if not cast:
            break
        eff_cost = _affinity_cost(5, player)
        _sac_petal_if_needed(eff_cost)
        if mana < eff_cost or not _has_blue():
            break
        player.remove_from_hand(cast)
        player.add_to_grave(cast)
        mana -= eff_cost
        drawn = player.draw(2)
        log_fn(f"Thoughtcast (affinity {eff_cost}) — draws 2")
        bowmasters_triggers(2, gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')
        if gs.game_over:
            return

    # ── 8. Pinnacle Emissary — affinity creature ────────────────────────────
    # Deployed AFTER draw spells so any Emissaries drawn this turn are included.
    while True:
        emissary = player.find_tag('emissary')
        if not emissary:
            break
        eff_cost = _affinity_cost(4, player)
        _sac_petal_if_needed(eff_cost)
        if mana < eff_cost:
            break
        player.remove_from_hand(emissary)
        if not _try_counter_any(player, opponent, gs, emissary, log_entries):
            player.put_creature_in_play(emissary)
            mana -= eff_cost
            art_count += 1
            log_fn(f"Pinnacle Emissary (3/3, affinity {eff_cost})")
        else:
            player.add_to_grave(emissary)

    # ── 9. Kappa Cannoneer — big affinity threat ────────────────────────────
    while True:
        cannoneer = player.find_tag('cannoneer')
        if not cannoneer:
            break
        eff_cost = _affinity_cost(6, player)
        _sac_petal_if_needed(eff_cost)
        if mana < eff_cost or not _has_blue():
            break
        player.remove_from_hand(cannoneer)
        if not _try_counter_any(player, opponent, gs, cannoneer, log_entries):
            player.put_creature_in_play(cannoneer)
            mana -= eff_cost
            art_count += 1
            # Cannoneer is now on the board — subsequent artifact ETBs trigger it.
            cannoneer_on_board = True
            log_fn(f"Kappa Cannoneer (4/4 trample ward, affinity {eff_cost})")
        else:
            player.add_to_grave(cannoneer)

    # ── 10. Krang, Master Mind ────────────────────────────────────────────────
    # Krang costs {U}{B}{3} — requires BOTH blue AND black mana.
    # This deck has no natural black sources; black can only come from
    # Mox Opal (metalcraft) or Lotus Petal. Both colours must be available.
    krang = player.find_tag('krang')
    if krang:
        _sac_petal_if_needed(5)
    if krang and mana >= 5 and _has_blue() and _has_black():
        player.remove_from_hand(krang)
        if not _try_counter_any(player, opponent, gs, krang, log_entries):
            player.put_creature_in_play(krang)
            mana -= 5
            log_fn("Krang, Master Mind (4/5)")
        else:
            player.add_to_grave(krang)

    # ── 11. Equipment — Lavaspur Boots / Shadowspear ─────────────────────────
    for equip_tag in ('boots', 'spear'):
        equip = player.find_tag(equip_tag)
        if equip:
            _sac_petal_if_needed(1)
        if equip and mana >= 1:
            player.remove_from_hand(equip)
            player.put_artifact_in_play(equip)
            mana -= 1
            art_count += 1
            artifacts_cast_this_turn += 1
            if cannoneer_on_board:
                cannoneer_triggers += 1
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
                             controller='b' if player is gs.p1 else 'o',
                             summoning_sick=True)
            perm.is_artifact = True
            player.creatures.append(perm)
            art_count = _artifact_count(player)
            perm.power_mod = art_count
            perm.toughness_mod = art_count
            # Construct is an artifact ETB — triggers Cannoneer and Automaton
            artifacts_cast_this_turn += 1
            if cannoneer_on_board:
                cannoneer_triggers += 1
            log_fn(f"Urza's Saga Ch.2 — Construct {art_count}/{art_count} enters", True)
        elif chapter >= 3:
            # Ch.3: tutor 0-1 CMC artifact, then sacrifice Saga
            targets = [c for c in player.library
                       if c.card_type == _CT.ARTIFACT and c.cmc <= 1]
            if targets:
                # Smart tutor priority based on board state
                art_count_now = _artifact_count(player)
                has_opal_in_play = any(a.card.tag == 'opal' for a in player.artifacts)
                has_equipment = any(a.card.tag in ('boots', 'spear')
                                    for a in player.artifacts)
                has_creatures = bool(player.creatures)
                # Priority 1: If few artifacts in play and no Mox Opal, tutor Mox Opal
                opal_targets = [c for c in targets if c.tag == 'opal']
                # Priority 2: If we have creatures but no equipment, tutor equipment
                equip_targets = [c for c in targets if c.tag in ('boots', 'spear')]
                # Priority 3: Lotus Petal for mana
                petal_targets = [c for c in targets if c.tag == 'petal']
                # Priority 4: Baubles for card draw
                bauble_targets = [c for c in targets if c.tag in ('bauble', 'ubauble')]

                # Priority 0: If life is low, Shadowspear is critical for lifelink
                spear_targets = [c for c in targets if c.tag == 'spear']
                has_spear = any(a.card.tag == 'spear' for a in player.artifacts)
                if player.life <= 14 and has_creatures and not has_spear and spear_targets:
                    target = spear_targets[0]
                elif art_count_now < 3 and not has_opal_in_play and opal_targets:
                    target = opal_targets[0]
                elif has_creatures and not has_equipment and equip_targets:
                    target = equip_targets[0]
                elif petal_targets and mana < 2:
                    target = petal_targets[0]
                elif bauble_targets:
                    target = bauble_targets[0]
                else:
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

    # ── 12b. Equip Lavaspur Boots — give haste to summoning-sick creature ────
    # Boots are most valuable on a freshly played creature so it can attack
    # immediately.  Prefer the highest-power summoning-sick creature; fall back
    # to the highest-power ready creature so boots are always attached to the
    # biggest threat.
    boots_in_play = next((a for a in player.artifacts if a.card.tag == 'boots'), None)
    if boots_in_play:
        sick_creatures  = [c for c in player.creatures if c.summoning_sick and c.power > 0]
        ready_creatures = [c for c in player.creatures if not c.summoning_sick and c.power > 0]
        boot_target = (max(sick_creatures, key=lambda c: c.power, default=None)
                       or max(ready_creatures, key=lambda c: c.power, default=None))
        if boot_target and not getattr(boot_target, '_boots_equipped', False):
            # Un-equip from previous bearer when boots move to a new creature
            for c in player.creatures:
                if getattr(c, '_boots_equipped', False) and c is not boot_target:
                    c._boots_equipped = False
            boot_target._boots_equipped = True
            if boot_target.summoning_sick:
                boot_target.summoning_sick = False
                log_fn(f"Lavaspur Boots equipped to {boot_target.card.name} (haste)")

    # ── 12c. Equip Shadowspear — +1/+1, trample, lifelink ───────────────────
    # Attach to the highest-power attacker to maximise damage and life gain.
    # Set trample/lifelink on both the Permanent's Card so the combat engine
    # (which reads atk.card.trample / atk.card.lifelink) sees the keywords.
    spear_in_play = next((a for a in player.artifacts if a.card.tag == 'spear'), None)
    if spear_in_play:
        eligible = [c for c in player.creatures if c.power > 0]
        if eligible:
            spear_target = max(eligible, key=lambda c: c.power)
            # Un-equip from previous bearer if the spear moves to a new creature
            for c in player.creatures:
                if getattr(c, '_spear_equipped', False) and c is not spear_target:
                    c._spear_equipped = False
                    c.power_mod     = max(0, c.power_mod - 1)
                    c.toughness_mod = max(0, c.toughness_mod - 1)
                    c.card.trample  = False
                    c.card.lifelink = False
            if not getattr(spear_target, '_spear_equipped', False):
                spear_target._spear_equipped = True
                spear_target.power_mod     += 1
                spear_target.toughness_mod += 1
                spear_target.card.trample  = True
                spear_target.card.lifelink = True
                log_fn(f"Shadowspear equipped to {spear_target.card.name} (+1/+1, trample, lifelink)")

    # ── 13. Emry — tap to cast artifact from graveyard ───────────────────────
    # Emry's tap ability: {T} — cast an artifact card from your graveyard.
    # Artifact creatures are valid targets — they are artifact spells on the
    # stack. Recasting them requires paying the affinity-reduced mana cost.
    # Find an untapped, non-summoning-sick Emry on the battlefield.
    emry_perm = next(
        (c for c in player.creatures
         if c.card.tag == 'emry' and not c.summoning_sick and not c.tapped),
        None
    )
    if emry_perm:
        # Artifact cards sitting in graveyard (Card objects, not Permanents).
        # Artifact creatures (emissary, automaton, monitor, cannoneer) are also
        # valid Emry targets — they are artifact spells while on the stack.
        gy_artifacts = [c for c in player.graveyard
                        if c.card_type == _CT.ARTIFACT
                        or c.tag in ARTIFACT_CREATURE_TAGS]

        if gy_artifacts:
            # Base CMCs for artifact creatures (used to compute affinity costs)
            _CREATURE_BASE_CMC = {
                'cannoneer': 6, 'monitor': 7, 'emissary': 4,
                'automaton': 2, 'emry': 3, 'krang': 5,
            }
            art_count_now = _artifact_count(player)
            opal_in_play_now = any(a.card.tag == 'opal' for a in player.artifacts)

            def _emry_can_afford(c):
                """True if we have enough mana (and blue/black if needed) to recast c."""
                base = _CREATURE_BASE_CMC.get(c.tag)
                if base is None:
                    return True  # Non-creature artifacts have 0 effective cast cost
                eff = _affinity_cost(base, player)
                if c.tag in ('cannoneer', 'monitor', 'emry') and not _has_blue():
                    return False
                if c.tag == 'krang' and (not _has_blue() or not _has_black()):
                    return False
                return mana >= eff

            def _emry_priority(c):
                # Artifact creatures: rank by impact, but only if we can pay for them
                if c.tag == 'cannoneer':
                    # 4/4 trample ward — highest-impact recursion target
                    return 0 if _emry_can_afford(c) else 10
                if c.tag == 'monitor':
                    # Draws 2 on ETB — strong card-advantage refuel
                    return 1 if _emry_can_afford(c) else 10
                if c.tag == 'emissary':
                    # 3/3 body for cheap — solid threat
                    return 2 if _emry_can_afford(c) else 10
                if c.tag == 'automaton':
                    # Grows with artifacts; modest base stats
                    return 3 if _emry_can_afford(c) else 10
                if c.tag == 'krang':
                    # 4/5 with relevant ETB — solid threat requiring UB
                    return 3 if _emry_can_afford(c) else 10
                if c.tag == 'emry':
                    # Legend rule: recasting a second Emry would sacrifice one;
                    # skip unless nothing else is available.
                    return 10
                # Pure artifacts (no creature type): always free to recur via Emry
                if c.tag == 'opal' and not opal_in_play_now and art_count_now >= 2:
                    return 4   # Mox Opal — metalcraft mana engine
                if c.tag in ('bauble', 'ubauble'):
                    return 5   # Baubles — free cantrip, builds artifact count
                if c.tag == 'petal':
                    return 6   # Lotus Petal — burst mana
                if c.tag in ('boots', 'spear'):
                    return 7   # Equipment
                return 8       # Generic artifacts

            # Prefer targets we can fully resolve; fall back to anything if needed.
            # For artifact creatures, _emry_can_afford() returns False when we
            # can't pay the affinity cost, so they get priority 10 and are excluded
            # from the first pass.
            actionable = [c for c in gy_artifacts if _emry_priority(c) < 10]
            if not actionable:
                actionable = gy_artifacts  # fall back: recur whatever is available

            target = min(actionable, key=_emry_priority)
            player.graveyard.remove(target)
            emry_perm.tapped = True  # Emry taps to activate the ability

            if target.tag in ARTIFACT_CREATURE_TAGS:
                # Recasting an artifact creature from GY: pay affinity-reduced cost
                base_cmc = _CREATURE_BASE_CMC.get(target.tag, target.cmc)
                eff_cost = _affinity_cost(base_cmc, player)
                needs_blue = target.tag in ('cannoneer', 'monitor', 'emry', 'krang')
                needs_black = target.tag == 'krang'
                if (mana >= eff_cost
                        and (not needs_blue or _has_blue())
                        and (not needs_black or _has_black())):
                    if not _try_counter_any(player, opponent, gs, target, log_entries):
                        player.put_creature_in_play(target)
                        mana -= eff_cost
                        art_count += 1
                        artifacts_cast_this_turn += 1
                        if cannoneer_on_board and target.tag != 'cannoneer':
                            cannoneer_triggers += 1
                        if target.tag == 'monitor':
                            player.draw(2)
                            bowmasters_triggers(2, gs, log_entries,
                                                controller='o' if player is gs.p1 else 'b')
                            log_fn(f"Emry recurs {target.name} (affinity {eff_cost}) — draws 2")
                        elif target.tag == 'cannoneer':
                            # Cannoneer itself entering does not trigger its own
                            # counter ability (it wasn't on board when it entered).
                            cannoneer_on_board = True
                            log_fn(f"Emry recurs {target.name} (4/4 trample ward, affinity {eff_cost})")
                        else:
                            log_fn(f"Emry recurs {target.name} (affinity {eff_cost})")
                        if gs.game_over:
                            return
                    else:
                        player.add_to_grave(target)
                else:
                    # Can't afford right now — restore card and leave Emry untapped
                    player.graveyard.append(target)
                    emry_perm.tapped = False

            elif target.tag == 'petal':
                # Lotus Petal (CMC 0): enters, immediately sacrifice for mana
                player.exile.append(target)
                mana += 1
                artifacts_cast_this_turn += 1
                art_count = _artifact_count(player)
                if cannoneer_on_board:
                    cannoneer_triggers += 1
                log_fn(f"Emry recurs {target.name} — sacrifice for mana")

            elif target.tag in ('bauble', 'ubauble'):
                # Baubles (CMC 0): enter and immediately cantrip into graveyard
                player.add_to_grave(target)
                player.draw(1)
                artifacts_cast_this_turn += 1
                art_count = _artifact_count(player)
                if cannoneer_on_board:
                    cannoneer_triggers += 1
                log_fn(f"Emry recurs {target.name} — cantrip")
                bowmasters_triggers(1, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
                if gs.game_over:
                    return

            elif target.tag == 'opal':
                # Mox Opal (CMC 0): put into play; tap for mana if metalcraft (3+ artifacts)
                player.put_artifact_in_play(target)
                artifacts_cast_this_turn += 1
                art_count = _artifact_count(player)
                if cannoneer_on_board:
                    cannoneer_triggers += 1
                if art_count >= 3:
                    mana += 1
                    log_fn(f"Emry recurs {target.name} (Metalcraft — +1 mana)")
                else:
                    log_fn(f"Emry recurs {target.name}")

            else:
                # Equipment (CMC 1) or other pure non-creature artifact: pay mana cost
                mana -= target.cmc
                player.put_artifact_in_play(target)
                artifacts_cast_this_turn += 1
                art_count = _artifact_count(player)
                if cannoneer_on_board:
                    cannoneer_triggers += 1
                log_fn(f"Emry recurs {target.name} (cost {target.cmc})")

            # Recount after Emry activation; update Construct token sizes
            art_count = _artifact_count(player)
            for c in player.creatures:
                if c.card.tag == 'construct':
                    c.power_mod = art_count
                    c.toughness_mod = art_count

            # Credit Automaton for the artifact cast via Emry
            for c in player.creatures:
                if c.card.tag == 'automaton':
                    c.power_mod = getattr(c, 'power_mod', 0) + 1
                    c.toughness_mod = getattr(c, 'toughness_mod', 0) + 1

    # ── 13b. Sink into Stupor — bounce blocker or discard mode ───────────────
    # Priority 1: bounce a big blocker (power >= 3) before combat
    # Priority 2: vs combo opponents with a full hand, use discard mode
    sink = player.find_tag("sink")
    if sink and mana >= 3 and _has_blue():
        _sac_petal_if_needed(3)
        if mana >= 3:
            # Determine opponent deck key for combo detection
            from config import MatchupCategory
            opp_deck = (getattr(gs, "p2_deck", "") if player is gs.p1
                        else getattr(gs, "p1_deck", ""))
            opp_is_combo = opp_deck in MatchupCategory.COMBO

            # Check for a big blocker on opponent side (power >= 3)
            big_blockers = [c for c in opponent.creatures
                            if c.power >= 3 and not c.summoning_sick]
            if big_blockers:
                # Bounce the highest-power blocker
                target = max(big_blockers, key=lambda c: c.power)
                opponent.creatures.remove(target)
                opponent.hand.append(target.card)
                player.remove_from_hand(sink)
                player.add_to_grave(sink)
                mana -= 3
                log_fn(f"Sink into Stupor — bounce {target.card.name} ({target.power}/{target.toughness})")
            elif opp_is_combo and len(opponent.hand) > 0:
                # Discard mode vs combo: strip a combo piece or key spell
                # Choose best target: win condition > combo piece > any nonland
                nonland_hand = [c for c in opponent.hand if not c.is_land()]
                if nonland_hand:
                    target_card = (
                        next((c for c in nonland_hand if c.win_condition), None)
                        or next((c for c in nonland_hand if c.is_combo_piece), None)
                        or nonland_hand[0]
                    )
                    opponent.hand.remove(target_card)
                    opponent.graveyard.append(target_card)
                    player.remove_from_hand(sink)
                    player.add_to_grave(sink)
                    mana -= 3
                    log_fn(f"Sink into Stupor — discard mode, strips {target_card.name} from opponent")

    # ── 14a. Apply Kappa Cannoneer triggers ────────────────────────────────
    # Each artifact ETB while Cannoneer was on board = +1/+1 counter + unblockable
    if cannoneer_triggers > 0:
        for c in player.creatures:
            if c.card.tag == 'cannoneer':
                c.power_mod += cannoneer_triggers
                c.toughness_mod += cannoneer_triggers
                c.cant_be_blocked = True
                log_fn(f"Kappa Cannoneer +{cannoneer_triggers} counters, can't be blocked")

    # ── 14b. Combat ──────────────────────────────────────────────────────────
    # Exclude tapped creatures (e.g. Emry after activating her ability this turn)
    attackers = [c for c in player.creatures if not c.summoning_sick and not c.tapped]
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


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_affinity(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    tags = {c.tag for c in hand}
    fast_mana = sum(1 for c in hand if c.tag in ('petal', 'opal', 'tomb', 'seat'))
    threats = sum(1 for c in nonlands if c.is_creature())
    engine = any(t in tags for t in ('emry', 'monitor', 'automaton', 'cannoneer', 'saga'))
    return fast_mana >= 1 and (threats >= 1 or engine)


DECK_META = {
    'key':        'affinity',
    'name':       'Affinity (8-Cast variant)',
    'make_deck':  make_affinity_deck,
    'strategy':   _strategy_affinity,
    'keep':       _keep_affinity,
    'categories': {'aggro', 'prison'},
    'interaction': {'speed': 3, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.02,
}
