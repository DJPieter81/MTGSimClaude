"""
Wan Shi Tong Control — UW Chalice Control for Legacy.
Adapted from Modern UW Control shell with full Legacy conversion.
Key: Chalice on 1 + wraths + counters + Wan Shi Tong as card advantage engine.
No Brainstorm/Ponder (anti-synergy with own Chalice on 1).
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import (creature, instant, sorcery, artifact, planeswalker,
                   fetch_land, dual_land, basic_land, utility_land)


def make_wst_deck():
    d = []
    # Creatures (10)
    d += [creature('Wan Shi Tong, Librarian', 4, {'W':1,'U':1,'generic':2}, {'W','U'}, 3, 5,
                   tag='wst', engine=True, flying=True)] * 4
    d += [creature('Sanctifier en-Vec', 2, {'W':1,'generic':1}, {'W'}, 2, 2,
                   tag='sanctifier')] * 2
    d += [creature('Snapcaster Mage', 2, {'U':1,'generic':1}, {'U'}, 2, 1,
                   tag='snap', flash=True)] * 2
    # Lock piece (4)
    d += [artifact('Chalice of the Void', 0, {}, tag='chalice', lock_piece=True,
                   is_combo_piece=True)] * 4
    # Removal (8)
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp',
                  is_removal=True)] * 4
    d += [instant('March of Otherworldly Light', 1, {'W':1}, {'W'}, tag='march',
                  is_removal=True)] * 4
    # Wraths (5)
    d += [sorcery('Wrath of the Skies', 2, {'W':1,'generic':1}, {'W'}, tag='wrath',
                  is_removal=True, is_mass_removal=True)] * 3
    d += [sorcery('Supreme Verdict', 4, {'W':2,'U':1,'generic':1}, {'W','U'}, tag='verdict',
                  is_removal=True, is_mass_removal=True)] * 2
    # Counters (10)
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow',
                  free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                  free_cast_if_blue=True)] * 1
    d += [instant('Counterspell', 2, {'U':2}, {'U'}, tag='counter')] * 2
    d += [instant("Dovin's Veto", 2, {'W':1,'U':1}, {'W','U'}, tag='veto')] * 2
    # Planeswalker (3)
    d += [planeswalker('Teferi, Time Raveler', 3, {'W':1,'U':1,'generic':1}, {'W','U'},
                       tag='teferi', engine=True)] * 3
    # Lands (23)
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 4
    d += [fetch_land('Marsh Flats', ['Swamp','Plains'])] * 4
    d += [dual_land('Tundra', ['U','W'], ['Island','Plains'])] * 3
    d += [basic_land('Island', 'U', 'Island')] * 3
    d += [basic_land('Plains', 'W', 'Plains')] * 3
    d += [dual_land('Plateau', ['R','W'], ['Mountain','Plains'])] * 1
    d += [utility_land('Karakas', ['W'], 'karakas')] * 1
    d += [utility_land('Wasteland', ['C'], 'wl')] * 1
    d += [utility_land('Meticulous Archive', ['W','U'], 'archive')] * 1
    d += [utility_land('Ancient Tomb', ['C','C'], 'tomb', mana_ritual=True)] * 1
    d += [utility_land('Mystic Sanctuary', ['U'], 'sanctuary')] * 1
    assert len(d) == 60, f"WST deck: {len(d)}"
    return d


def _strategy_wst(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Wan Shi Tong Control — UW Chalice Control.
    Priority: Chalice on 1 → removal → wraths → Teferi → WST → counters → combat.
    """
    from engine import (opp_can_cast, _try_counter_any, combat_declare,
                        update_goyf, _resolve_lock, MTGRules)

    # ── 1. Chalice of the Void on 1 — T1 priority ──
    ch = player.find_tag('chalice')
    if ch and gs.chalice_x is None and total_mana >= 2:
        player.remove_from_hand(ch)
        if not _try_counter_any(player, opponent, gs, ch, log_entries):
            player.put_artifact_in_play(ch)
            total_mana -= 2
            _resolve_lock(gs, ch, log_fn)
        else:
            player.add_to_grave(ch)
    # Also deploy Chalice on 0 if we have a second copy and already have Chalice on 1
    ch2 = player.find_tag('chalice')
    if ch2 and gs.chalice_x == 1 and total_mana >= 0:
        # Don't deploy second Chalice — it would overwrite chalice_x
        pass

    # ── 2. Swords to Plowshares — remove biggest threat ──
    stp = player.find_tag('stp')
    if stp and opponent.creatures and total_mana >= 1:
        target = max(opponent.creatures, key=lambda c: c.power + c.toughness)
        if target.power >= 2:
            player.remove_from_hand(stp); player.add_to_grave(stp)
            total_mana -= 1
            life_gain = MTGRules.stp_life_gain(target)
            opponent.remove_creature(target, to_exile=True)
            opponent.life += life_gain
            log_fn(f"Swords to Plowshares → exiles {target.card.name}")
            update_goyf(gs)

    # March of Otherworldly Light — exile removal
    march = player.find_tag('march')
    if march and opponent.creatures and total_mana >= 2:
        target = max(opponent.creatures, key=lambda c: c.power + c.toughness)
        if target.power >= 2:
            player.remove_from_hand(march); player.add_to_grave(march)
            total_mana -= 2
            opponent.remove_creature(target, to_exile=True)
            log_fn(f"March of Otherworldly Light → exiles {target.card.name}")
            update_goyf(gs)

    # ── 3. Wraths — clear board when opponent has 2+ creatures ──
    opp_threat = sum(c.power for c in opponent.creatures)
    wst_on_board = any(c.card.tag == 'wst' for c in player.creatures)

    if len(opponent.creatures) >= 2 and (not wst_on_board or opp_threat >= player.life):
        wrath = player.find_tag('verdict') or player.find_tag('wrath')
        if wrath and total_mana >= wrath.cmc:
            player.remove_from_hand(wrath); player.add_to_grave(wrath)
            total_mana -= wrath.cmc
            for c in list(opponent.creatures):
                opponent.add_to_grave(c.card); opponent.revolt_this_turn = True
            opponent.creatures.clear()
            for c in list(player.creatures):
                player.add_to_grave(c.card)
            player.creatures.clear()
            log_fn(f"★ {wrath.name} — all creatures destroyed", True)
            update_goyf(gs)

    # ── 4. Teferi, Time Raveler ──
    teferi = player.find_tag('teferi')
    teferi_on_board = any(p.card.tag == 'teferi' for p in player.artifacts)
    if teferi and not teferi_on_board and total_mana >= 3:
        player.remove_from_hand(teferi)
        if not _try_counter_any(player, opponent, gs, teferi, log_entries):
            player.put_artifact_in_play(teferi)
            total_mana -= 3
            # Teferi -3: bounce a permanent
            if opponent.creatures:
                tgt = max(opponent.creatures, key=lambda c: c.power)
                opponent.remove_creature(tgt)
                opponent.hand.append(tgt.card)
                log_fn(f"Teferi, Time Raveler — bounces {tgt.card.name}, draw 1", True)
            else:
                log_fn("Teferi, Time Raveler — opponent can't cast at instant speed", True)
            player.draw(1)
        else:
            player.add_to_grave(teferi)

    # ── 5. Wan Shi Tong — deploy the engine ──
    wst = player.find_tag('wst')
    if wst and not wst_on_board and total_mana >= 4:
        player.remove_from_hand(wst)
        if not _try_counter_any(player, opponent, gs, wst, log_entries):
            player.put_creature_in_play(wst)
            total_mana -= 4
            log_fn("★ Wan Shi Tong, Librarian (3/5 flying) — draws on each opponent draw", True)
        else:
            player.add_to_grave(wst)

    # ── 6. Sanctifier en-Vec ──
    sanc = player.find_tag('sanctifier')
    if sanc and total_mana >= 2:
        player.remove_from_hand(sanc)
        if not _try_counter_any(player, opponent, gs, sanc, log_entries):
            player.put_creature_in_play(sanc)
            total_mana -= 2
            log_fn("Sanctifier en-Vec (2/2, pro black/red)")
        else:
            player.add_to_grave(sanc)

    # ── 7. Snapcaster Mage — flashback value ──
    snap = player.find_tag('snap')
    if snap and total_mana >= 2:
        fb_target = next((c for c in player.graveyard
                          if c.is_removal and not c.is_mass_removal and opponent.creatures), None)
        if fb_target:
            player.remove_from_hand(snap)
            if not _try_counter_any(player, opponent, gs, snap, log_entries):
                player.put_creature_in_play(snap)
                total_mana -= 2
                # Flashback removal
                if opponent.creatures:
                    tgt = max(opponent.creatures, key=lambda c: c.power)
                    if tgt.power >= 2:
                        lg = MTGRules.stp_life_gain(tgt)
                        opponent.remove_creature(tgt, to_exile=True)
                        opponent.life += lg
                        player.graveyard.remove(fb_target)
                        log_fn(f"Snapcaster Mage — flashback {fb_target.name} → exiles {tgt.card.name}")
                        update_goyf(gs)
            else:
                player.add_to_grave(snap)

    # ── 8. Combat — attack with non-summoning-sick creatures ──
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


def _keep_wst(hand, matchup=''):
    lands = sum(1 for c in hand if c.is_land())
    counters = sum(1 for c in hand if c.tag in ('fow', 'fon', 'counter', 'veto'))
    removal = sum(1 for c in hand if c.is_removal)
    chalice = sum(1 for c in hand if c.tag == 'chalice')
    action = counters + removal + chalice
    return 2 <= lands <= 4 and action >= 1


DECK_META = {
    'key':        'wan_shi_tong',
    'name':       'Wan Shi Tong Control',
    'make_deck':  make_wst_deck,
    'strategy':   _strategy_wst,
    'keep':       _keep_wst,
    'categories': {'control', 'prison'},
    'meta_share': 0.02,
}
