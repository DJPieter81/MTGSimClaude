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
    Priority: removal → threats (WST, Murktide, Bowmasters, Tamiyo) → cantrips → combat.
    Murktide uses delve: effective cost = max(2, 7 - graveyard_count).
    """
    from config import CombatThresholds as CT
from engine import (opp_can_cast, _try_counter_any, bowmasters_triggers,
                        update_goyf, combat_declare)
    from rules import MTGRules

    rem = total_mana  # remaining mana — deduct after each cast

    # ── Thoughtseize: strip opponent's best card early ──
    ts = player.find_tag('ts')
    if ts and rem >= 1 and player.life > 4:
        opp_nonland = [c for c in opponent.hand if not c.is_land()]
        if opp_nonland:
            player.remove_from_hand(ts)
            if not _try_counter_any(player, opponent, gs, ts, log_entries):
                player.add_to_grave(ts)
                player.life -= 2
                rem -= 1
                def _ts_priority(c):
                    score = 0
                    if c.win_condition: score += 10
                    if c.is_combo_piece: score += 8
                    if c.tag in ('fow', 'fon', 'daze', 'fluster'): score += 6
                    if c.is_creature(): score += 3 + c.base_power
                    score += c.cmc
                    return score
                best = max(opp_nonland, key=_ts_priority)
                opponent.remove_from_hand(best)
                opponent.add_to_grave(best)
                log_fn(f"Thoughtseize -> strips {best.name} (-2 life, {player.life})")
            else:
                player.add_to_grave(ts)

    # ── Removal: Fatal Push — kill opponent's best creature ──
    push = player.find_tag('push')
    if push and opponent.creatures and rem >= 1:
        target = next((c for c in sorted(opponent.creatures, key=lambda c: -c.power)
                       if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)), None)
        if target:
            player.remove_from_hand(push); player.add_to_grave(push)
            rem -= 1
            opponent.remove_creature(target)
            rev = "[revolt CMC<=4]" if player.revolt_this_turn else "[CMC<=2]"
            log_fn(f"Fatal Push {rev} -> kills {target.name}")
            update_goyf(gs)

    # ── Wan Shi Tong — cast with maximum X affordable (threat before cantrips) ──
    wst_card = player.find_tag('wst')
    wst_on_board = next((p for p in player.creatures if p.card.tag == 'wst'), None)
    if wst_card and not wst_on_board and rem >= 2:
        x = max(0, min(rem - 2, 4))  # pay UU + X generic
        has_board = len(player.creatures) > 0
        deploy = (x >= 1) or (not has_board)
        if deploy:
            player.remove_from_hand(wst_card)
            if not _try_counter_any(player, opponent, gs, wst_card, log_entries):
                perm = player.put_creature_in_play(wst_card)
                perm.power_mod = x
                perm.toughness_mod = x
                actual_cost = 2 + x
                rem -= actual_cost
                cards_drawn = x // 2
                log_fn(f"Wan Shi Tong, Librarian (X={x}) enters as {perm.power}/{perm.toughness}")
                if cards_drawn > 0:
                    drawn = player.draw(cards_drawn)
                    if drawn:
                        log_fn(f"  WST ETB: draws {cards_drawn} card(s)")
                    if gs.bowmasters_on_board:
                        ctr = []; bowmasters_triggers(cards_drawn, gs, ctr)
                        for m in ctr: log_entries.append(m)
            else:
                player.add_to_grave(wst_card)

    # ── Murktide Regent via delve (threat before cantrips) ──
    murk = player.find_tag('murk')
    if murk and not any(c.card.tag == 'murk' for c in player.creatures):
        gy_count = len([c for c in player.graveyard
                        if not c.is_land()])  # only nonland cards count for delve
        effective_cost = max(2, murk.cmc - gy_count)  # at least UU (2 mana)
        if rem >= effective_cost:
            player.remove_from_hand(murk)
            if not _try_counter_any(player, opponent, gs, murk, log_entries):
                # Exile cards from graveyard for delve
                exiled = 0
                to_exile = min(gy_count, murk.cmc - 2)  # exile enough to reduce to UU
                for _ in range(to_exile):
                    nonland_gy = [c for c in player.graveyard if not c.is_land()]
                    if nonland_gy:
                        exile_card = nonland_gy[0]
                        player.graveyard.remove(exile_card)
                        player.exile.append(exile_card)
                        exiled += 1
                perm = player.put_creature_in_play(murk)
                # Murktide enters with +1/+1 counters equal to instants/sorceries exiled
                perm.power_mod = exiled - murk.base_power
                perm.toughness_mod = exiled - murk.base_toughness
                rem -= effective_cost
                log_fn(f"Murktide via delve ({exiled} exiled) -> {perm.power}/{perm.toughness}")
            else:
                player.add_to_grave(murk)

    # ── Bowmasters at flash speed (threat before cantrips) ──
    bowm = player.find_tag('bowm')
    if bowm and rem >= 2:
        player.remove_from_hand(bowm)
        if not _try_counter_any(player, opponent, gs, bowm, log_entries):
            player.put_creature_in_play(bowm)
            rem -= 2
            log_fn("Orcish Bowmasters (flash)")
        else:
            player.add_to_grave(bowm)

    # ── Other threats: Tamiyo ──
    for tag in ('tamiyo',):
        thr = player.find_tag(tag)
        if thr and rem >= thr.cmc:
            player.remove_from_hand(thr)
            if not _try_counter_any(player, opponent, gs, thr, log_entries):
                player.put_creature_in_play(thr)
                rem -= thr.cmc
                log_fn(f"{thr.name} ({thr.base_power}/{thr.base_toughness})")
            else:
                player.add_to_grave(thr)

    # ── Cantrips: dig for threats/answers (after deploying threats) ──
    for _ in range(2):  # cast up to 2 cantrips with remaining mana
        can = next((c for c in player.hand if c.is_cantrip and rem >= 1), None)
        if not can:
            break
        player.remove_from_hand(can); player.add_to_grave(can)
        rem -= 1
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)

    # ── Wasteland: destroy opponent's best nonbasic ──
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        wt = next((l for l in opponent.lands if MTGRules.wasteland_can_target(l)), None)
        if wt:
            player.lands.remove(wl); player.add_to_grave(wl.card)
            opponent.lands.remove(wt); opponent.add_to_grave(wt.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland [ACTIVATED-uncounterable] -> {wt.name}")
            update_goyf(gs)

    # ── WST search trigger: check if opponent fetched this turn ──
    # Wan Shi Tong oracle: "Whenever an opponent searches their library,
    # put a +1/+1 counter on WST and draw a card."
    # opponent.revolt_this_turn is set when they crack a fetch (same turn cycle).
    wst_perm = next((p for p in player.creatures if p.card.tag == 'wst'), None)
    if wst_perm and opponent.revolt_this_turn:
        wst_perm.power_mod += 1
        wst_perm.toughness_mod += 1
        drawn = player.draw(1)
        if drawn:
            log_fn(f"WST trigger: opp searched → Wan Shi Tong grows ({wst_perm.power}/{wst_perm.toughness}), draws {drawn[0].name}")
        else:
            log_fn(f"WST trigger: Wan Shi Tong grows ({wst_perm.power}/{wst_perm.toughness})")

    # ── Combat: attack with non-summoning-sick creatures ──
    opp_has_blockers = len(opponent.creatures) > 0
    desperate = player.life < CT.DESPERATE_LIFE
    attackers_this_turn = []
    for c in player.creatures:
        if c.summoning_sick:
            continue
        if c.card.tag == 'bowm':
            # Hold Bowmasters back unless no blockers or desperate
            if not opp_has_blockers or desperate:
                attackers_this_turn.append(c)
        elif c.card.tag == 'tamiyo' and c.power <= 0:
            pass  # 0/3 blocks, doesn't attack productively
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
