"""
Cephalid Breakfast — Legacy combo deck (TrbnN, 6th Place).

The combo: Cephalid Illusionist + Nomads en-Kor (or Shuko) in play.
Nomads targets Illusionist repeatedly (0-cost ability), each targeting
mills 3 cards, milling the entire library. Narcomoebas enter from the
graveyard, then flashback Dread Return sacrificing 3 creatures to
reanimate Thassa's Oracle, whose ETB wins with an empty library.

Backup plan: Fair beats with Tamiyo and Voice of Victory, protected
by Force of Will, Daze, and Orim's Chant.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from cards import (creature, instant, sorcery, artifact, enchantment,
                   planeswalker, fetch_land, dual_land, basic_land, utility_land)
from rules import Card, CardType


# ─── Deck construction ────────────────────────────────────────────────────────

def make_cephalid_deck():
    d = []

    # ── Cantrips (8) ────────────────────────────────────────────────────────
    for _ in range(4):
        d.append(instant('Brainstorm', 1, {'U': 1}, {'U'}, tag='bs',
                         is_cantrip=True))

    for _ in range(4):
        d.append(sorcery('Ponder', 1, {'U': 1}, {'U'}, tag='ponder',
                         is_cantrip=True))

    # ── Combo Pieces (14) ───────────────────────────────────────────────────
    # Cephalid Illusionist: when targeted, mill 3 cards
    for _ in range(4):
        d.append(creature('Cephalid Illusionist', 2, {'U': 1, 'generic': 1},
                          {'U'}, 1, 1, tag='illusionist', is_combo_piece=True))

    # Nomads en-Kor: can target Illusionist repeatedly for free
    for _ in range(3):
        d.append(creature('Nomads en-Kor', 1, {'W': 1}, {'W'}, 1, 1,
                          tag='nomads', is_combo_piece=True))

    # Shuko: equipment, equip 0 — targets creature (triggers Illusionist)
    for _ in range(2):
        d.append(artifact('Shuko', 1, {'generic': 1}, tag='shuko',
                          is_combo_piece=True))

    # Narcomoeba: when milled, enters battlefield for free
    for _ in range(3):
        d.append(creature('Narcomoeba', 2, {'U': 1, 'generic': 1}, {'U'},
                          1, 1, tag='narco', flying=True, is_combo_piece=True))

    # Thassa's Oracle: ETB — if devotion >= cards in library, win the game
    d.append(creature("Thassa's Oracle", 2, {'U': 2}, {'U'}, 1, 3,
                      tag='oracle', is_combo_piece=True, win_condition=True))

    # Dread Return: flashback — sac 3 creatures, reanimate from GY
    d.append(sorcery('Dread Return', 4, {'B': 1, 'generic': 3}, {'B'},
                     tag='dread', is_combo_piece=True))

    # ── Interaction (9) ─────────────────────────────────────────────────────
    # Force of Will
    for _ in range(4):
        d.append(instant('Force of Will', 5, {'U': 1, 'generic': 4}, {'U'},
                         tag='fow', free_cast_if_blue=True))

    # Daze
    for _ in range(2):
        d.append(instant('Daze', 2, {'U': 1, 'generic': 1}, {'U'}, tag='daze'))

    # Swords to Plowshares
    for _ in range(2):
        d.append(instant('Swords to Plowshares', 1, {'W': 1}, {'W'},
                         tag='stp'))

    # ── Disruption / Protection (3) ─────────────────────────────────────────
    # Orim's Chant: opponent can't cast spells this turn
    for _ in range(2):
        d.append(instant("Orim's Chant", 1, {'W': 1}, {'W'}, tag='chant'))

    # Cabal Therapy: discard spell
    d.append(sorcery('Cabal Therapy', 1, {'B': 1}, {'B'}, tag='therapy'))

    # ── Tutor (1) ───────────────────────────────────────────────────────────
    # Step Through: wizardcycling for 3 mana, tutors Illusionist
    d.append(sorcery('Step Through', 5, {'U': 1, 'generic': 4}, {'U'},
                     tag='step'))

    # ── Fair Creatures (6) ──────────────────────────────────────────────────
    # Tamiyo, Inquisitive Student
    for _ in range(3):
        d.append(creature('Tamiyo, Inquisitive Student', 1, {'U': 1}, {'U'},
                          0, 3, tag='tamiyo'))

    # Voice of Victory: ETB create token, has protection
    for _ in range(3):
        d.append(creature('Voice of Victory', 2, {'W': 1, 'generic': 1},
                          {'W'}, 2, 1, tag='voice'))

    # ── Lands (19) ──────────────────────────────────────────────────────────
    # Fetch lands (9)
    for _ in range(4):
        d.append(fetch_land('Flooded Strand', ['Island', 'Plains']))

    for _ in range(4):
        d.append(fetch_land('Polluted Delta', ['Island', 'Swamp']))

    d.append(fetch_land('Marsh Flats', ['Swamp', 'Plains']))

    # Dual lands (3)
    for _ in range(2):
        d.append(dual_land('Tundra', ['U', 'W'], ['Island', 'Plains']))

    d.append(dual_land('Underground Sea', ['U', 'B'], ['Island', 'Swamp']))

    # Utility lands (2)
    d.append(utility_land('Meticulous Archive', ['U', 'W'], 'archive'))

    d.append(utility_land('Undercity Sewers', ['U', 'B'], 'sewers'))

    # Basic lands (3)
    for _ in range(2):
        d.append(basic_land('Island', 'U', 'Island'))

    d.append(basic_land('Plains', 'W', 'Plains'))

    # Urza's Saga (3) — special land, saga that tutors artifacts
    for _ in range(3):
        c = Card("Urza's Saga", CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='saga', produces={'C'}, gy_type='land',
                 is_combo_piece=True)
        c.saga_chapter = 0
        d.append(c)

    assert len(d) == 60, f"Cephalid deck: {len(d)} cards (expected 60)"
    return d


# ─── Combo resolution helper ─────────────────────────────────────────────────

def _resolve_cephalid_combo(player, opponent, gs, log_fn, log_entries):
    """
    Mill entire library, put Narcomoebas onto battlefield from graveyard,
    flashback Dread Return sacrificing 3 creatures to reanimate Thassa's Oracle.
    Oracle ETB: if devotion to blue >= cards in library → win the game.
    """
    from engine import _try_counter_any

    # 1. Mill entire library into graveyard
    milled = list(player.library)
    player.graveyard.extend(milled)
    player.library.clear()
    log_fn(f"★ Mill entire library ({len(milled)} cards)", True)

    # 2. Narcomoebas enter battlefield from graveyard (triggered ability, uncounterable)
    narcos = [c for c in player.graveyard if c.tag == 'narco']
    narco_count = 0
    for n in narcos:
        player.graveyard.remove(n)
        player.put_creature_in_play(n)
        narco_count += 1
    log_fn(f"  {narco_count} Narcomoeba(s) enter from graveyard", True)

    # 3. Flashback Dread Return: sacrifice 3 creatures, reanimate Oracle from GY
    #    Dread Return flashback is an alternate cost (exile from GY), not "cast from hand"
    oracle_in_gy = next((c for c in player.graveyard if c.tag == 'oracle'), None)
    dread_in_gy = next((c for c in player.graveyard if c.tag == 'dread'), None)
    sac_count = len(player.creatures)

    if dread_in_gy and oracle_in_gy and sac_count >= 3:
        # Sacrifice 3 creatures
        for _ in range(3):
            if player.creatures:
                sac = player.creatures.pop()
                player.add_to_grave(sac.card)
        player.graveyard.remove(dread_in_gy)
        player.exile.append(dread_in_gy)
        log_fn("  Flashback Dread Return (sac 3 creatures) → Thassa's Oracle", True)

        # Dread Return can be countered
        if not _try_counter_any(player, opponent, gs, dread_in_gy, log_entries):
            # Oracle enters — ETB: library is empty, so we win
            player.graveyard.remove(oracle_in_gy)
            player.put_creature_in_play(oracle_in_gy)
            log_fn("  ★ Thassa's Oracle ETB — library empty → WIN", True)
            gs.game_over = True
            gs.winner = 'p1' if player is gs.p1 else 'p2'
            gs.win_reason = "Cephalid Breakfast: Illusionist + Oracle"
            gs.kill_turn = gs.turn
        else:
            log_fn("  Dread Return countered — combo fizzles")
    elif oracle_in_gy and sac_count >= 0:
        # No Dread Return but have Oracle — can't reanimate, combo incomplete
        log_fn("  No Dread Return in graveyard — combo fizzles")
    else:
        log_fn("  Missing combo pieces in graveyard — combo fizzles")


# ─── Strategy ────────────────────────────────────────────────────────────────

def _strategy_cephalid(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Cephalid Breakfast combo strategy.

    Priority:
    1. Execute combo if both pieces in play (Illusionist + Nomads/Shuko)
    2. Cantrip to find combo pieces (Brainstorm, Ponder)
    3. Deploy Cephalid Illusionist (2 mana)
    4. Deploy Nomads en-Kor (1 mana) or cast Shuko (1 mana)
    5. Orim's Chant to protect combo turn
    6. Swords to Plowshares for removal
    7. Urza's Saga tutors Shuko
    8. Fair creatures as backup plan
    9. Combat with available creatures
    """
    from engine import _try_counter_any, combat_declare, bowmasters_triggers, update_goyf, cast_spell

    budget = [total_mana]

    # ── Track Shuko in play via attribute ────────────────────────────────────
    if not hasattr(gs, 'shuko_in_play'):
        gs.shuko_in_play = False

    # ── Check for combo: Illusionist + (Nomads or Shuko) in play ────────────
    illusionist_in_play = any(c.card.tag == 'illusionist' for c in player.creatures)
    nomads_in_play = any(c.card.tag == 'nomads' for c in player.creatures)
    shuko_in_play = gs.shuko_in_play

    if illusionist_in_play and (nomads_in_play or shuko_in_play):
        # Combo goes off — mill entire library, Narcomoeba enters,
        # Dread Return Oracle
        log_fn("★ Cephalid Illusionist combo activates!", True)
        _resolve_cephalid_combo(player, opponent, gs, log_fn, log_entries)
        if gs.game_over:
            return

    # ── Orim's Chant — protect combo turn if we have pieces ─────────────────
    chant = player.find_tag('chant')
    illusionist_in_hand = player.find_tag('illusionist')
    enabler_in_hand = (player.find_tag('nomads') or player.find_tag('shuko'))
    # Cast chant if we're about to combo (have pieces or one is in play)
    need_protection = (
        (illusionist_in_play and enabler_in_hand) or
        (illusionist_in_hand and (nomads_in_play or shuko_in_play))
    )
    if chant and budget[0] >= 1 and need_protection:
        def _resolve_chant(c):
            player.add_to_grave(c)
            log_fn("Orim's Chant — opponent can't cast spells this turn", True)
        cast_spell(player, opponent, gs, chant, budget, log_fn, log_entries,
                   on_resolve=_resolve_chant)

    # ── Cantrips — dig for combo pieces ─────────────────────────────────────
    for cantrip_tag in ('bs', 'ponder'):
        cantrip = player.find_tag(cantrip_tag)
        if cantrip and budget[0] >= 1:
            def _resolve_cant(c):
                player.add_to_grave(c)
                player.draw(1)
                log_fn(f"{c.name} — dig for combo")
                if hasattr(gs, 'bowmasters_on_board') and gs.bowmasters_on_board:
                    bowmasters_triggers(1, gs, log_entries,
                                        controller='o' if player is gs.p1 else 'b')
            cast_spell(player, opponent, gs, cantrip, budget, log_fn, log_entries,
                       on_resolve=_resolve_cant)
            gs.check_life_totals()
            if gs.game_over:
                return

    # ── Step Through — wizardcycling to tutor Illusionist ───────────────────
    step = player.find_tag('step')
    if step and budget[0] >= 3 and not illusionist_in_play:
        def _resolve_step(c):
            player.add_to_grave(c)
            target = next((cc for cc in player.library if cc.tag == 'illusionist'), None)
            if target:
                player.library.remove(target)
                player.hand.append(target)
                log_fn("Step Through (wizardcycling) → Cephalid Illusionist to hand")
            else:
                log_fn("Step Through (wizardcycling) — no Illusionist in library")
        cast_spell(player, opponent, gs, step, budget, log_fn, log_entries,
                   on_resolve=_resolve_step, cost_override=3)

    # ── Deploy Cephalid Illusionist (2 mana) ────────────────────────────────
    illusionist = player.find_tag('illusionist')
    if illusionist and budget[0] >= 2:
        def _resolve_ill(c):
            player.put_creature_in_play(c)
            log_fn("★ Cephalid Illusionist (combo piece)", True)
        if cast_spell(player, opponent, gs, illusionist, budget, log_fn, log_entries,
                      on_resolve=_resolve_ill, cost_override=2):
            nomads_in_play = any(c.card.tag == 'nomads' for c in player.creatures)
            if nomads_in_play or gs.shuko_in_play:
                log_fn("★ Combo assembled!", True)
                _resolve_cephalid_combo(player, opponent, gs, log_fn, log_entries)
                if gs.game_over:
                    return

    # ── Deploy Nomads en-Kor (1 mana) ──────────────────────────────────────
    nomads = player.find_tag('nomads')
    if nomads and budget[0] >= 1:
        def _resolve_nom(c):
            player.put_creature_in_play(c)
            log_fn("Nomads en-Kor (combo enabler)")
        if cast_spell(player, opponent, gs, nomads, budget, log_fn, log_entries,
                      on_resolve=_resolve_nom):
            illusionist_in_play = any(c.card.tag == 'illusionist' for c in player.creatures)
            if illusionist_in_play:
                log_fn("★ Combo assembled!", True)
                _resolve_cephalid_combo(player, opponent, gs, log_fn, log_entries)
                if gs.game_over:
                    return

    # ── Cast Shuko (1 mana artifact) ───────────────────────────────────────
    shuko = player.find_tag('shuko')
    if shuko and budget[0] >= 1:
        def _resolve_shuko(c):
            player.add_to_grave(c)  # proxy for "in play"
            gs.shuko_in_play = True
            log_fn("Shuko (equip 0 — combo enabler)")
        if cast_spell(player, opponent, gs, shuko, budget, log_fn, log_entries,
                      on_resolve=_resolve_shuko):
            illusionist_in_play = any(c.card.tag == 'illusionist' for c in player.creatures)
            if illusionist_in_play:
                log_fn("★ Combo assembled!", True)
                _resolve_cephalid_combo(player, opponent, gs, log_fn, log_entries)
                if gs.game_over:
                    return

    # ── Swords to Plowshares — removal ──────────────────────────────────────
    stp = player.find_tag('stp')
    if stp and budget[0] >= 1 and opponent.creatures:
        target = max(opponent.creatures, key=lambda c: c.card.base_power)
        if target.card.base_power >= 2:
            def _resolve_stp(c, _t=target):
                player.add_to_grave(c)
                if _t in opponent.creatures:
                    opponent.creatures.remove(_t)
                    opponent.life += _t.card.base_power
                    log_fn(f"Swords to Plowshares → exile {_t.card.name}")
                    update_goyf(gs)
            cast_spell(player, opponent, gs, stp, budget, log_fn, log_entries,
                       on_resolve=_resolve_stp)

    # ── Cabal Therapy — discard ─────────────────────────────────────────────
    therapy = player.find_tag('therapy')
    if therapy and budget[0] >= 1:
        def _resolve_therapy(c):
            player.add_to_grave(c)
            discarded = [cc for cc in opponent.hand if cc.tag == 'fow']
            for cc in discarded:
                opponent.hand.remove(cc)
                opponent.graveyard.append(cc)
            log_fn(f"Cabal Therapy naming Force of Will — hit {len(discarded)}")
        cast_spell(player, opponent, gs, therapy, budget, log_fn, log_entries,
                   on_resolve=_resolve_therapy)

    # ── Deploy fair creatures ───────────────────────────────────────────────
    tamiyo = player.find_tag('tamiyo')
    if tamiyo and budget[0] >= 1:
        def _resolve_tam(c):
            player.put_creature_in_play(c)
            log_fn("Tamiyo, Inquisitive Student (0/3)")
        cast_spell(player, opponent, gs, tamiyo, budget, log_fn, log_entries,
                   on_resolve=_resolve_tam)

    voice = player.find_tag('voice')
    if voice and budget[0] >= 2:
        def _resolve_voice(c):
            player.put_creature_in_play(c)
            log_fn("Voice of Victory (2/1)")
        cast_spell(player, opponent, gs, voice, budget, log_fn, log_entries,
                   on_resolve=_resolve_voice, cost_override=2)

    # ── Combat ──────────────────────────────────────────────────────────────
    if not gs.game_over:
        attackers = [c for c in player.creatures if not c.summoning_sick]
        if attackers:
            combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_cephalid():
    results = []

    # Test 1: Deck size
    deck = make_cephalid_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for req in ['illusionist', 'nomads', 'shuko', 'narco', 'oracle', 'dread',
                'bs', 'ponder', 'fow', 'daze', 'stp', 'chant', 'therapy',
                'step', 'tamiyo', 'voice', 'saga', 'fetch', 'dual', 'basic',
                'archive', 'sewers']:
        assert req in tags, f"Missing tag: {req}"
    results.append("OK  All key card types present")

    # Test 3: Card counts
    from collections import Counter
    tag_counts = Counter(c.tag for c in deck)
    assert tag_counts['illusionist'] == 4, f"Illusionist: {tag_counts['illusionist']}"
    assert tag_counts['nomads'] == 3, f"Nomads: {tag_counts['nomads']}"
    assert tag_counts['shuko'] == 2, f"Shuko: {tag_counts['shuko']}"
    assert tag_counts['narco'] == 3, f"Narcomoeba: {tag_counts['narco']}"
    assert tag_counts['oracle'] == 1, f"Oracle: {tag_counts['oracle']}"
    assert tag_counts['dread'] == 1, f"Dread Return: {tag_counts['dread']}"
    assert tag_counts['bs'] == 4, f"Brainstorm: {tag_counts['bs']}"
    assert tag_counts['ponder'] == 4, f"Ponder: {tag_counts['ponder']}"
    assert tag_counts['fow'] == 4, f"FoW: {tag_counts['fow']}"
    assert tag_counts['stp'] == 2, f"StP: {tag_counts['stp']}"
    assert tag_counts['saga'] == 3, f"Saga: {tag_counts['saga']}"
    assert tag_counts['fetch'] == 9, f"Fetch: {tag_counts['fetch']}"
    results.append("OK  All card counts correct")

    # Test 4: Combo pieces marked correctly
    combo_pieces = [c for c in deck if c.is_combo_piece]
    combo_tags = {c.tag for c in combo_pieces}
    for req in ['illusionist', 'nomads', 'shuko', 'narco', 'oracle', 'dread',
                'saga']:
        assert req in combo_tags, f"Missing combo piece: {req}"
    results.append("OK  Combo pieces flagged correctly")

    # Test 5: Land count
    lands = [c for c in deck if c.is_land()]
    assert len(lands) == 20, f"Expected 20 lands, got {len(lands)}"
    results.append("OK  Land count = 20")

    # Test 6: Win condition present
    win_cons = [c for c in deck if c.win_condition]
    assert len(win_cons) >= 1, "No win condition found"
    assert any(c.tag == 'oracle' for c in win_cons)
    results.append("OK  Win condition: Thassa's Oracle")

    return results


if __name__ == '__main__':
    print("Running Cephalid Breakfast tests...")
    for r in test_cephalid():
        print(f"  {r}")
    print("All Cephalid Breakfast tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_cephalid(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_combo = any(t in tags for t in ('illusionist', 'nomads', 'shuko'))
    has_cantrip = any(c.is_cantrip for c in nonlands)
    has_protection = any(t in tags for t in ('fow', 'daze', 'chant'))
    if len(hand) <= 5: return lc >= 1 and (has_combo or has_cantrip)
    return 1 <= lc <= 4 and (has_combo or has_cantrip) and (has_combo or has_protection)


DECK_META = {
    'key':        'cephalid',
    'name':       'Cephalid Breakfast',
    'make_deck':  make_cephalid_deck,
    'strategy':   _strategy_cephalid,
    'keep':       _keep_cephalid,
    'categories': {'combo', 'gy_combo'},
    'interaction': {'speed': 3, 'resilience': 2, 'uses_graveyard': True, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.01,
}
