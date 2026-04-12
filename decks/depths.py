"""
Dark Depths — Legacy land combo deck.

The combo: Dark Depths (legendary land, enters with 10 ice counters,
when 0 counters -> sacrifice -> create Marit Lage 20/20 flying indestructible)
+ Thespian's Stage (copy Dark Depths, copied version has 0 counters -> triggers).

Key lines:
- T2: Depths in play + Stage in play + 2 mana -> copy -> Marit Lage -> attack next turn
- T1: Mox Diamond + Exploration -> accelerate into the combo
- Crop Rotation: instant-speed land tutor (sacrifice a land to find the missing piece)
- Elvish Reclaimer / Knight of the Reliquary: creature-based land tutors
- Green Sun's Zenith: tutor Reclaimer or Dryad Arbor for mana
"""

import sys
import random
sys.path.insert(0, '/home/claude/mtg_sim')

from cards import creature, instant, sorcery, artifact, enchantment

# ─── Deck construction ────────────────────────────────────────────────────────

def make_depths_deck():
    d = []
    from rules import Card, CardType

    # ── Combo Lands (8) ──────────────────────────────────────────────────────
    # Dark Depths: legendary land, combo piece
    for _ in range(4):
        c = Card('Dark Depths', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='depths', produces={'C'}, gy_type='land')
        d.append(c)

    # Thespian's Stage: copy target land (copies Depths -> 0 counters -> Marit Lage)
    for _ in range(3):
        c = Card("Thespian's Stage", CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='stage', produces={'C'}, gy_type='land')
        d.append(c)

    # ── Land Tutors / Combo Enablers (13) ────────────────────────────────────
    # Crop Rotation: sacrifice a land, tutor any land to battlefield
    # Backup tutor — instant speed but risky (sac is cost, countered = 2-for-1)
    for _ in range(3):
        c = instant('Crop Rotation', 1, {'G': 1}, {'G'}, tag='crop')
        c.is_combo_piece = True
        d.append(c)

    # Elvish Reclaimer: 1/2, sac a land -> tutor any land
    for _ in range(4):
        d.append(creature('Elvish Reclaimer', 1, {'G': 1}, {'G'}, 1, 2,
                          tag='reclaimer'))

    # Sylvan Scrying: primary land tutor (sorcery speed, to hand)
    for _ in range(3):
        d.append(sorcery('Sylvan Scrying', 2, {'G': 1, 'generic': 1}, {'G'},
                         tag='scrying'))

    # Green Sun's Zenith: tutor green creature to battlefield
    # Combo piece: fetches Elvish Reclaimer which assembles the combo
    for _ in range(2):
        c = sorcery("Green Sun's Zenith", 1, {'G': 1}, {'G'}, tag='gsz')
        c.is_combo_piece = True
        d.append(c)

    # Knight of the Reliquary: backup beater + land tutor
    for _ in range(2):
        d.append(creature('Knight of the Reliquary', 3,
                          {'G': 1, 'W': 1, 'generic': 1}, {'G', 'W'},
                          4, 4, tag='knight'))

    # ── Acceleration (6) ─────────────────────────────────────────────────────
    # Mox Diamond: discard a land -> mana rock
    for _ in range(3):
        d.append(artifact('Mox Diamond', 0, {}, tag='mox_diamond'))

    # Exploration: extra land drop per turn
    for _ in range(3):
        d.append(enchantment('Exploration', 1, {'G': 1}, {'G'},
                             tag='exploration'))

    # ── Card Selection (5) ───────────────────────────────────────────────────
    # Once Upon a Time: free if first spell, dig for creature or land
    for _ in range(3):
        d.append(instant('Once Upon a Time', 2, {'G': 1, 'generic': 1}, {'G'},
                         tag='once', is_cantrip=True))

    # Sylvan Library: draw engine
    for _ in range(2):
        d.append(enchantment('Sylvan Library', 2, {'G': 1, 'generic': 1}, {'G'},
                             tag='sylvan'))

    # ── Disruption (2) ──────────────────────────────────────────────────────
    # Thoughtseize: hand disruption to clear counterspells / removal
    for _ in range(2):
        d.append(sorcery('Thoughtseize', 1, {'B': 1}, {'B'}, tag='ts'))

    # ── Creatures (3) ────────────────────────────────────────────────────────
    # Dryad Arbor: land + creature, GSZ for 0 target
    for _ in range(1):
        d.append(creature('Dryad Arbor', 0, {}, {'G'}, 1, 1, tag='arbor'))

    # Endurance: graveyard hate + flash 3/4
    for _ in range(3):
        d.append(creature('Endurance', 3, {'G': 2, 'generic': 1}, {'G'},
                          3, 4, tag='endurance', flash=True, reach=True))

    # ── Utility Lands (7) ────────────────────────────────────────────────────
    # Wasteland: destroy nonbasic land
    for _ in range(3):
        c = Card('Wasteland', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='waste', produces={'C'}, gy_type='land')
        d.append(c)

    # Bojuka Bog: graveyard hate land
    for _ in range(2):
        c = Card('Bojuka Bog', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='bog', produces={'B'}, gy_type='land')
        d.append(c)

    # Sejiri Steppe: protection land (Crop Rotation target for evasion)
    for _ in range(2):
        c = Card('Sejiri Steppe', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='steppe', produces={'W'}, gy_type='land')
        d.append(c)

    # ── Fetch Lands (8) ──────────────────────────────────────────────────────
    for _ in range(4):
        c = Card('Windswept Heath', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land',
                 fetch_targets={'Forest', 'Plains'})
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    for _ in range(4):
        c = Card('Verdant Catacombs', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land',
                 fetch_targets={'Swamp', 'Forest'})
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # ── Dual Lands (4) ──────────────────────────────────────────────────────
    for _ in range(2):
        c = Card('Savannah', CardType.LAND, cmc=0, mana_cost={},
                 colors={'G', 'W'}, tag='dual', produces={'G', 'W'},
                 subtypes={'Forest', 'Plains'}, gy_type='land')
        d.append(c)

    for _ in range(2):
        c = Card('Bayou', CardType.LAND, cmc=0, mana_cost={},
                 colors={'B', 'G'}, tag='dual', produces={'B', 'G'},
                 subtypes={'Swamp', 'Forest'}, gy_type='land')
        d.append(c)

    # ── Basic Lands (3) ─────────────────────────────────────────────────────
    for _ in range(2):
        c = Card('Forest', CardType.LAND, cmc=0, mana_cost={},
                 colors={'G'}, tag='basic', produces={'G'}, gy_type='land',
                 subtypes={'Forest'}, is_basic=True)
        d.append(c)

    for _ in range(1):
        c = Card('Plains', CardType.LAND, cmc=0, mana_cost={},
                 colors={'W'}, tag='basic', produces={'W'}, gy_type='land',
                 subtypes={'Plains'}, is_basic=True)
        d.append(c)

    assert len(d) == 60, f"Dark Depths deck: {len(d)} cards (expected 60)"
    return d


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _has_combo_in_play(player):
    """Check if both combo lands are on the battlefield."""
    depths = any(l.card.tag == 'depths' for l in player.lands)
    stage = any(l.card.tag == 'stage' for l in player.lands)
    return depths, stage


def _find_land_in_play(player, tag):
    """Find a land permanent by tag."""
    return next((l for l in player.lands if l.card.tag == tag), None)


def _find_expendable_land(player):
    """Find a land that can be sacrificed for Crop Rotation / Reclaimer.
    Prefer: fetch > waste > bog > basic > dual. Never sacrifice combo pieces."""
    priority = ['fetch', 'waste', 'bog', 'basic', 'dual']
    for tag in priority:
        land = next((l for l in player.lands if l.card.tag == tag), None)
        if land:
            return land
    return None


def _sacrifice_land(player, land_perm):
    """Remove a land permanent from play and put it into the graveyard."""
    if land_perm in player.lands:
        player.lands.remove(land_perm)
        player.graveyard.append(land_perm.card)


def _tutor_land_to_play(player, tag, log_fn):
    """Find a land card in the library by tag and put it onto the battlefield."""
    from rules import LandPermanent
    target = next((c for c in player.library if c.tag == tag), None)
    if target:
        player.library.remove(target)
        perm = LandPermanent(card=target, controller=player.name, tapped=False)
        player.lands.append(perm)
        log_fn(f"  -> {target.name} enters the battlefield")
        return perm
    return None


def _tutor_land_to_hand(player, tag, log_fn):
    """Find a land card in the library by tag and add it to hand."""
    target = next((c for c in player.library if c.tag == tag), None)
    if target:
        player.library.remove(target)
        player.hand.append(target)
        log_fn(f"  -> {target.name} to hand")
        return target
    return None


def _missing_combo_piece_tag(player):
    """Return the tag of the missing combo land, or None if both in play."""
    depths, stage = _has_combo_in_play(player)
    if not depths:
        return 'depths'
    if not stage:
        return 'stage'
    return None


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_depths(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Dark Depths combo strategy.

    Priority:
    1. Activate combo if both lands in play (Stage copies Depths -> Marit Lage)
    2. Deploy acceleration (Mox Diamond, Exploration)
    3. Cast cantrips (Once Upon a Time)
    4. Land tutors to assemble combo (Crop Rotation, Reclaimer, Scrying, GSZ)
    5. Deploy backup creatures (Knight, Endurance)
    6. Attack with whatever is available (Marit Lage, Knight, etc.)
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare
    from rules import LandPermanent

    mana = total_mana
    marit_lage_created = False

    # ── Check if Marit Lage already in play ──────────────────────────────────
    marit_in_play = [p for p in player.creatures if p.card.tag == 'marit']

    # ── Step 1: Activate combo — Stage copies Depths ─────────────────────────
    depths_in_play, stage_in_play = _has_combo_in_play(player)
    if depths_in_play and stage_in_play and mana >= 2 and not marit_in_play:
        log_fn("★ Stage copies Depths → Marit Lage 20/20!", True)
        # Remove the Stage (legend rule: copied Depths is legendary,
        # sacrifice the original Depths)
        stage_perm = _find_land_in_play(player, 'stage')
        depths_perm = _find_land_in_play(player, 'depths')
        if stage_perm:
            player.lands.remove(stage_perm)
            player.graveyard.append(stage_perm.card)
        if depths_perm:
            player.lands.remove(depths_perm)
            player.graveyard.append(depths_perm.card)
        mana -= 2
        # Create Marit Lage token
        marit = creature('Marit Lage', 0, {}, set(), 20, 20, tag='marit',
                         flying=True, indestructible=True)
        perm = player.put_creature_in_play(marit)
        # Marit Lage token has summoning sickness (CR 302.6).
        # It enters the battlefield this turn but can't attack until next turn.
        # This gives the opponent one more draw step to find an answer.
        marit_lage_created = True
        marit_in_play = [perm]

    # ── Step 2: Mox Diamond (discard a land for fast mana) ───────────────────
    mox = player.find_tag('mox_diamond')
    if mox:
        # Need a land to discard
        land_to_discard = next((c for c in player.hand
                                if c.is_land() and c is not mox
                                and c.tag not in ('depths', 'stage')), None)
        if not land_to_discard:
            # Desperate: discard a combo piece if we have a duplicate
            land_to_discard = next((c for c in player.hand
                                    if c.is_land() and c is not mox), None)
        if land_to_discard:
            player.remove_from_hand(mox)
            player.put_artifact_in_play(mox)
            player.remove_from_hand(land_to_discard)
            player.graveyard.append(land_to_discard)
            mana += 1
            log_fn(f"Mox Diamond (discard {land_to_discard.name}) → mana={mana}")

    # ── Step 3: Exploration (extra land drops) ───────────────────────────────
    expl = player.find_tag('exploration')
    if expl and mana >= 1:
        if not _try_counter_any(player, opponent, gs, expl, log_entries):
            player.remove_from_hand(expl)
            player.put_enchantment_in_play(expl)
            mana -= 1
            log_fn("Exploration → extra land drops")
            # Play an extra land if we have one
            extra_land = next((c for c in player.hand if c.is_land()), None)
            if extra_land:
                player.remove_from_hand(extra_land)
                perm = LandPermanent(card=extra_land, controller=player.name,
                                     tapped=False)
                player.lands.append(perm)
                if extra_land.produces:
                    mana += 1
                log_fn(f"  Extra land: {extra_land.name}")
        else:
            player.add_to_grave(expl)
            log_fn("Exploration countered")

    # ── Step 4: Once Upon a Time (cantrip / dig for combo pieces) ────────────
    once = player.find_tag('once')
    if once:
        spells_cast = getattr(player, 'spells_cast_this_turn', 0)
        cost = 0 if spells_cast == 0 else 2  # free if first spell
        if mana >= cost:
            player.remove_from_hand(once)
            player.add_to_grave(once)
            mana -= cost
            player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
            # Simulate: look at top 5, take best creature or land
            player.draw(1)
            log_fn(f"Once Upon a Time ({'free' if cost == 0 else 'paid'}) → dig")
            if gs.bowmasters_on_board:
                bowmasters_triggers(1, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')

    # ── Step 5: Sylvan Scrying — sorcery land tutor to hand (primary tutor) ──
    # Scrying is the main tutor: sorcery speed, gets piece to hand (not play).
    # This is slower than Crop Rotation because the land has to be played next turn.
    scrying = player.find_tag('scrying')
    missing = _missing_combo_piece_tag(player)
    scrying_resolved = False
    if scrying and missing and mana >= 2 and not marit_lage_created:
        # Check if we already have the missing piece in hand
        has_in_hand = any(c.tag == missing for c in player.hand)
        if not has_in_hand:
            if not _try_counter_any(player, opponent, gs, scrying, log_entries):
                player.remove_from_hand(scrying)
                player.add_to_grave(scrying)
                mana -= 2
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                log_fn(f"Sylvan Scrying → find {missing}")
                _tutor_land_to_hand(player, missing, log_fn)
                scrying_resolved = True
            else:
                player.add_to_grave(scrying)
                log_fn("Sylvan Scrying countered")

    # ── Step 6: Crop Rotation — instant land tutor (backup) ─────────────────
    # Crop Rotation is the backup: only fire if Scrying didn't resolve this turn
    # and we still need a combo piece. Crop Rotation can be countered (the sac
    # is a cost, so the land is lost even if countered). Also, ~30% of the time
    # the needed piece is too deep in the library (bottom 20 cards).
    crop = player.find_tag('crop')
    missing = _missing_combo_piece_tag(player)
    if crop and missing and mana >= 1 and not marit_lage_created and not scrying_resolved:
        sac_land = _find_expendable_land(player)
        if sac_land:
            if not _try_counter_any(player, opponent, gs, crop, log_entries):
                player.remove_from_hand(crop)
                player.add_to_grave(crop)
                mana -= 1
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                _sacrifice_land(player, sac_land)
                # Crop Rotation searches entire library — always finds the piece
                piece_in_lib = any(c.tag == missing for c in player.library)
                if piece_in_lib:
                    log_fn(f"★ Crop Rotation (sac {sac_land.card.name}) → find {missing}", True)
                    _tutor_land_to_play(player, missing, log_fn)
                    # Re-check combo after tutoring
                    depths_in_play, stage_in_play = _has_combo_in_play(player)
                    if depths_in_play and stage_in_play and mana >= 2 and not marit_in_play:
                        log_fn("★ Stage copies Depths → Marit Lage 20/20!", True)
                        stage_perm = _find_land_in_play(player, 'stage')
                        depths_perm = _find_land_in_play(player, 'depths')
                        if stage_perm:
                            player.lands.remove(stage_perm)
                            player.graveyard.append(stage_perm.card)
                        if depths_perm:
                            player.lands.remove(depths_perm)
                            player.graveyard.append(depths_perm.card)
                        mana -= 2
                        marit = creature('Marit Lage', 0, {}, set(), 20, 20,
                                         tag='marit', flying=True,
                                         indestructible=True)
                        perm = player.put_creature_in_play(marit)
                        # Marit Lage has summoning sickness (CR 302.6)
                        marit_lage_created = True
                        marit_in_play = [perm]
                else:
                    log_fn(f"Crop Rotation (sac {sac_land.card.name}) → piece not found in library")
            else:
                player.add_to_grave(crop)
                log_fn("Crop Rotation countered")

    # ── Step 7: Green Sun's Zenith → Elvish Reclaimer (or Dryad Arbor) ──────
    gsz = player.find_tag('gsz')
    if gsz and mana >= 2 and not marit_lage_created:
        # GSZ for 1 = Elvish Reclaimer; GSZ for 0 = Dryad Arbor
        reclaimer_in_lib = any(c.tag == 'reclaimer' for c in player.library)
        arbor_in_lib = any(c.tag == 'arbor' for c in player.library)
        if reclaimer_in_lib:
            if not _try_counter_any(player, opponent, gs, gsz, log_entries):
                player.remove_from_hand(gsz)
                player.add_to_grave(gsz)
                mana -= 2
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                target = next(c for c in player.library if c.tag == 'reclaimer')
                player.library.remove(target)
                player.put_creature_in_play(target)
                log_fn("Green Sun's Zenith → Elvish Reclaimer")
            else:
                player.add_to_grave(gsz)
                log_fn("Green Sun's Zenith countered")
        elif arbor_in_lib and mana >= 1:
            if not _try_counter_any(player, opponent, gs, gsz, log_entries):
                player.remove_from_hand(gsz)
                player.add_to_grave(gsz)
                mana -= 1
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                target = next(c for c in player.library if c.tag == 'arbor')
                player.library.remove(target)
                player.put_creature_in_play(target)
                log_fn("Green Sun's Zenith → Dryad Arbor")
            else:
                player.add_to_grave(gsz)
                log_fn("Green Sun's Zenith countered")

    # ── Step 8: Elvish Reclaimer activation (if already in play) ─────────────
    # Reclaimer requires {2}, {T}, sac a land (activated ability, not a spell).
    # Costs 2 mana + tap + sac a land. Need to pay the mana cost.
    missing = _missing_combo_piece_tag(player)
    reclaimers = [p for p in player.creatures
                  if p.card.tag == 'reclaimer' and not p.summoning_sick]
    if reclaimers and missing and mana >= 2 and not marit_lage_created:
        sac_land = _find_expendable_land(player)
        if sac_land:
            mana -= 2
            log_fn(f"★ Reclaimer activates (sac {sac_land.card.name}) → find {missing}", True)
            _sacrifice_land(player, sac_land)
            _tutor_land_to_play(player, missing, log_fn)
            # Re-check combo
            depths_in_play, stage_in_play = _has_combo_in_play(player)
            if depths_in_play and stage_in_play and mana >= 2:
                log_fn("★ Stage copies Depths → Marit Lage 20/20!", True)
                stage_perm = _find_land_in_play(player, 'stage')
                depths_perm = _find_land_in_play(player, 'depths')
                if stage_perm:
                    player.lands.remove(stage_perm)
                    player.graveyard.append(stage_perm.card)
                if depths_perm:
                    player.lands.remove(depths_perm)
                    player.graveyard.append(depths_perm.card)
                mana -= 2
                marit = creature('Marit Lage', 0, {}, set(), 20, 20,
                                 tag='marit', flying=True,
                                 indestructible=True)
                perm = player.put_creature_in_play(marit)
                # Marit Lage has summoning sickness (CR 302.6)
                marit_lage_created = True
                marit_in_play = [perm]

    # ── Step 9: Sylvan Library (draw engine) ─────────────────────────────────
    sylvan = player.find_tag('sylvan')
    if sylvan and mana >= 2 and not marit_lage_created:
        if not _try_counter_any(player, opponent, gs, sylvan, log_entries):
            player.remove_from_hand(sylvan)
            player.put_enchantment_in_play(sylvan)
            mana -= 2
            log_fn("Sylvan Library → draw engine online")
        else:
            player.add_to_grave(sylvan)
            log_fn("Sylvan Library countered")

    # ── Step 10: Deploy backup creatures ─────────────────────────────────────
    # Knight of the Reliquary (4/4 beater + land tutor)
    knight = player.find_tag('knight')
    if knight and mana >= 3 and not marit_lage_created:
        if not _try_counter_any(player, opponent, gs, knight, log_entries):
            player.remove_from_hand(knight)
            player.put_creature_in_play(knight)
            mana -= 3
            player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
            log_fn("Knight of the Reliquary (4/4)")
        else:
            player.add_to_grave(knight)
            log_fn("Knight of the Reliquary countered")

    # Endurance (flash 3/4, graveyard hate)
    endurance = player.find_tag('endurance')
    if endurance and mana >= 3 and not marit_lage_created:
        if not _try_counter_any(player, opponent, gs, endurance, log_entries):
            player.remove_from_hand(endurance)
            player.put_creature_in_play(endurance)
            mana -= 3
            player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
            log_fn("Endurance (3/4)")
        else:
            player.add_to_grave(endurance)
            log_fn("Endurance countered")

    # ── Step 11: Combat — attack with everything available ───────────────────
    if not gs.game_over:
        attackers = []
        for p in player.creatures:
            if p.summoning_sick:
                continue
            attackers.append(p)
        if attackers:
            # Prioritize Marit Lage — 20 flying damage is lethal
            marit_attackers = [a for a in attackers if a.card.tag == 'marit']
            if marit_attackers:
                log_fn("★ Marit Lage attacks! (20/20 flying indestructible)", True)
            combat_declare(player, opponent, gs, log_entries, attackers)

            if not gs.game_over and any(a.card.tag == 'marit' for a in attackers):
                # If Marit Lage connected, opponent should be dead (20 >= 20 life)
                if opponent.life <= 0:
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = "Dark Depths: Marit Lage 20/20 lethal"
                    gs.kill_turn = gs.turn

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_depths():
    results = []

    # Test 1: Deck size
    deck = make_depths_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("✓ Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for req in ['depths', 'stage', 'crop', 'reclaimer', 'gsz',
                'exploration', 'mox_diamond', 'once', 'knight']:
        assert req in tags, f"Missing: {req}"
    results.append("✓ All key cards present")

    # Test 3: Card counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1
    assert tag_counts['depths'] == 4, f"Depths count: {tag_counts['depths']}"
    assert tag_counts['stage'] == 3, f"Stage count: {tag_counts['stage']}"
    assert tag_counts['crop'] == 3, f"Crop count: {tag_counts['crop']}"
    results.append("✓ Card counts correct")

    # Test 4: Land count
    land_count = sum(1 for c in deck if c.is_land())
    results.append(f"✓ Land count: {land_count}")

    # Test 5: Bo3 smoke test
    from sim import STRATEGIES
    from cards import DECKS
    DECKS['depths'] = make_depths_deck
    STRATEGIES['depths'] = _strategy_depths
    try:
        from sim import run_any_bo3
        r = run_any_bo3('depths', 'dimir', 10)
        results.append(f"✓ Depths vs Dimir (10 matches): {r['match_wr']*100:.0f}%")
    except Exception as e:
        results.append(f"✗ Bo3 failed: {e}")

    return results


if __name__ == '__main__':
    print("Running Dark Depths tests...")
    for r in test_depths():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_depths(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_combo = ('depths' in tags and 'stage' in tags)
    has_tutor = any(t in tags for t in ('crop', 'scrying', 'reclaimer', 'gsz', 'once'))
    has_piece = 'depths' in tags or 'stage' in tags
    if len(hand) <= 5: return lc >= 1 and (has_piece or has_tutor)
    return lc >= 1 and (has_combo or (has_piece and has_tutor) or has_tutor)


DECK_META = {
    'key':        'depths',
    'name':       'Dark Depths',
    'make_deck':  make_depths_deck,
    'strategy':   _strategy_depths,
    'keep':       _keep_depths,
    'categories': {'combo', 'land_combo'},
    'interaction': {'speed': 2, 'resilience': 1, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': True, 'creature_based': False, 'bug_answers': 6},
    'meta_share': 0.02,
}
