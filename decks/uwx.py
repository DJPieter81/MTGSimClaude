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
                        update_goyf, combat_declare, cast_spell)
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
        def _resolve_stp(c, _t=target):
            player.add_to_grave(c)
            if _t in opponent.creatures:
                lg = MTGRules.stp_life_gain(_t)
                opponent.remove_creature(_t, to_exile=True)
                opponent.life += lg
                log_fn(f"Swords to Plowshares -> exiles {_t.card.name}, opp gains {lg} life")
                update_goyf(gs)
                mentor_trigger()
        cast_spell(player, opponent, gs, stp, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_stp)
        stps_used += 1

    # ── Terminus — wrath when opp has 2+ creatures AND we don't have Mentor on board ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    opp_threat = sum(c.power for c in opponent.creatures)
    if len(opponent.creatures) >= 2 and (not mentor_on_board or opp_threat >= player.life):
        term = player.find_tag('terminus')
        if term:
            # Miracle cost {W} — cast at miracle cost (override to 1)
            def _resolve_term(c):
                player.add_to_grave(c)
                for cc in list(opponent.creatures):
                    opponent.exile.append(cc.card); opponent.revolt_this_turn = True
                opponent.creatures.clear()
                for cc in list(player.creatures): player.library.append(cc.card)
                player.creatures.clear()
                log_fn("Terminus (Miracle {W}) -- all creatures on bottom of library", True)
                update_goyf(gs)
            cast_spell(player, opponent, gs, term, mana_ref, log_fn, log_entries,
                       on_resolve=_resolve_term, cost_override=1)

    # ── Monastery Mentor — primary win condition ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    mentor = player.find_tag('mentor')
    if mentor and not mentor_on_board and can_cast(mentor):
        def _resolve_mentor(c):
            player.put_creature_in_play(c)
            log_fn("Monastery Mentor (2/2 prowess -- tokens on noncreature spells)", True)
        cast_spell(player, opponent, gs, mentor, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_mentor)

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
            def _resolve_snap(c, _fb=fb, _stp_fb=stp_fb, _term_fb=term_fb, _bs_fb=bs_fb):
                player.put_creature_in_play(c)
                log_fn(f"Snapcaster Mage (2/1) -- flashback {_fb.name}")
                if _fb is _stp_fb and opponent.creatures:
                    t = max(opponent.creatures, key=lambda cc: cc.power)
                    lg = MTGRules.stp_life_gain(t)
                    opponent.remove_creature(t, to_exile=True); opponent.life += lg
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    log_fn(f"  Snapcaster flashback STP -> exiles {t.card.name}", True)
                    update_goyf(gs)
                elif _fb is _term_fb and opponent.creatures:
                    for cc in list(opponent.creatures):
                        opponent.exile.append(cc.card); opponent.revolt_this_turn = True
                    opponent.creatures.clear()
                    for cc in list(player.creatures): player.library.append(cc.card)
                    player.creatures.clear()
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    log_fn("  Snapcaster flashback Terminus", True); update_goyf(gs)
                elif _fb is _bs_fb:
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    drawn = player.draw(MTGRules.brainstorm_draws())
                    log_fn(f"  Snapcaster flashback Brainstorm ({len(drawn)} draw)")
                    bowmasters_triggers(len(drawn), gs, log_entries, controller='o' if player is gs.p1 else 'b')
            cast_spell(player, opponent, gs, snap, mana_ref, log_fn, log_entries,
                       on_resolve=_resolve_snap)

    # ── Back to Basics — only deploy vs decks with nonbasic lands ──
    opp_nonbasics = sum(1 for l in opponent.lands if not l.card.is_basic)
    b2b = player.find_tag('b2b')
    if b2b and not gs.b2b_on_board and can_cast(b2b) and (opp_nonbasics >= 2 or not opp_is_aggro):
        def _resolve_b2b(c):
            player.put_enchantment_in_play(c)
            gs.set_b2b(True)
            log_fn("Back to Basics -- nonbasic lands don't untap", True)
            mentor_trigger()
        cast_spell(player, opponent, gs, b2b, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_b2b)

    # ── Narset ──
    narset = player.find_tag('narset')
    narset_on_board = any(p.card.tag == 'narset' for p in player.planeswalkers)
    if narset and not narset_on_board and can_cast(narset):
        def _resolve_narset(c):
            player.put_planeswalker_in_play(c)
            log_fn("Narset, Parter of Veils -- opponent can only draw one card per turn", True)
            mentor_trigger()
        cast_spell(player, opponent, gs, narset, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_narset)

    # ── Cantrips — cast up to 2 per turn ──
    for _ in range(2):
        if mana_ref[0] < 1: break
        can_c = next((c for c in player.hand if c.is_cantrip and can_cast(c)), None)
        if not can_c: break
        def _resolve_cant(c):
            player.add_to_grave(c)
            draws = MTGRules.brainstorm_draws() if c.tag == 'bs' else 1
            log_fn(f"{c.name} ({draws} draw{'s' if draws > 1 else ''})")
            player.draw(draws)
            bowmasters_triggers(draws, gs, log_entries, controller='o' if player is gs.p1 else 'b')
            mentor_trigger()
        cast_spell(player, opponent, gs, can_c, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_cant)

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
