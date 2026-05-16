"""
Dimir Flash (Wan Shi Tong) — deck module with full strategy.
Deck constructor in cards.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_dimir_flash_deck


# ─── Strategy ───────────────────────────────────────────────────────────────

def _strategy_dimir_flash(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Dimir Flash strategy — tempo deck with Wan Shi Tong, Bowmasters, Murktide.
    Based on engine._strategy_dimir_flash with cantrip fix and correct creature
    deployment order. Priority: cantrips → WST → other threats → Bowmasters →
    removal → Wasteland → combat.
    """
    from engine import (opp_can_cast, _try_counter_any, bowmasters_triggers,
                        update_goyf, combat_declare, cast_spell, resolve_cantrip)
    from rules import MTGRules
    from decision import DisruptionDecision

    budget = [total_mana]

    # ── Cantrips ──
    can = next((c for c in player.hand
                if c.is_cantrip and opp_can_cast(c, budget[0], gs, caster=player)), None)
    if can:
        cast_spell(player, opponent, gs, can, budget, log_fn, log_entries,
                   on_resolve=lambda c: (player.add_to_grave(c),
                                         resolve_cantrip(player, c, gs, log_fn, log_entries)))

    # ── Wan Shi Tong ──
    wst_card = player.find_tag('wst')
    wst_on_board = next((p for p in player.creatures if p.card.tag == 'wst'), None)
    if wst_card and not wst_on_board and opp_can_cast(wst_card, budget[0], gs, caster=player):
        x = max(0, min(budget[0] - 2, 4))
        has_board = len(player.creatures) > 0
        deploy = (x >= 1) or (x >= 0 and not has_board and budget[0] >= 2)
        if deploy:
            def _resolve_wst(c, _x=x):
                perm = player.put_creature_in_play(c)
                perm.power_mod = _x
                perm.toughness_mod = _x
                cards_drawn = _x // 2
                log_fn(f"Wan Shi Tong, Librarian (X={_x}) enters as {perm.power}/{perm.toughness}")
                if cards_drawn > 0:
                    drawn = player.draw(cards_drawn)
                    if drawn:
                        log_fn(f"  WST ETB: draws {cards_drawn} card(s)")
                    if gs.bowmasters_on_board:
                        ctr = []; bowmasters_triggers(cards_drawn, gs, ctr)
                        for m in ctr: log_entries.append(m)
            cast_spell(player, opponent, gs, wst_card, budget, log_fn, log_entries,
                       on_resolve=_resolve_wst, cost_override=2 + x)

    # ── Other threats ──
    thr = player.find_any(lambda c: c.is_creature() and c.cmc <= budget[0]
                          and c.tag not in ('bowm', 'wst', 'snuffout'))
    if thr:
        def _resolve_thr(c):
            player.put_creature_in_play(c)
            log_fn(f"{c.name} ({c.base_power}/{c.base_toughness})")
        cast_spell(player, opponent, gs, thr, budget, log_fn, log_entries,
                   on_resolve=_resolve_thr)

    # ── Bowmasters at flash speed ──
    bowm = player.find_tag('bowm')
    if bowm and opp_can_cast(bowm, budget[0], gs, caster=player):
        def _resolve_bowm(c):
            player.put_creature_in_play(c)
            log_fn("Orcish Bowmasters (flash)")
        cast_spell(player, opponent, gs, bowm, budget, log_fn, log_entries,
                   on_resolve=_resolve_bowm)

    # ── Removal ──
    push = player.find_tag('push')
    if push and opponent.creatures:
        target = next((c for c in opponent.creatures
                       if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)), None)
        if target:
            def _resolve_push(c, _t=target):
                player.add_to_grave(c)
                opponent.remove_creature(_t)
                rev = "[revolt CMC<=4]" if player.revolt_this_turn else "[CMC<=2]"
                log_fn(f"Fatal Push {rev} -> kills {_t.name}")
                update_goyf(gs)
            cast_spell(player, opponent, gs, push, budget, log_fn, log_entries,
                       on_resolve=_resolve_push)

    # ── Wasteland ──
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        wt = next((l for l in opponent.lands if MTGRules.wasteland_can_target(l)), None)
        if wt:
            player.lands.remove(wl); player.add_to_grave(wl.card)
            opponent.lands.remove(wt); opponent.add_to_grave(wt.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland [ACTIVATED-uncounterable] -> {wt.name}")
            gs.strat_log.log(DisruptionDecision(
                turn=gs.turn,
                deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                phase=None,
                reason=f'wasteland destroys {wt.card.tag or "nonbasic"}',
                candidates=('wasteland', 'pass'),
                kind='land_destroy',
                target_tag=wt.card.tag or 'nonbasic',
                instrument_tag='wasteland',
            ))
            update_goyf(gs)

    # ── Combat ──
    opp_has_blockers = len(opponent.creatures) > 0
    desperate = player.life < 8
    attackers_this_turn = []
    for c in player.creatures:
        if c.summoning_sick:
            continue
        if c.card.tag == 'bowm':
            if not opp_has_blockers or desperate:
                attackers_this_turn.append(c)
        elif c.card.tag == 'tamiyo':
            pass  # 0/3 blocks, doesn't attack
        else:
            attackers_this_turn.append(c)

    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_dimir_flash(hand, matchup=''):
    """Dimir Flash keep — counts removal (Fatal Push, Thoughtseize) as action.
    A Dimir tempo hand needs lands + interaction. Removal IS interaction.
    """
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands if c.tag in ('fow', 'fon', 'daze', 'fluster'))
    removal = sum(1 for c in nonlands if c.tag in ('push', 'ts'))
    action = threats + cantrips + counters + removal
    if lc < 1 or lc > 4:
        return False
    if action == 0:
        return False
    # Blue access check
    blue_access = any('U' in getattr(c, 'produces', set()) or getattr(c, 'is_fetch', False) for c in lands)
    if lc == 1:
        return blue_access and cantrips >= 1 and action >= 2
    if lc == 2:
        return blue_access and action >= 2
    # 3-4 lands: keep with any meaningful action
    return action >= 1


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'dimir_flash',
    'name':       'Dimir Flash (Wan Shi Tong)',
    'make_deck':  make_dimir_flash_deck,
    'strategy':   _strategy_dimir_flash,
    'keep':       _keep_dimir_flash,
    'categories': {'bowm_decks', 'mirror'},
    'interaction': {'speed': 4, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True},
    'meta_share': 0.01,
}
