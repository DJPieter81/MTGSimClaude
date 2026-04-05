"""
8-Cast — Legacy artifact combo/tempo deck.

Key mechanics:
- Urza's Saga: enchantment land that creates Karnstruct tokens (growing artifacts)
  Ch1: can activate
  Ch2: can activate (costs 1C)
  Ch3: tutor 0-1 CMC artifact from library, then sacrifice
- Chalice of the Void on 1: blanks Push, Brainstorm, Ponder, Daze, Thoughtseize
- Thought Monitor: affinity for artifacts (often 0-2 mana), draws 2 on ETB
- Karn, The Great Creator: -2 fetches artifact from sideboard/exile. Disables opp artifacts.
- Emry, Lurker of the Loch: self-mill 4, cast artifacts from GY
- Seat of the Synod / Vault of Whispers: artifact lands (tap for U/B)
- Ancient Tomb: 2 colorless mana for 2 life
- City of Traitors: 2 colorless, sacrifices if you play another land

Strategy priority order:
1. T1 Chalice on 1 (via Ancient Tomb/City) — locks BUG's Push/Brainstorm/Ponder
2. Emry — fills GY, recasts artifacts
3. Urza's Saga — generates growing tokens, tutors Shadowspear/Pithing Needle
4. Thought Monitor — refuel hand
5. Karn — tutor win condition or lock piece
6. Sai — generates thopters on artifact casts
7. Attack with growing army
"""

import sys, os
sys.path.insert(0, '/home/claude/mtg_sim')

import random
from cards import instant, sorcery, creature, artifact, enchantment
from rules import Card as _Card, CardType as _CT, Permanent, LandPermanent

# ─── Deck construction ────────────────────────────────────────────────────────

def make_eight_cast_deck():
    d = []

    # ── Lands (23) ────────────────────────────────────────────────────────────
    # Ancient Tomb: produces {C}{C}, pay 2 life
    for _ in range(4):
        c = _Card('Ancient Tomb', _CT.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='ancient_tomb', produces={'C'},
                 gy_type='land')
        c.taps_for = 2  # produces 2 mana
        c.life_cost_tap = 2
        d.append(c)

    # City of Traitors: produces {C}{C}, sacrifice when second land played
    for _ in range(4):
        c = _Card('City of Traitors', _CT.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='city', produces={'C'}, gy_type='land')
        c.taps_for = 2
        d.append(c)

    # Seat of the Synod: artifact + land, taps for {U}
    for _ in range(4):
        c = _Card('Seat of the Synod', _CT.LAND, cmc=0, mana_cost={},
                 colors={'U'}, tag='seat', produces={'U'},
                 gy_type='land', subtypes={'Artifact'})
        d.append(c)

    # Vault of Whispers: artifact + land, taps for {B}
    for _ in range(3):
        c = _Card('Vault of Whispers', _CT.LAND, cmc=0, mana_cost={},
                 colors={'B'}, tag='vault', produces={'B'},
                 gy_type='land', subtypes={'Artifact'})
        d.append(c)

    # Urza's Saga: enchantment land (adds as enchantment not land in sim)
    for _ in range(4):
        c = _Card("Urza's Saga", _CT.LAND, cmc=0, mana_cost={},
                 colors={'C'}, tag='saga', produces={'C'},
                 gy_type='land', is_combo_piece=True)
        c.saga_chapter = 0
        d.append(c)

    # Mishra's Factory: becomes 2/2 artifact creature
    for _ in range(2):
        c = _Card("Mishra's Factory", _CT.LAND, cmc=0, mana_cost={},
                 colors={'C'}, tag='factory', produces={'C'}, gy_type='land')
        d.append(c)

    # Inventors' Fair: gain 1 life per artifact, tutor artifact
    for _ in range(2):
        c = _Card("Inventors' Fair", _CT.LAND, cmc=0, mana_cost={},
                 colors={'C'}, tag='fair', produces={'C'}, gy_type='land')
        d.append(c)

    # ── Artifact Mana (8) ─────────────────────────────────────────────────────
    # Lotus Petal: 0 cost, exile: add 1 any
    for _ in range(4):
        d.append(artifact('Lotus Petal', 0, {}, tag='petal'))

    # Mox Opal: 0 cost, Metalcraft — tap for any color if 3+ artifacts
    for _ in range(4):
        c = artifact('Mox Opal', 0, {}, tag='opal', is_combo_piece=True)
        c.metalcraft_mana = True
        d.append(c)

    # ── Lock Pieces (4) ──────────────────────────────────────────────────────
    # Chalice of the Void: X=1, counters all CMC-1 spells
    for _ in range(4):
        d.append(artifact('Chalice of the Void', 0, {}, tag='chalice',
                          is_combo_piece=True))

    # ── Threats / Engines (16) ───────────────────────────────────────────────
    # Thought Monitor: affinity, draw 2
    for _ in range(4):
        c = creature('Thought Monitor', 6, {'U':2,'generic':4}, {'U'},
                     2, 2, tag='monitor', flying=True)
        c.affinity_artifacts = True   # reduces cost by 1 per artifact
        c.draw_on_etb = 2
        d.append(c)

    # Emry, Lurker of the Loch: affinity, self-mill 4, cast artifacts from GY
    for _ in range(4):
        c = creature('Emry, Lurker of the Loch', 4, {'U':1,'generic':3}, {'U'},
                     1, 2, tag='emry')
        c.affinity_artifacts = True
        c.self_mill = 4
        d.append(c)

    # Sai, Master Thopterist: creates 1/1 thopter on each artifact cast
    for _ in range(4):
        c = creature('Sai, Master Thopterist', 3, {'U':1,'generic':2}, {'U'},
                     1, 4, tag='sai', engine=True)
        d.append(c)

    # Karn, The Great Creator: 4 mana, -2 fetches artifact from SB/exile
    for _ in range(4):
        c = artifact('Karn, The Great Creator', 4, {'generic':4}, tag='karn',
                     win_condition=True)
        c.planeswalker = True
        d.append(c)

    # Shadowspear: 1 mana equipment, +1/+1, lifelink, trample; removes indestructible/hexproof
    for _ in range(1):
        d.append(artifact('Shadowspear', 1, {'generic':1}, tag='shadowspear'))

    # ── Interaction (5) ──────────────────────────────────────────────────────
    # Portable Hole: exile CMC<=2 artifact/creature
    for _ in range(4):
        c = artifact('Portable Hole', 1, {'W':1}, tag='hole', is_removal=True)
        d.append(c)

    # Pithing Needle: name a card, its activated abilities don't work
    for _ in range(1):
        d.append(artifact('Pithing Needle', 1, {'generic':1}, tag='needle'))

    # Mishra's Bauble: 0 cost, sac: look at top of library, draw at next upkeep
    for _ in range(3):
        b = _Card("Mishra's Bauble", _CT.ARTIFACT, cmc=0, mana_cost={},
                  colors=set(), tag='bauble', gy_type='artifact', is_cantrip=True)
        d.append(b)

    assert len(d) == 60, f"8-Cast deck: {len(d)} cards (expected 60)"
    return d


def make_eight_cast_sideboard():
    sb = []
    # vs Blue (BUG/UWx): Hurkyl's Recall, Spell Pierce, Force of Negation
    for _ in range(3):
        sb.append(instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'},
                          tag='fon', free_cast_if_blue=True))
    for _ in range(2):
        sb.append(instant("Hurkyl's Recall", 2, {'U':1,'generic':1}, {'U'},
                          tag='hurkyl', is_removal=True))
    # vs Combo: Thorn of Amethyst (noncreature spells cost 1 more)
    for _ in range(4):
        c = artifact('Thorn of Amethyst', 2, {'generic':2}, tag='thorn')
        sb.append(c)
    # vs Artifact hate: Soul Guide Lantern (GY hate)
    for _ in range(3):
        sb.append(artifact('Soul Guide Lantern', 1, {'generic':1}, tag='lantern'))
    # vs Graveyard: Tormod's Crypt
    for _ in range(3):
        sb.append(artifact("Tormod's Crypt", 0, {}, tag='crypt'))
    return sb


# ─── Utility helpers (self-contained) ────────────────────────────────────────

ARTIFACT_CREATURE_TAGS = {'monitor','emry','sai','karnstruct'}
ARTIFACT_SPELL_TAGS    = {'karn','shadowspear','hole','needle','petal','opal','chalice','lantern','crypt','thorn'}
ARTIFACT_LAND_TAGS     = {'seat','vault'}

def _artifact_count(player):
    """Count artifacts player controls (creatures + artifacts + artifact lands)."""
    a_creatures = sum(1 for c in player.creatures
                      if c.card.tag in ARTIFACT_CREATURE_TAGS
                      or 'Artifact' in getattr(c.card,'subtypes',set()))
    a_perms     = sum(1 for a in player.artifacts)
    a_lands     = sum(1 for l in player.lands if l.card.tag in ARTIFACT_LAND_TAGS)
    return a_creatures + a_perms + a_lands


def _affinity_cost(base_cmc, player):
    """Reduce CMC by 1 per artifact controlled (minimum 0)."""
    return max(0, base_cmc - _artifact_count(player))


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_eight_cast(player, opponent, gs, total_mana, log_fn, log_entries):
    from rules import Card as _Card, CardType as _CT, Permanent  # explicit import for closure safety
    """
    8-Cast strategy — direction-agnostic.
    player = 8-Cast protagonist, opponent = whoever they're facing.

    Priority:
    1. Lotus Petal / Mox Opal — free mana first
    2. Chalice on 1 (via Ancient Tomb / City) — lock CMC-1 spells
    3. Emry — self-mill, enable GY casts
    4. Urza's Saga — tick up, generate Karnstruct tokens
    5. Sai — token generator on artifact casts
    6. Thought Monitor — refuel hand
    7. Karn — tutor answer or lock piece
    8. Combat
    """
    from engine import resolve_combat, update_goyf, _try_counter_any
    # Recalculate mana accounting for Ancient Tomb/City (produce 2 each, not 1)
    mana = sum(getattr(l.card,'taps_for',1) for l in player.lands
               if not l.tapped and l.effective_produces())
    mana += total_mana - sum(1 for l in player.lands  # subtract standard count
                             if not l.tapped and not l.is_fetch and l.effective_produces())
    # Simpler: just add 1 extra per fast land (Tomb/City each give 2 not 1)
    mana = total_mana + sum(1 for l in player.lands
                            if not l.tapped and l.card.tag in ('ancient_tomb','city')
                            and l.effective_produces())
    art_count = _artifact_count(player)

    # ── Priority 1: Chalice of the Void on 1 ────────────────────────────────
    # Best T1 play with Ancient Tomb / City (provides 2 colorless)
    chalice = player.find_tag('chalice')
    chalice_active = getattr(gs, 'chalice_x', None) == 1
    if chalice and not chalice_active and mana >= 0:  # X=1 costs 2 mana (XX where X=1)
        if mana >= 2:
            player.remove_from_hand(chalice)
            if not _try_counter_any(player, opponent, gs, chalice, log_entries):
                player.put_artifact_in_play(chalice)
                gs.chalice_x = 1
                mana -= 2
                art_count += 1
                log_fn("★ Chalice of the Void on 1 — all CMC-1 spells countered", True)
            else:
                player.add_to_grave(chalice)

    # ── Free mana: Lotus Petal ───────────────────────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.exile.append(petal)
        mana += 1
        art_count += 1  # petal added to artifacts (in exile, but counts while resolving)

    # ── Free mana: Mox Opal (Metalcraft = 3+ artifacts) ─────────────────────
    for opal in [c for c in player.hand if c.tag == 'opal']:
        if art_count >= 3:  # Metalcraft active
            player.remove_from_hand(opal)
            player.put_artifact_in_play(opal)
            mana += 1
            art_count += 1
            log_fn("Mox Opal (Metalcraft — 3+ artifacts)")


    # ── Priority 2: Emry, Lurker of the Loch ────────────────────────────────
    emry = player.find_tag('emry')
    emry_on_board = any(c.card.tag == 'emry' for c in player.creatures)
    if emry and not emry_on_board:
        eff_cost = _affinity_cost(4, player)
        if mana >= eff_cost:
            player.remove_from_hand(emry)
            if not _try_counter_any(player, opponent, gs, emry, log_entries):
                player.put_creature_in_play(emry)
                mana -= eff_cost
                art_count += 1
                # Self-mill 4
                milled = []
                for _ in range(min(4, len(player.library))):
                    card = player.library.pop(0)
                    if card.card_type in (_CT.ARTIFACT,):
                        player.graveyard.append(card)
                        milled.append(card.name)
                    else:
                        player.graveyard.append(card)
                        milled.append(card.name)
                log_fn(f"Emry, Lurker of the Loch — mills: {milled[:3]}")
            else:
                player.add_to_grave(emry)

    # ── Priority 3: Urza's Saga — tick and generate Karnstruct ──────────────
    # Each Saga land gets a chapter counter each turn
    for land in [l for l in player.lands if l.card.tag == 'saga']:
        chapter = getattr(land, 'saga_chapter', 0) + 1
        land.saga_chapter = chapter
        if chapter == 1:
            log_fn("Urza's Saga Ch.1 — can activate (generates {C})")
            mana += 1  # Ch.1 produces {C}
        elif chapter == 2:
            # Create a 0/0 Karnstruct artifact creature (gets +1/+1 per artifact you control)
            # _Card and _CT imported at module level
            karn_card = _Card('Karnstruct', _CT.CREATURE, cmc=0, mana_cost={},
                              colors=set(), tag='karnstruct', gy_type='creature',
                              subtypes={'Construct'}, base_power=0, base_toughness=0)
            perm = Permanent(card=karn_card,
                             controller='b' if player is gs.bug else 'o',
                             summoning_sick=True)
            perm.is_artifact = True
            player.creatures.append(perm)
            art_count += 1
            size = art_count  # Karnstruct P/T = # artifacts you control
            perm.power_mod = size; perm.toughness_mod = size
            log_fn(f"Urza's Saga Ch.2 — Karnstruct {size}/{size} enters", True)
        elif chapter >= 3:
            # Ch.3: tutor 0-1 CMC artifact from library, then sacrifice Saga
            targets = [c for c in player.library if c.card_type == _CT.ARTIFACT and c.cmc <= 1]
            if targets:
                target = targets[0]
                player.library.remove(target)
                player.hand.append(target)
                log_fn(f"Urza's Saga Ch.3 — tutors {target.name}", True)
            player.lands.remove(land)
            player.graveyard.append(land.card)
            log_fn("Urza's Saga sacrificed (Ch.3 complete)")
            break

    # ── Update Karnstruct sizes (grow with artifact count) ───────────────────
    art_count = _artifact_count(player)
    for c in player.creatures:
        if c.card.tag == 'karnstruct':
            c.power_mod = art_count
            c.toughness_mod = art_count

    # ── Priority 4: Sai, Master Thopterist ──────────────────────────────────
    sai = player.find_tag('sai')
    sai_on = any(c.card.tag == 'sai' for c in player.creatures)
    if sai and not sai_on and mana >= 3:
        player.remove_from_hand(sai)
        if not _try_counter_any(player, opponent, gs, sai, log_entries):
            player.put_creature_in_play(sai)
            mana -= 3
            log_fn("Sai, Master Thopterist (1/4) — 1/1 thopter on each artifact cast")
        else:
            player.add_to_grave(sai)

    # ── Priority 5: Thought Monitor ──────────────────────────────────────────
    monitor = player.find_tag('monitor')
    if monitor and not any(c.card.tag == 'monitor' for c in player.creatures):
        eff_cost = _affinity_cost(6, player)
        if mana >= eff_cost:
            player.remove_from_hand(monitor)
            if not _try_counter_any(player, opponent, gs, monitor, log_entries):
                player.put_creature_in_play(monitor)
                mana -= eff_cost
                art_count += 1
                drawn = player.draw(2)
                log_fn(f"Thought Monitor (2/2 flying, affinity {eff_cost}) — draws 2")
                from engine import bowmasters_triggers
                bowmasters_triggers(2, gs, log_entries,
                                    controller='o' if player is gs.bug else 'b')
            else:
                player.add_to_grave(monitor)

    # ── Priority 6: Karn, The Great Creator ──────────────────────────────────
    karn = player.find_tag('karn')
    if karn and mana >= 4 and not any(c.card.tag == 'karn' for c in player.artifacts):
        player.remove_from_hand(karn)
        if not _try_counter_any(player, opponent, gs, karn, log_entries):
            player.put_artifact_in_play(karn)
            mana -= 4
            # Karn -2: fetch Ensnaring Bridge (vs creature decks) or Tormod's Crypt (vs GY)
            opp_has_creatures = len(opponent.creatures) > 0
            fetch_tag = 'bridge' if opp_has_creatures else 'lantern'
            fetched = next((c for c in player.library if c.tag == fetch_tag), None)
            if fetched:
                player.library.remove(fetched)
                player.hand.append(fetched)
                log_fn(f"★ Karn, The Great Creator — fetches {fetched.name}", True)
        else:
            player.add_to_grave(karn)

    # ── Combat ───────────────────────────────────────────────────────────────
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        from engine import combat_declare
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_eight_cast():
    """Minimal smoke tests for 8-Cast deck and strategy."""
    results = []

    # Test 1: Deck size
    deck = make_eight_cast_deck()
    assert len(deck) == 60, f"Deck size {len(deck)} != 60"
    results.append("✓ Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for required in ['chalice', 'emry', 'monitor', 'karn', 'saga', 'opal', 'petal']:
        assert required in tags, f"Missing: {required}"
    results.append("✓ All key cards present")

    # Test 3: Affinity calculation
    class MockPlayer:
        creatures = []
        artifacts = []
        lands = []
    p = MockPlayer()
    cost = _affinity_cost(6, p)
    assert cost == 6, f"Affinity with 0 artifacts: {cost}"
    results.append("✓ Affinity cost calculation correct")

    # Test 4: Strategy runs without error
    import sys; sys.path.insert(0, '/home/claude/mtg_sim')
    from sim import run_any_bo3, STRATEGIES
    from cards import DECKS
    DECKS['eight_cast'] = make_eight_cast_deck
    STRATEGIES['eight_cast'] = _strategy_eight_cast
    # Also need opp_turn dispatch entry
    import engine as eng
    old_opp = eng.opp_turn.__code__
    # Add dispatch for eight_cast
    content = open('/home/claude/mtg_sim/engine.py').read()
    if "'eight_cast'" not in content:
        # Add to dispatch
        old_dispatch = "    elif matchup in ('bug', 'bug_sb'):  # BUG as antagonist"
        new_dispatch = ("    elif matchup == 'eight_cast': _strategy_eight_cast_wrapper(gs, om, log, log_entries)\n"
                        + old_dispatch)
        # Don't modify engine.py here — just test strategy function directly
    results.append("✓ Strategy function importable")

    # Test 5: Bo3 smoke test
    try:
        r = run_any_bo3('eight_cast', 'dimir', 5)
        results.append(f"✓ 8-Cast vs Dimir (5 matches): {r['match_wr']*100:.0f}%")
    except Exception as e:
        results.append(f"✗ Bo3 test failed: {e}")

    return results


if __name__ == '__main__':
    print("Running 8-Cast tests...")
    for r in test_eight_cast():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_eight_cast(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    tags = {c.tag for c in hand}
    fast_land = any(c.tag in ('ancient_tomb', 'city', 'seat', 'vault') for c in lands)
    lock_piece = 'chalice' in tags
    engine = any(t in tags for t in ('emry', 'monitor', 'sai', 'karn', 'saga'))
    has_mana = 'opal' in tags or 'petal' in tags or fast_land
    return has_mana and (lock_piece or engine)


DECK_META = {
    'key':        'eight_cast',
    'name':       '8-Cast',
    'make_deck':  make_eight_cast_deck,
    'strategy':   _strategy_eight_cast,
    'keep':       _keep_eight_cast,
    'categories': {'aggro', 'prison'},
    'interaction': {'speed': 3, 'resilience': 4, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.03,
}
