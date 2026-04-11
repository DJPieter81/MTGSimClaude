"""
Sneak & Show (rerere, 1st Place) — Legacy Challenge Top 8.

Sneak Attack + Show and Tell combo deck. The plan:
- Show and Tell (3 mana sorcery): each player puts a permanent from hand into play.
  We put Emrakul (15/15 haste flying trample) or Omniscience or Sneak Attack.
- Sneak Attack (4 mana enchantment): pay R, put a creature from hand into play
  with haste. It's sacrificed at end of turn, but Emrakul deals 15 = lethal.
- Atraxa, Grand Unifier (7/7 flying lifelink vigilance): backup fatty.

Fast mana: Ancient Tomb (taps for 2, costs 2 life), City of Traitors (taps for 2),
Lotus Petal (free +1 mana).

Cantrips: Brainstorm, Ponder, Stock Up (draw 2 for 2).
Protection: Force of Will, Daze, Sink into Stupor (bounce).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import (creature, instant, sorcery, artifact, enchantment,
                   fetch_land, dual_land, basic_land, utility_land)
from rules import Card, CardType


# --- Deck construction --------------------------------------------------------

def make_sneak_a_deck():
    d = []

    # -- Lands (19) ------------------------------------------------------------

    # Ancient Tomb x4: taps for 2 colorless, costs 2 life
    for _ in range(4):
        c = Card('Ancient Tomb', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='tomb', produces={'C'}, gy_type='land')
        c.taps_for = 2
        c.life_cost_tap = 2
        d.append(c)

    # City of Traitors x1: taps for 2 colorless (sacrificed when another land enters)
    for _ in range(1):
        c = Card('City of Traitors', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='city', produces={'C'}, gy_type='land')
        c.taps_for = 2
        d.append(c)

    # Fetch lands
    for _ in range(4):
        d.append(fetch_land('Misty Rainforest', ['Island', 'Forest']))
    for _ in range(4):
        d.append(fetch_land('Scalding Tarn', ['Island', 'Mountain']))

    # Dual lands
    for _ in range(2):
        d.append(dual_land('Volcanic Island', ['U', 'R'], ['Island', 'Mountain']))

    # Utility lands
    for _ in range(2):
        d.append(utility_land('Thundering Falls', ['U', 'R'], 'tfall'))

    # Basic lands
    for _ in range(2):
        d.append(basic_land('Island', 'U', 'Island'))
    for _ in range(1):
        d.append(basic_land('Mountain', 'R', 'Mountain'))

    # -- Fast Mana (4) ---------------------------------------------------------

    # Lotus Petal x4
    for _ in range(4):
        d.append(artifact('Lotus Petal', 0, {}, tag='petal', mana_ritual=True))

    # -- Cantrips (12) ---------------------------------------------------------

    # Brainstorm x4
    for _ in range(4):
        d.append(instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs', is_cantrip=True))

    # Ponder x4
    for _ in range(4):
        d.append(sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder', is_cantrip=True))

    # Stock Up x4: instant, draw 2 for 2
    for _ in range(4):
        d.append(instant('Stock Up', 2, {'U': 1, 'generic': 1}, {'U'},
                         tag='stock', is_cantrip=True))

    # -- Combo Pieces (14) -----------------------------------------------------

    # Show and Tell x4
    for _ in range(4):
        d.append(sorcery('Show and Tell', 3, {'U': 1, 'generic': 2}, {'U'},
                         tag='sat', is_combo_piece=True, win_condition=True))

    # Sneak Attack x4
    for _ in range(4):
        d.append(enchantment('Sneak Attack', 4, {'R': 1, 'generic': 3}, {'R'},
                             tag='sneak', is_combo_piece=True, win_condition=True))

    # Emrakul, the Aeons Torn x3
    for _ in range(3):
        d.append(creature('Emrakul, the Aeons Torn', 15, {'generic': 15}, set(),
                          15, 15, tag='emrakul', flying=True, trample=True,
                          haste=True, win_condition=True))

    # Atraxa, Grand Unifier x4
    for _ in range(4):
        d.append(creature('Atraxa, Grand Unifier', 7,
                          {'W': 1, 'U': 1, 'B': 1, 'G': 2, 'generic': 2},
                          {'W', 'U', 'B', 'G'}, 7, 7, tag='atraxa',
                          flying=True, lifelink=True, vigilance=True,
                          deathtouch=True, win_condition=True))

    # Omniscience x2
    for _ in range(2):
        d.append(enchantment('Omniscience', 10, {'U': 1, 'generic': 9}, {'U'},
                             tag='omni', win_condition=True))

    # -- Protection (7) --------------------------------------------------------

    # Force of Will x4
    for _ in range(4):
        d.append(instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                         tag='fow', free_cast_if_blue=True))

    # Daze x2
    for _ in range(2):
        d.append(instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'}, tag='daze'))

    # Sink into Stupor x1
    for _ in range(1):
        d.append(instant('Sink into Stupor', 3, {'U': 1, 'generic': 2}, {'U'},
                         tag='sink'))

    assert len(d) == 60, f"sneak_a deck: {len(d)} cards (expected 60)"
    return d


# --- Strategy -----------------------------------------------------------------

def _strategy_sneak_a(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Sneak & Show strategy (rerere, 1st Place).

    Priority:
    1. Count effective mana (lands + tomb bonus + city bonus + petals)
    2. Cantrip to dig for combo pieces
    3. Show and Tell with a payoff in hand
    4. Sneak Attack activation with a creature in hand
    5. Combat with any creatures in play
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf

    mana = total_mana

    # -- Effective mana: count bonus from sol lands + petals in hand ------------
    tomb_bonus = sum(1 for l in player.lands
                     if l.card.tag == 'tomb' and not l.tapped)
    city_bonus = sum(1 for l in player.lands
                     if l.card.tag == 'city' and not l.tapped)
    petals_in_hand = [c for c in player.hand if c.tag == 'petal']
    effective_mana = mana + tomb_bonus + city_bonus + len(petals_in_hand)

    # -- Assess hand -----------------------------------------------------------
    payoffs = [c for c in player.hand
               if c.tag in ('emrakul', 'atraxa', 'omni', 'sneak')]
    has_sat = any(c.tag == 'sat' for c in player.hand)
    has_sneak_in_play = any(hasattr(p, 'card') and p.card.tag == 'sneak'
                           for p in getattr(player, 'enchantments', []))
    cantrips = [c for c in player.hand
                if c.tag in ('bs', 'ponder', 'stock')]
    creature_payoffs = [c for c in player.hand
                        if c.tag in ('emrakul', 'atraxa')]

    # -- Step 1: Crack Lotus Petals for mana if we're going to combo ----------
    can_combo = has_sat and payoffs and effective_mana >= 3
    can_sneak = (has_sneak_in_play and creature_payoffs and effective_mana >= 1)

    if can_combo or can_sneak:
        for petal in list(petals_in_hand):
            player.remove_from_hand(petal)
            player.exile.append(petal)
            mana += 1
            player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
            log_fn(f"Lotus Petal (+1 mana={mana})")
        petals_in_hand = []

    # -- Step 2: Cast cantrips to dig for combo --------------------------------
    if not can_combo and not can_sneak:
        for cantrip in list(cantrips):
            cost = cantrip.cmc
            if mana >= cost:
                player.remove_from_hand(cantrip)
                player.add_to_grave(cantrip)
                mana -= cost
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                draws = 2 if cantrip.tag == 'stock' else 1
                player.draw(draws)
                log_fn(f"{cantrip.name} (draw {draws}, mana={mana})")
                bowmasters_triggers(draws, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
                gs.check_life_totals()
                if gs.game_over:
                    return
                break  # one cantrip per turn is usually enough
        gs.state_based_actions()
        return

    # If we're going to combo, still cast cantrips first if we have spare mana
    spare_mana = mana - 3  # save 3 for Show and Tell
    if can_combo and spare_mana >= 1:
        for cantrip in list(cantrips):
            cost = cantrip.cmc
            if cost <= spare_mana and cantrip in player.hand:
                player.remove_from_hand(cantrip)
                player.add_to_grave(cantrip)
                mana -= cost
                spare_mana -= cost
                player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1
                draws = 2 if cantrip.tag == 'stock' else 1
                player.draw(draws)
                log_fn(f"{cantrip.name} (draw {draws}, mana={mana})")
                bowmasters_triggers(draws, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
                gs.check_life_totals()
                if gs.game_over:
                    return
                break

    # -- Step 3: Show and Tell with payoff -------------------------------------
    sat = player.find_tag('sat')
    # Re-check payoffs (hand may have changed from cantrips)
    payoffs = [c for c in player.hand
               if c.tag in ('emrakul', 'atraxa', 'omni', 'sneak')]
    if sat and payoffs and mana >= 3 and not gs.game_over:
        if not _try_counter_any(player, opponent, gs, sat, log_entries):
            player.remove_from_hand(sat)
            player.add_to_grave(sat)
            mana -= 3
            player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1

            # Choose best payoff: Emrakul > Omniscience > Sneak Attack > Atraxa
            payoff_priority = {'emrakul': 0, 'omni': 1, 'sneak': 2, 'atraxa': 3}
            best = min(payoffs, key=lambda c: payoff_priority.get(c.tag, 99))
            player.remove_from_hand(best)

            if best.tag == 'emrakul':
                perm = player.put_creature_in_play(best)
                perm.summoning_sick = False  # haste
                log_fn(f"Show and Tell -> Emrakul (15/15 haste flying trample)!", True)
                # Emrakul attacks immediately for 15 — usually lethal
                opponent.life -= 15
                log_fn(f"Emrakul attacks for 15! Opponent at {opponent.life}", True)
                if opponent.life <= 0:
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = "Sneak & Show: Show and Tell -> Emrakul lethal"
                    gs.kill_turn = gs.turn
            elif best.tag == 'atraxa':
                perm = player.put_creature_in_play(best)
                log_fn(f"Show and Tell -> Atraxa (7/7 flying lifelink vigilance)", True)
                # Atraxa ETB: draw cards (simplified as draw 3)
                player.draw(3)
                player.life += 3  # approximate lifelink value
                log_fn(f"Atraxa ETB: drew cards, life={player.life}")
                bowmasters_triggers(3, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
            elif best.tag == 'omni':
                player.add_to_grave(best)  # enchantment goes to "in play" conceptually
                log_fn(f"Show and Tell -> Omniscience! (cast anything for free)", True)
                gs.game_over = True
                gs.winner = 'p1' if player is gs.p1 else 'p2'
                gs.win_reason = "Sneak & Show: Omniscience in play"
                gs.kill_turn = gs.turn
            elif best.tag == 'sneak':
                log_fn(f"Show and Tell -> Sneak Attack! (activate for R)", True)
                # Now try to activate Sneak Attack immediately
                creature_in_hand = next(
                    (c for c in player.hand if c.tag in ('emrakul', 'atraxa')),
                    None)
                if creature_in_hand and mana >= 1:
                    player.remove_from_hand(creature_in_hand)
                    mana -= 1
                    if creature_in_hand.tag == 'emrakul':
                        perm = player.put_creature_in_play(creature_in_hand)
                        perm.summoning_sick = False
                        log_fn(f"Sneak Attack -> Emrakul (15/15 haste)!", True)
                        opponent.life -= 15
                        log_fn(f"Emrakul attacks for 15! Opponent at {opponent.life}", True)
                        if opponent.life <= 0:
                            gs.game_over = True
                            gs.winner = 'p1' if player is gs.p1 else 'p2'
                            gs.win_reason = "Sneak & Show: Sneak Attack -> Emrakul lethal"
                            gs.kill_turn = gs.turn
                    else:
                        perm = player.put_creature_in_play(creature_in_hand)
                        perm.summoning_sick = False
                        log_fn(f"Sneak Attack -> Atraxa (7/7 haste)!", True)
                        player.draw(3)
                        bowmasters_triggers(3, gs, log_entries,
                                            controller='o' if player is gs.p1 else 'b')
                else:
                    # Sneak Attack in play but no creature — still strong position
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = "Sneak & Show: Sneak Attack in play"
                    gs.kill_turn = gs.turn + 1
        else:
            player.add_to_grave(sat)
            log_fn("Show and Tell countered")

    # -- Step 4: Sneak Attack activation (if already in play) ------------------
    if has_sneak_in_play and not gs.game_over:
        creature_in_hand = next(
            (c for c in player.hand if c.tag in ('emrakul', 'atraxa')), None)
        if creature_in_hand and mana >= 1:
            # Crack petals if needed
            if mana < 1:
                for petal in [c for c in player.hand if c.tag == 'petal']:
                    player.remove_from_hand(petal)
                    player.exile.append(petal)
                    mana += 1
                    break
            player.remove_from_hand(creature_in_hand)
            mana -= 1
            if creature_in_hand.tag == 'emrakul':
                perm = player.put_creature_in_play(creature_in_hand)
                perm.summoning_sick = False
                log_fn(f"Sneak Attack -> Emrakul (15/15 haste)!", True)
                opponent.life -= 15
                if opponent.life <= 0:
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = "Sneak & Show: Sneak Attack -> Emrakul"
                    gs.kill_turn = gs.turn
            else:
                perm = player.put_creature_in_play(creature_in_hand)
                perm.summoning_sick = False
                log_fn(f"Sneak Attack -> Atraxa (7/7 haste)!", True)
                player.draw(3)
                bowmasters_triggers(3, gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')

    # -- Step 5: Combat with any creatures in play -----------------------------
    if not gs.game_over:
        attackers = [p for p in player.creatures
                     if not p.summoning_sick or p.card.haste]
        if attackers:
            combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# --- Mini test suite ----------------------------------------------------------

def test_sneak_a():
    results = []

    # Test 1: Deck size
    deck = make_sneak_a_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("ok Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for req in ['tomb', 'sat', 'sneak', 'emrakul', 'atraxa', 'omni',
                'fow', 'bs', 'ponder', 'stock', 'petal', 'daze']:
        assert req in tags, f"Missing: {req}"
    results.append("ok All key cards present")

    # Test 3: Card counts
    tag_counts = {}
    for c in deck:
        tag_counts[c.tag] = tag_counts.get(c.tag, 0) + 1
    assert tag_counts['sat'] == 4, f"Show and Tell count: {tag_counts['sat']}"
    assert tag_counts['sneak'] == 4, f"Sneak Attack count: {tag_counts['sneak']}"
    assert tag_counts['emrakul'] == 3, f"Emrakul count: {tag_counts['emrakul']}"
    assert tag_counts['atraxa'] == 4, f"Atraxa count: {tag_counts['atraxa']}"
    assert tag_counts['fow'] == 4, f"FoW count: {tag_counts['fow']}"
    assert tag_counts['petal'] == 4, f"Petal count: {tag_counts['petal']}"
    results.append("ok Card counts correct")

    # Test 4: Land count
    land_count = sum(1 for c in deck if c.is_land())
    results.append(f"ok Land count: {land_count}")

    # Test 5: Mana sources
    assert tag_counts.get('tomb', 0) == 4, "Ancient Tomb x4"
    assert tag_counts.get('city', 0) == 1, "City of Traitors x1"
    results.append("ok Sol lands correct")

    # Test 6: Bo3 smoke test
    from sim import STRATEGIES
    from cards import DECKS
    DECKS['sneak_a'] = make_sneak_a_deck
    STRATEGIES['sneak_a'] = _strategy_sneak_a
    try:
        from sim import run_any_bo3
        r = run_any_bo3('sneak_a', 'dimir', 10)
        results.append(f"ok Sneak A vs Dimir (10 matches): {r['match_wr']*100:.0f}%")
    except Exception as e:
        results.append(f"FAIL Bo3 failed: {e}")

    return results


if __name__ == '__main__':
    print("Running Sneak A tests...")
    for r in test_sneak_a():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_sneak_a(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_sat = 'sat' in tags
    has_payoff = any(t in tags for t in ('emrakul', 'atraxa', 'omni', 'sneak'))
    has_cantrip = any(c.is_cantrip for c in nonlands)
    fast_mana = sum(1 for c in hand if c.tag in ('petal', 'tomb', 'city'))
    mana_ok = lc >= 1 or fast_mana >= 1
    has_action = has_sat or has_payoff or has_cantrip
    if len(hand) <= 5: return mana_ok and (has_sat or has_payoff or has_cantrip)
    return mana_ok and 1 <= lc <= 5 and has_action


DECK_META = {
    'key':        'sneak_a',
    'name':       'Sneak & Show A (rerere)',
    'make_deck':  make_sneak_a_deck,
    'strategy':   _strategy_sneak_a,
    'keep':       _keep_sneak_a,
    'categories': {'combo', 'land_combo'},
    'interaction': {'speed': 3, 'resilience': 3, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.04,
}
