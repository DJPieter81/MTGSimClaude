"""
UWx Control — deck module with improved strategy.
Deck constructor in cards.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import make_uwx_deck


# ─── Strategy ───────────────────────────────────────────────────────────────

def _strategy_uwx(player, opponent, gs, total_mana, log_fn, log_entries):
    """UWx Control strategy — improved for aggro/burn matchups.
    Priority: STP any creature (vs aggro) → Terminus → Mentor → lock pieces → cantrips → combat.
    Key fix: STP fires on ANY creature power >= 1 vs aggro/burn (not just >= 2).
    """
    from engine import (opp_can_cast, _try_counter_any, bowmasters_triggers,
                        update_goyf, combat_declare)
    from rules import MTGRules, Permanent, Card, CardType

    _MONK_TOKEN = Card(name='Monk Token', card_type=CardType.CREATURE, cmc=0,
                       mana_cost={}, colors=set(), base_power=1, base_toughness=1,
                       tag='monk_token', gy_type='creature')

    mana_ref = [total_mana]

    def can_cast(card):
        return opp_can_cast(card, mana_ref[0], gs, caster=player)

    def spend(card):
        mana_ref[0] -= card.cmc

    def mentor_trigger():
        if any(c.card.tag == 'mentor' for c in player.creatures):
            player.put_creature_in_play(_MONK_TOKEN)
            log_fn("  Mentor trigger -> 1/1 Monk token")

    # ── STP — exile opponent's creatures aggressively ──
    # Against aggro/burn, STP any creature (even power 1 like Swiftspear/Guide).
    # Against other matchups, STP power >= 2.
    p2_deck = getattr(gs, 'p2_deck', '') or getattr(gs, 'matchup', '')
    from config import MatchupCategory as _MC, CombatThresholds as CT
    opp_is_aggro = p2_deck in _MC.AGGRO or p2_deck == 'burn'
    stp_threshold = CT.STP_THRESHOLD_AGGRO if opp_is_aggro else CT.STP_THRESHOLD_FAIR
    _mom_protected = getattr(gs, '_mom_protected_tag', None)

    # Fire STP on multiple creatures if available (vs aggro, clear the board)
    stps_used = 0
    while stps_used < 2:
        stp = player.find_tag('stp')
        if not stp or not opponent.creatures or mana_ref[0] < 1:
            break
        valid = [c for c in opponent.creatures if c.card.tag != _mom_protected]
        target = max(valid, key=lambda c: c.power) if valid else None
        if not target or target.power < stp_threshold:
            break
        player.remove_from_hand(stp); player.add_to_grave(stp)
        life_gain = MTGRules.stp_life_gain(target)
        opponent.remove_creature(target, to_exile=True)
        opponent.life += life_gain
        spend(stp)
        stps_used += 1
        log_fn(f"Swords to Plowshares -> exiles {target.card.name}, opp gains {life_gain} life")
        update_goyf(gs)
        mentor_trigger()

    # ── Terminus — wrath when opp has 2+ creatures AND we don't have Mentor on board ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    opp_threat = sum(c.power for c in opponent.creatures)
    if len(opponent.creatures) >= 2 and (not mentor_on_board or opp_threat >= player.life):
        term = player.find_tag('terminus')
        if term and random.random() < 0.80:
            player.remove_from_hand(term); player.add_to_grave(term)
            for c in list(opponent.creatures):
                opponent.exile.append(c.card); opponent.revolt_this_turn = True
            opponent.creatures.clear()
            for c in list(player.creatures): player.library.append(c.card)
            player.creatures.clear()
            log_fn("Terminus (Miracle {W}) -- all creatures on bottom of library", True)
            update_goyf(gs)

    # ── Monastery Mentor — primary win condition ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    mentor = player.find_tag('mentor')
    if mentor and not mentor_on_board and can_cast(mentor):
        player.remove_from_hand(mentor)
        if not _try_counter_any(player, opponent, gs, mentor, log_entries):
            player.put_creature_in_play(mentor)
            spend(mentor)
            log_fn("Monastery Mentor (2/2 prowess -- tokens on noncreature spells)", True)
        else:
            player.add_to_grave(mentor)

    # ── Snapcaster Mage — flashback value ──
    snap = player.find_tag('snap')
    if snap and can_cast(snap):
        stp_fb = next((c for c in player.graveyard
                       if c.is_removal and not c.is_mass_removal and c.cmc == 1
                       and opponent.creatures and max(c2.power for c2 in opponent.creatures) >= stp_threshold), None)
        term_fb = next((c for c in player.graveyard if c.tag == 'terminus'), None) if len(opponent.creatures) >= 2 else None
        bs_fb = next((c for c in player.graveyard if c.is_cantrip), None)
        fb = stp_fb or term_fb or bs_fb
        if fb:
            player.remove_from_hand(snap)
            if not _try_counter_any(player, opponent, gs, snap, log_entries):
                player.put_creature_in_play(snap); spend(snap)
                log_fn(f"Snapcaster Mage (2/1) -- flashback {fb.name}")
                if fb == stp_fb and opponent.creatures:
                    t = max(opponent.creatures, key=lambda c: c.power)
                    lg = MTGRules.stp_life_gain(t)
                    opponent.remove_creature(t, to_exile=True); opponent.life += lg
                    player.graveyard.remove(fb); player.exile.append(fb)
                    log_fn(f"  Snapcaster flashback STP -> exiles {t.card.name}", True)
                    update_goyf(gs)
                elif fb == term_fb and opponent.creatures:
                    for c in list(opponent.creatures): opponent.exile.append(c.card); opponent.revolt_this_turn = True
                    opponent.creatures.clear()
                    for c in list(player.creatures): player.library.append(c.card)
                    player.creatures.clear()
                    player.graveyard.remove(fb); player.exile.append(fb)
                    log_fn("  Snapcaster flashback Terminus", True); update_goyf(gs)
                elif fb == bs_fb:
                    player.graveyard.remove(fb); player.exile.append(fb)
                    drawn = player.draw(MTGRules.brainstorm_draws())
                    log_fn(f"  Snapcaster flashback Brainstorm ({len(drawn)} draw)")
                    bowmasters_triggers(len(drawn), gs, log_entries, controller='o' if player is gs.p1 else 'b')
            else:
                player.add_to_grave(snap)

    # ── Back to Basics — only deploy vs decks with nonbasic lands ──
    # Skip vs burn/aggro (they mostly run basics) — save mana for threats/removal
    opp_nonbasics = sum(1 for l in opponent.lands if not l.card.is_basic)
    b2b = player.find_tag('b2b')
    if b2b and not gs.b2b_on_board and can_cast(b2b) and (opp_nonbasics >= 2 or not opp_is_aggro):
        player.remove_from_hand(b2b)
        if not _try_counter_any(player, opponent, gs, b2b, log_entries):
            player.put_enchantment_in_play(b2b); spend(b2b)
            gs.set_b2b(True)
            log_fn("Back to Basics -- nonbasic lands don't untap", True)
            mentor_trigger()
        else:
            player.add_to_grave(b2b)

    # ── Narset ──
    narset = player.find_tag('narset')
    narset_on_board = any(p.card.tag == 'narset' for p in player.planeswalkers)
    if narset and not narset_on_board and can_cast(narset):
        player.remove_from_hand(narset)
        if not _try_counter_any(player, opponent, gs, narset, log_entries):
            player.put_planeswalker_in_play(narset); spend(narset)
            log_fn("Narset, Parter of Veils -- opponent can only draw one card per turn", True)
            mentor_trigger()
        else:
            player.add_to_grave(narset)

    # ── Cantrips — cast up to 2 per turn ──
    for _ in range(2):
        if mana_ref[0] < 1: break
        can_c = next((c for c in player.hand if c.is_cantrip and can_cast(c)), None)
        if not can_c: break
        player.remove_from_hand(can_c); player.add_to_grave(can_c); spend(can_c)
        draws = MTGRules.brainstorm_draws() if can_c.tag == 'bs' else 1
        log_fn(f"{can_c.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        bowmasters_triggers(draws, gs, log_entries, controller='o' if player is gs.p1 else 'b')
        mentor_trigger()

    # ── Combat ──
    attackers = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag in ('tamiyo',): pass  # 0/3 blocks, doesn't attack
        else:
            attackers.append(c)
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_uwx(hand, matchup=''):
    """UWx Control keep — values removal and lock pieces as action, not just counters/threats.
    A hand with 3 lands + FoW + STP is a perfect control hand.
    """
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'fon', 'daze', 'fluster', 'counter'))
    removal = sum(1 for c in nonlands if c.tag in ('stp', 'terminus'))
    lock_pieces = sum(1 for c in nonlands if c.tag in ('b2b', 'narset'))
    action = threats + cantrips + counters + removal + lock_pieces
    if lc < 2 or lc > 4:
        return False
    if action == 0:
        return False
    if lc <= 3:
        return action >= 1  # control can keep on 1 interactive spell
    # 4 lands: need at least 2 action cards
    return action >= 2


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'uwx',
    'name':       'UWx Control',
    'make_deck':  make_uwx_deck,
    'strategy':   _strategy_uwx,
    'keep':       _keep_uwx,
    'categories': {'mirror', 'control'},
    'interaction': {'speed': 5, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.03,
}
