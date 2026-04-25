"""
UR Delver — Legacy tempo deck.

Tempo variant of UR Aggro: more Delvers (4x), more Dazes (4x), more cantrips,
fewer burn spells.  Deploy cheap evasive threats T1, protect with free counters
(Daze, FoW), cantrip to flip Delver, Bolt to close.

Key differences from UR Aggro:
- 4 Delver of Secrets (vs 0 in aggro) — the namesake threat
- 4 Daze (vs 2) — tempo-positive on T1–3
- 2 Spell Pierce — catches early noncreature spells
- 2 Preordain — more cantrips to flip Delver
- No Ragavan, no Price of Progress
- 18 lands (vs 20) — lower curve, Daze returns Islands
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import creature, instant, sorcery, artifact, fetch_land, dual_land, basic_land
from rules import Card, CardType
from typing import List


# ─── Deck construction ────────────────────────────────────────────────────────

def make_ur_delver_deck() -> List[Card]:
    d: List[Card] = []

    # ── Creatures (14) ───────────────────────────────────────────────────────
    # Delver of Secrets: enters as 1/1 (unflipped). Strategy checks for flip
    # each upkeep (~60% with this deck's instant/sorcery density).
    d += [creature('Delver of Secrets', 1, {'U': 1}, {'U'}, 1, 1,
                   tag='delver', flying=False)] * 4
    # Dragon's Rage Channeler: 1/1 base, delirium → 3/3
    # Strategy checks delirium (4+ card types in GY) each turn
    d += [creature("Dragon's Rage Channeler", 1, {'R': 1}, {'R'}, 1, 1,
                   tag='drc')] * 4
    # Murktide Regent: delve flyer, effectively 2 mana with full GY
    d += [creature('Murktide Regent', 7, {'U': 1, 'generic': 6}, {'U'}, 5, 5,
                   tag='murk', delve=True, flying=True)] * 4
    # Brazen Borrower: flash flyer, bounces a permanent (Petty Theft)
    d += [creature('Brazen Borrower', 3, {'U': 1, 'generic': 2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 2

    # ── Burn / Removal (6) ───────────────────────────────────────────────────
    d += [instant('Lightning Bolt', 1, {'R': 1}, {'R'}, tag='bolt')] * 4
    d += [instant('Unholy Heat', 1, {'R': 1}, {'R'}, tag='heat')] * 2

    # ── Cantrips (10) ────────────────────────────────────────────────────────
    d += [instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                  is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                  is_cantrip=True)] * 4
    d += [sorcery('Preordain', 1, {'U': 1}, {'U'}, tag='pre',
                  is_cantrip=True)] * 2

    # ── Counterspells (10) ───────────────────────────────────────────────────
    d += [instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'},
                  tag='daze')] * 4
    d += [instant('Spell Pierce', 1, {'U': 1}, {'U'},
                  tag='pierce')] * 2

    # ── Card Advantage (2) ───────────────────────────────────────────────────
    d += [sorcery('Expressive Iteration', 2, {'U': 1, 'R': 1}, {'U', 'R'},
                  tag='ei')] * 2

    # ── Lands (18) ───────────────────────────────────────────────────────────
    d += [fetch_land('Scalding Tarn', ['Island', 'Mountain'])] * 4
    d += [fetch_land('Polluted Delta', ['Island', 'Swamp'])] * 2
    d += [fetch_land('Misty Rainforest', ['Island', 'Forest'])] * 2
    d += [dual_land('Volcanic Island', ['U', 'R'], ['Island', 'Mountain'])] * 4
    d += [dual_land('Steam Vents', ['U', 'R'], ['Island', 'Mountain'],
                    tag='dual')] * 2
    d += [basic_land('Island', 'U', 'Island')] * 2
    d += [basic_land('Mountain', 'R', 'Mountain')] * 2

    assert len(d) == 60, f"UR Delver deck has {len(d)} cards (expected 60)"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_ur_delver(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    UR Delver tempo strategy.

    Priority:
    0. Upkeep: Delver flip check (~60% per turn — reveal top card)
    1. Deploy cheap threats (Delver T1, DRC T1, Murktide T2+ with delve)
    2. Cantrip to flip Delver and find action
    3. Lightning Bolt / Unholy Heat — removal first, face burn only late
    4. Expressive Iteration for card advantage mid-game
    5. Combat — attack with all non-summoning-sick creatures
    6. Daze / FoW held reactively (via _try_counter_any)
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare
    from engine import update_goyf, opp_can_cast
    from state_encoder import record as _trace_record

    mana = total_mana
    turn = gs.turn

    # ── 0. Delver flip check (upkeep) ────────────────────────────────────────
    # In real Legacy, Delver reveals the top card of the library each upkeep.
    # With ~28 instants/sorceries in 42 non-land cards, flip rate is ~60%.
    # Unflipped Delver is a 1/1 (base stats); flipped is 3/2 flying.
    DELVER_FLIP_RATE = 0.60
    for c in player.creatures:
        if c.card.tag == 'delver' and c.power == 1:
            # Unflipped Delver — attempt flip
            if random.random() < DELVER_FLIP_RATE:
                c.power_mod += 2   # 1 + 2 = 3 power
                c.toughness_mod += 1  # 1 + 1 = 2 toughness
                c.card.flying = True  # Insectile Aberration has flying
                log_fn("Delver of Secrets flips → Insectile Aberration (3/2 flying)")
            else:
                log_fn("Delver upkeep — no flip (stays 1/1)")

    # ── 0b. DRC delirium check ──────────────────────────────────────────────
    # DRC is 1/1 until delirium (4+ card types in graveyard), then 3/3.
    # DRC's own surveil trigger (each time you cast a spell) accelerates
    # delirium. With fetchlands + cantrips, delirium is typical by T3.
    # Model: count distinct gy_types; DRC surveil effectively adds ~1 type
    # (representing cards DRC puts into the GY via surveil over the game).
    gy_types_drc = set()
    for c in player.graveyard:
        gt = getattr(c, 'gy_type', '')
        if gt:
            gy_types_drc.add(gt)
    # DRC surveil bonus: each cast spell would have surveiled, contributing
    # card types. Approximate by counting GY size as a proxy for surveil depth.
    gy_count = len(player.graveyard)
    has_delirium = len(gy_types_drc) >= 4 or (len(gy_types_drc) >= 3 and gy_count >= 4)
    for c in player.creatures:
        if c.card.tag == 'drc':
            if has_delirium and c.power == 1:
                # Gain delirium — becomes 3/3
                c.power_mod += 2   # 1 + 2 = 3
                c.toughness_mod += 2  # 1 + 2 = 3
                log_fn("DRC gains delirium → 3/3")

    # ── 1. Deploy threats ────────────────────────────────────────────────────

    from engine import cast_spell
    budget = [mana]

    # Delver of Secrets — best T1 play
    deployed_threat = False
    for tag in ('delver', 'drc'):
        threat = player.find_tag(tag)
        if threat and budget[0] >= 1:
            def _resolve_threat(c, _tag=tag):
                player.put_creature_in_play(c)
                suffix = " (1/1 — flips next upkeep)" if _tag == 'delver' else ""
                log_fn(f"{c.name}{suffix}")
            cast_spell(player, opponent, gs, threat, budget, log_fn, log_entries,
                       on_resolve=_resolve_threat, cost_override=1)
            deployed_threat = True
            break

    # Murktide Regent — delve
    if not deployed_threat:
        murk = player.find_tag('murk')
        if murk:
            gy_count = len(player.graveyard)
            delve_amount = min(gy_count, 6)
            effective_cost = max(2, 7 - delve_amount)
            if budget[0] >= effective_cost:
                # Exile cards from GY for delve BEFORE casting (part of the cost)
                exiled = 0
                while exiled < delve_amount and player.graveyard:
                    card = player.graveyard.pop(0)
                    if hasattr(player, 'exile'): player.exile.append(card)
                    exiled += 1
                def _resolve_murk(c, _e=exiled, _cost=effective_cost):
                    player.put_creature_in_play(c)
                    log_fn(f"Murktide Regent (delve {_e}, paid {_cost})")
                cast_spell(player, opponent, gs, murk, budget, log_fn, log_entries,
                           on_resolve=_resolve_murk, cost_override=effective_cost)
                deployed_threat = True

    # Brazen Borrower
    if not deployed_threat:
        borrow = player.find_tag('borrow')
        if borrow and budget[0] >= 3:
            def _resolve_borrow(c):
                player.put_creature_in_play(c)
                log_fn("Brazen Borrower (3/1 flash flyer)")
            cast_spell(player, opponent, gs, borrow, budget, log_fn, log_entries,
                       on_resolve=_resolve_borrow, cost_override=3)

    # ── 2. Cantrips ──
    _cant_cands = [t for t in ('bs', 'ponder', 'pre')
                   if player.find_tag(t) is not None and budget[0] >= 1]
    for cantrip_tag in ('bs', 'ponder', 'pre'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and budget[0] >= 1:
            # ── TRACE: cantrip pick (≥ 2 candidates only) ───────────────
            if len(_cant_cands) >= 2:
                _trace_record('ur_cantrip_pick', cantrip_tag, gs, player, opponent,
                              candidates=_cant_cands)
            # ── PHASE 3 OPT-IN: NN scorer can re-rank cantrip choices ───
            if (getattr(gs, 'use_neural_scorer', False)
                    and len(_cant_cands) >= 2):
                try:
                    from neural_scorer import score as _nn_score
                    # Score the current state. Lever 2 (1-ply lookahead) will
                    # do per-candidate scoring; for now this just observes.
                    _trace_record('ur_cantrip_score',
                                  cantrip_tag, gs, player, opponent,
                                  candidates=_cant_cands,
                                  scorer_p_win=_nn_score(gs, player, opponent,
                                                         deck='ur_delver'))
                except Exception:
                    pass
            def _resolve_cant(c):
                player.add_to_grave(c)
                player.draw(1)
                log_fn(f"{c.name} — cantrip")
                bowmasters_triggers(1, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
            cast_spell(player, opponent, gs, cantrip, budget, log_fn, log_entries,
                       on_resolve=_resolve_cant, cost_override=1)
            break

    # ── 3. Expressive Iteration ──
    ei = player.find_tag('ei')
    if ei and budget[0] >= 2:
        def _resolve_ei(c):
            player.add_to_grave(c)
            player.draw(1)
            log_fn("Expressive Iteration — draw + exile selection")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
        cast_spell(player, opponent, gs, ei, budget, log_fn, log_entries,
                   on_resolve=_resolve_ei, cost_override=2)
    mana = budget[0]

    # ── 4. Lightning Bolt — removal-first, face burn only when closing ──────

    bolt = player.find_tag('bolt')
    if bolt and mana >= 1:
        # Priority targets for removal — only worth Bolting meaningful threats
        def bolt_priority(c):
            if c.card.tag == 'tamiyo':  return 0   # must kill before flip
            if c.card.tag == 'bowm':    return 1   # shuts down cantrips
            if c.toughness <= 3 and c.power >= 2:  return 2   # real threat in Bolt range
            if c.toughness <= 3 and c.power >= 1 and len(opponent.creatures) >= 3:
                return 3  # clear smaller threats only when board is getting wide
            return 99

        candidates = [c for c in opponent.creatures if bolt_priority(c) < 99]
        target = min(candidates, key=bolt_priority) if candidates else None

        # Go face only when closing the game:
        # - Need a clock on board (creatures attacking)
        # - Opponent must be in burn range (life <= 6), OR
        # - Opponent is at <= 9 life AND it's turn 5+ (late game, clock is ticking)
        has_clock = any(not c.summoning_sick for c in player.creatures)
        go_face = (target is None
                   and has_clock
                   and (opponent.life <= 6
                        or (opponent.life <= 9 and turn >= 5)))

        if target or go_face:
            # ── TRACE: Bolt mode decision (creature vs face) ────────────
            _bolt_mode = 'face' if (go_face and target is None) else 'creature'
            if target is not None or go_face:
                _trace_record('ur_bolt_mode', _bolt_mode, gs, player, opponent,
                              target_name=target.card.name if target else None,
                              opp_life=opponent.life,
                              creatures_on_board=len(opponent.creatures),
                              has_clock=has_clock)
            # ── LEVER 2: 1-ply action-space lookahead via NN scorer ────
            # When BOTH face and a creature target are available AND the
            # neural-scorer flag is on, score each post-state and pick max.
            # The heuristic restricts face to opp.life ≤ 9 — the NN can
            # vote face even when life is higher if it predicts a higher
            # win probability there.
            if (getattr(gs, 'use_neural_scorer', False)
                    and target is not None and has_clock):
                try:
                    from lookahead import (argmax_action,
                                           hypothetical_life_delta,
                                           hypothetical_creature_removed)
                    _cands = [
                        ('face',     hypothetical_life_delta(opponent, -3)),
                        ('creature', hypothetical_creature_removed(opponent, target)),
                    ]
                    if getattr(gs, 'use_ensemble', False):
                        from determinization import ensemble_argmax_action
                        _best_tag, _best_score = ensemble_argmax_action(
                            gs, player, opponent, 'ur_delver',
                            _cands, default_tag=_bolt_mode, n_samples=5)
                    else:
                        _best_tag, _best_score = argmax_action(
                            gs, player, opponent, 'ur_delver',
                            _cands, default_tag=_bolt_mode)
                    if _best_tag == 'face' and _best_score is not None:
                        target = None  # override → go face
                        log_fn(f"[neural_scorer] face P(win)={_best_score:.2f} "
                               f"> creature → going face")
                    elif _best_tag == 'creature':
                        log_fn(f"[neural_scorer] keep target choice "
                               f"(P(win)={_best_score:.2f})")
                except Exception as _e:
                    log_fn(f"[neural_scorer] bolt lookahead error: {_e!r}")
            _b = [mana]
            def _resolve_bolt(c, _t=target):
                player.add_to_grave(c)
                if _t and _t.toughness <= 3:
                    opponent.remove_creature(_t)
                    log_fn(f"Lightning Bolt -> {_t.card.name}", True)
                    update_goyf(gs)
                else:
                    opponent.life -= 3
                    log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                    gs.check_life_totals()
            cast_spell(player, opponent, gs, bolt, _b, log_fn, log_entries,
                       on_resolve=_resolve_bolt, cost_override=1)
            mana = _b[0]

    if gs.game_over:
        return

    # ── 5. Unholy Heat — bigger removal (delirium = 6 dmg) ─────────────────

    heat = player.find_tag('heat')
    if heat and mana >= 1:
        # Count card types in GY for delirium
        gy_types = set()
        for c in player.graveyard:
            gy_types.add(getattr(c, 'gy_type', 'unknown'))
        delirium = len(gy_types) >= 4
        heat_dmg = 6 if delirium else 2

        # Only use Heat on creatures that need it
        heat_targets = [c for c in opponent.creatures if c.toughness <= heat_dmg]
        # Prefer big targets that Bolt can't handle
        heat_targets.sort(key=lambda c: -c.toughness)

        if heat_targets:
            target = heat_targets[0]
            # ── LEVER 2: Heat target lookahead via NN scorer ──────────
            if (getattr(gs, 'use_neural_scorer', False)
                    and len(heat_targets) >= 2):
                try:
                    from lookahead import (argmax_action,
                                           hypothetical_creature_removed)
                    _cands = [
                        (f"idx{i}",
                         hypothetical_creature_removed(opponent, perm))
                        for i, perm in enumerate(heat_targets)
                    ]
                    if getattr(gs, 'use_ensemble', False):
                        from determinization import ensemble_argmax_action
                        _best_tag, _best_score = ensemble_argmax_action(
                            gs, player, opponent, 'ur_delver',
                            _cands, default_tag='idx0', n_samples=5)
                    else:
                        _best_tag, _best_score = argmax_action(
                            gs, player, opponent, 'ur_delver',
                            _cands, default_tag='idx0')
                    if _best_tag is not None:
                        _best_idx = int(_best_tag.replace('idx', ''))
                        target = heat_targets[_best_idx]
                        if _best_score is not None:
                            log_fn(f"[neural_scorer] Heat target → "
                                   f"{target.card.name} (P(win)={_best_score:.2f})")
                except Exception as _e:
                    log_fn(f"[neural_scorer] heat lookahead error: {_e!r}")
            _trace_record('ur_heat_target', target.card.name, gs, player, opponent,
                          n_candidates=len(heat_targets), heat_dmg=heat_dmg)
            _b = [mana]
            def _resolve_heat(c, _t=target, _d=heat_dmg):
                player.add_to_grave(c)
                opponent.remove_creature(_t)
                log_fn(f"Unholy Heat ({_d} dmg) -> {_t.card.name}", True)
                update_goyf(gs)
            cast_spell(player, opponent, gs, heat, _b, log_fn, log_entries,
                       on_resolve=_resolve_heat, cost_override=1)
            mana = _b[0]

    if gs.game_over:
        return

    # ── 6. Combat ────────────────────────────────────────────────────────────

    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_ur_delver():
    """Smoke tests for UR Delver deck and strategy."""
    results = []

    # Test 1: Deck size is exactly 60
    deck = make_ur_delver_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present with correct counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1

    expected = {
        'delver': 4, 'drc': 4, 'murk': 4, 'borrow': 2,
        'bolt': 4, 'heat': 2,
        'bs': 4, 'ponder': 4, 'pre': 2,
        'fow': 4, 'daze': 4, 'pierce': 2,
        'ei': 2,
        'fetch': 8, 'dual': 6, 'basic': 4,
    }
    for tag, count in expected.items():
        actual = tag_counts.get(tag, 0)
        assert actual == count, f"Tag '{tag}': expected {count}, got {actual}"
    results.append("OK  All card counts match expected")

    # Test 3: Land count = 18
    land_count = sum(1 for c in deck if c.card_type == CardType.LAND)
    assert land_count == 18, f"Land count {land_count} != 18"
    results.append("OK  Land count = 18")

    # Test 4: Creature count = 14
    creature_count = sum(1 for c in deck if c.card_type == CardType.CREATURE)
    assert creature_count == 14, f"Creature count {creature_count} != 14"
    results.append("OK  Creature count = 14")

    # Test 5: Spell count = 28 (instants + sorceries)
    spell_count = sum(1 for c in deck
                      if c.card_type in (CardType.INSTANT, CardType.SORCERY))
    assert spell_count == 28, f"Spell count {spell_count} != 28"
    results.append("OK  Spell count = 28")

    # Test 6: Delver has flying, enters as 1/1 (unflipped)
    delver = next(c for c in deck if c.tag == 'delver')
    assert not getattr(delver, 'flying', False), "Delver (unflipped) should not have flying"
    assert delver.base_power == 1, f"Delver should be 1/1 unflipped, got {delver.base_power}/{delver.base_toughness}"
    assert delver.base_toughness == 1, f"Delver should be 1/1 unflipped"
    results.append("OK  Delver has no flying (unflipped), enters as 1/1")

    # Test 7: Murktide has delve + flying
    murk = next(c for c in deck if c.tag == 'murk')
    assert getattr(murk, 'delve', False), "Murktide should have delve"
    assert getattr(murk, 'flying', False), "Murktide should have flying"
    results.append("OK  Murktide has delve + flying")

    # Test 8: FoW has free_cast_if_blue
    fow = next(c for c in deck if c.tag == 'fow')
    assert getattr(fow, 'free_cast_if_blue', False), "FoW should have free_cast_if_blue"
    results.append("OK  Force of Will is free-castable")

    # Test 9: Strategy function is callable
    assert callable(_strategy_ur_delver), "Strategy should be callable"
    results.append("OK  Strategy function is callable")

    return results


if __name__ == '__main__':
    print("Running UR Delver tests...")
    for r in test_ur_delver():
        print(f"  {r}")
    print("All tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_ur_delver(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    threats = sum(1 for c in nonlands if c.is_creature())
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder', 'pre'))
    return 1 <= lc <= 3 and threats >= 1 and (cantrips >= 1 or len(hand) <= 5)


DECK_META = {
    'key':        'ur_delver',
    'name':       'UR Delver',
    'make_deck':  make_ur_delver_deck,
    'strategy':   _strategy_ur_delver,
    'keep':       _keep_ur_delver,
    'categories': {'aggro', 'tempo_mirror'},
    'interaction': {'speed': 2, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'bug_answers': 8},
    'meta_share': 0.06,
}
