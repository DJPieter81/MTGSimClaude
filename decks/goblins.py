"""
Goblins — Legacy tribal aggro/combo deck.

Key plan:
- T1 Goblin Lackey or Aether Vial
- Lackey combat damage → free Muxus/Matron from hand
- Muxus ETB → put ~3 Goblins from top 6 into play
- Matron ETB → tutor any Goblin to hand
- Overwhelm with creature swarm
"""
import sys
sys.path.insert(0, '.')

from cards import creature, instant, sorcery, artifact
from rules import Card, CardType


# ─── Deck construction ────────────────────────────────────────────────────────

def make_goblins_deck():
    d = []

    # ── Creatures (32) ────────────────────────────────────────────────────────
    # Goblin Lackey: 1/1, {R}, when deals combat damage → put Goblin from hand
    for _ in range(4):
        d.append(creature('Goblin Lackey', 1, {'R': 1}, {'R'}, 1, 1,
                          tag='lackey', is_combo_piece=True))

    # Goblin Matron: 1/1, {2R}, ETB tutor a Goblin
    for _ in range(4):
        d.append(creature('Goblin Matron', 3, {'R': 1, 'generic': 2}, {'R'}, 1, 1,
                          tag='matron'))

    # Muxus, Goblin Grandee: 4/4, {4RR}, ETB reveal top 6 → put Goblins in play
    for _ in range(3):
        d.append(creature('Muxus, Goblin Grandee', 6, {'R': 2, 'generic': 4}, {'R'}, 4, 4,
                          tag='muxus', is_combo_piece=True))

    # Goblin Ringleader: 2/2, {3R}, ETB reveal 4 → Goblins to hand
    for _ in range(4):
        d.append(creature('Goblin Ringleader', 4, {'R': 1, 'generic': 3}, {'R'}, 2, 2,
                          tag='ringleader'))

    # Goblin Warchief: 2/2, {1RR}, Goblins cost {1} less, Goblins have haste
    for _ in range(2):
        d.append(creature('Goblin Warchief', 3, {'R': 2, 'generic': 1}, {'R'}, 2, 2,
                          tag='warchief', haste=True))

    # Munitions Expert: 1/1, {BR}, ETB deal damage = # Goblins you control
    for _ in range(3):
        d.append(creature('Munitions Expert', 2, {'B': 1, 'R': 1}, {'B', 'R'}, 1, 1,
                          tag='expert', is_removal=True))

    # Sling-Gang Lieutenant: 1/1, {3B}, creates 2 tokens, sac: drain 1
    for _ in range(2):
        d.append(creature('Sling-Gang Lieutenant', 4, {'B': 1, 'generic': 3}, {'B'}, 1, 1,
                          tag='sling'))

    # Goblin Cratermaker: 2/2, {1R}, sac: deal 2 or destroy artifact
    for _ in range(4):
        d.append(creature('Goblin Cratermaker', 2, {'R': 1, 'generic': 1}, {'R'}, 2, 2,
                          tag='cratermaker', is_removal=True))

    # Pashalik Mons: 2/2, {2R}, when a Goblin dies, deal 1 damage
    for _ in range(2):
        d.append(creature('Pashalik Mons', 3, {'R': 1, 'generic': 2}, {'R'}, 2, 2,
                          tag='pashalik'))

    # Skirk Prospector: 1/1, {R}, sac a Goblin: add {R}
    for _ in range(2):
        d.append(creature('Skirk Prospector', 1, {'R': 1}, {'R'}, 1, 1,
                          tag='prospector'))

    # Fury: 3/3, {3RR}, evoke: exile red card, 4 damage divided
    for _ in range(2):
        d.append(creature('Fury', 5, {'R': 2, 'generic': 3}, {'R'}, 3, 3,
                          tag='fury', haste=True))

    # ── Artifacts (6) ─────────────────────────────────────────────────────────
    # Aether Vial: {1}
    for _ in range(4):
        d.append(artifact('Aether Vial', 1, {'generic': 1}, tag='vial',
                          engine=True))

    # Chrome Mox: {0}, exile nonartifact nonland → add 1 mana
    for _ in range(2):
        d.append(artifact('Chrome Mox', 0, {}, tag='chrome_mox'))

    # ── Sorceries (2) ─────────────────────────────────────────────────────────
    # Thoughtseize: {B}
    for _ in range(2):
        d.append(sorcery('Thoughtseize', 1, {'B': 1}, {'B'}, tag='ts',
                          life_cost=2))

    # ── Lands (20) ────────────────────────────────────────────────────────────
    # Cavern of Souls — uncounterable Goblins
    for _ in range(4):
        c = Card('Cavern of Souls', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='cavern', produces={'R'}, gy_type='land')
        d.append(c)

    # Badlands (dual)
    for _ in range(4):
        c = Card('Badlands', CardType.LAND, cmc=0, mana_cost={},
                 colors={'B', 'R'}, tag='dual', produces={'B', 'R'},
                 subtypes={'Swamp', 'Mountain'}, gy_type='land')
        d.append(c)

    # Auntie's Hovel
    for _ in range(4):
        c = Card('Auntie\'s Hovel', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='hovel', produces={'B', 'R'}, gy_type='land')
        d.append(c)

    # Bloodstained Mire (fetch)
    for _ in range(2):
        c = Card('Bloodstained Mire', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land')
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # Wooded Foothills (fetch)
    for _ in range(2):
        c = Card('Wooded Foothills', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land')
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # Mountain (basic)
    for _ in range(2):
        c = Card('Mountain', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='basic', produces={'R'}, gy_type='land',
                 is_basic=True)
        d.append(c)

    # Swamp (basic)
    for _ in range(2):
        c = Card('Swamp', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='basic', produces={'B'}, gy_type='land',
                 is_basic=True)
        d.append(c)

    assert len(d) == 60, f"Goblins deck has {len(d)} cards"
    return d


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_goblins(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Goblins strategy — tribal aggro with explosive Muxus turns.

    Priority:
    1. T1: Aether Vial or Goblin Lackey
    2. Vial ticks each turn; at 3+ counters flash in Matron/Ringleader
    3. Lackey combat damage → put Muxus or big Goblin from hand
    4. Matron ETB → tutor Muxus to hand
    5. Muxus ETB → put ~3 Goblins into play
    6. Munitions Expert ETB → removal
    7. Attack with everything
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare

    rem = total_mana
    goblin_count = len(player.creatures)

    # ── Aether Vial T1-T2 ──────────────────────────────────────────────────
    vial = player.find_tag('vial')
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial and not vial_on_board and rem >= 1 and gs.turn <= 3:
        player.remove_from_hand(vial)
        if not _try_counter_any(player, opponent, gs, vial, log_entries):
            player.put_artifact_in_play(vial)
            gs.vial_counters = 0
            gs._vial_entered_last_turn = True
            log_fn("Aether Vial enters play")
        else:
            player.add_to_grave(vial)

    # ── Vial tick (upkeep) ──────────────────────────────────────────────────
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial_on_board and not getattr(gs, '_vial_entered_last_turn', False):
        gs.vial_counters = getattr(gs, 'vial_counters', 0) + 1
        if gs.vial_counters <= 6:
            log_fn(f"Vial ticks to {gs.vial_counters}")
    gs._vial_entered_last_turn = False

    # ── Chrome Mox for fast mana ────────────────────────────────────────────
    mox = player.find_tag('chrome_mox')
    if mox and not any(p.card.tag == 'chrome_mox' for p in player.artifacts):
        pitch = next((c for c in player.hand
                      if c is not mox and not c.is_land()
                      and c.tag not in ('chrome_mox', 'muxus', 'lackey')
                      and c.colors), None)
        if pitch:
            player.remove_from_hand(mox)
            player.put_artifact_in_play(mox)
            player.remove_from_hand(pitch)
            player.exile.append(pitch)
            rem += 1
            log_fn(f"Chrome Mox (exile {pitch.name}) → +1 mana")

    # ── Thoughtseize T1-T2 (if no Lackey/Vial) ─────────────────────────────
    ts = player.find_tag('ts')
    if ts and rem >= 1 and gs.turn <= 2 and not player.find_tag('lackey'):
        player.remove_from_hand(ts)
        if not _try_counter_any(player, opponent, gs, ts, log_entries):
            player.add_to_grave(ts)
            player.life -= 2
            target = (opponent.find_any(lambda c: c.free_cast_if_blue) or
                      opponent.find_any(lambda c: c.is_creature()) or
                      next((c for c in opponent.hand if not c.is_land()), None))
            if target:
                opponent.hand.remove(target)
                log_fn(f"Thoughtseize strips {target.name}", True)
            rem -= 1
        else:
            player.add_to_grave(ts)
            rem -= 1

    # ── Goblin Lackey T1 ───────────────────────────────────────────────────
    lackey = player.find_tag('lackey')
    lackey_in_play = any(c.card.tag == 'lackey' for c in player.creatures)
    if lackey and not lackey_in_play and rem >= 1:
        player.remove_from_hand(lackey)
        if not _try_counter_any(player, opponent, gs, lackey, log_entries):
            player.put_creature_in_play(lackey)
            goblin_count += 1
            log_fn("Goblin Lackey (attacks next turn)")
            rem -= 1
        else:
            player.add_to_grave(lackey)
            rem -= 1

    # ── Deploy creatures (Matron, Cratermaker, Warchief, etc.) ──────────────
    # Matron: tutor Muxus on ETB
    matron = player.find_tag('matron')
    if matron and rem >= 3 and not player.find_tag('muxus'):
        player.remove_from_hand(matron)
        if not _try_counter_any(player, opponent, gs, matron, log_entries):
            player.put_creature_in_play(matron)
            goblin_count += 1
            rem -= 3
            # ETB: tutor Muxus from library
            muxus_lib = next((c for c in player.library if c.tag == 'muxus'), None)
            if muxus_lib:
                player.library.remove(muxus_lib)
                player.hand.append(muxus_lib)
                log_fn("Goblin Matron → tutors Muxus!", True)
            else:
                ringleader = next((c for c in player.library if c.tag == 'ringleader'), None)
                if ringleader:
                    player.library.remove(ringleader)
                    player.hand.append(ringleader)
                    log_fn("Goblin Matron → tutors Ringleader", True)
                else:
                    log_fn("Goblin Matron ETB (no target)")
        else:
            player.add_to_grave(matron)
            rem -= 3

    # ── Muxus (the payoff) ─────────────────────────────────────────────────
    muxus = player.find_tag('muxus')
    warchief_discount = 1 if any(c.card.tag == 'warchief' for c in player.creatures) else 0
    muxus_cost = max(1, 6 - warchief_discount)
    if muxus and rem >= muxus_cost:
        player.remove_from_hand(muxus)
        if not _try_counter_any(player, opponent, gs, muxus, log_entries):
            player.put_creature_in_play(muxus)
            goblin_count += 1
            rem -= muxus_cost
            # ETB: reveal top 6, put all Goblins into play (avg ~3 hits)
            hits = 0
            revealed = player.library[:6]
            for card in revealed:
                if card.is_creature() and card.tag in ('lackey', 'matron', 'ringleader',
                    'warchief', 'expert', 'sling', 'cratermaker', 'pashalik',
                    'prospector', 'fury'):
                    player.library.remove(card)
                    perm = player.put_creature_in_play(card)
                    perm.summoning_sick = False  # Warchief gives haste
                    goblin_count += 1
                    hits += 1
            # Munitions Expert ETB from Muxus hits
            if hits > 0:
                expert_perm = next((c for c in player.creatures
                                    if c.card.tag == 'expert'), None)
                if expert_perm:
                    expert_dmg = goblin_count
                    # Kill biggest opponent creature
                    target = max(opponent.creatures, key=lambda c: c.power,
                                 default=None)
                    if target and expert_dmg >= target.toughness:
                        opponent.remove_creature(target)
                        log_fn(f"Munitions Expert deals {expert_dmg} → kills {target.card.name}", True)
            log_fn(f"★ Muxus reveals {hits} Goblins — {goblin_count} total!", True)
        else:
            player.add_to_grave(muxus)
            rem -= muxus_cost

    # ── Vial deploy (flash in creatures at vial_counters CMC) ──────────────
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    vc = getattr(gs, 'vial_counters', 0)
    if vial_on_board and vc > 0:
        vial_target = next((c for c in player.hand
                           if c.is_creature() and c.cmc == vc), None)
        if vial_target:
            player.remove_from_hand(vial_target)
            player.put_creature_in_play(vial_target)
            goblin_count += 1
            log_fn(f"Vial ({vc}) → {vial_target.name}")

    # ── Deploy remaining cheap creatures ────────────────────────────────────
    for tag in ('cratermaker', 'warchief', 'expert', 'prospector'):
        crea = player.find_tag(tag)
        if crea and rem >= crea.cmc:
            player.remove_from_hand(crea)
            if not _try_counter_any(player, opponent, gs, crea, log_entries):
                player.put_creature_in_play(crea)
                goblin_count += 1
                rem -= crea.cmc
                log_fn(f"{crea.name}")
            else:
                player.add_to_grave(crea)
                rem -= crea.cmc

    # ── Fury evoke (free removal) ──────────────────────────────────────────
    fury = player.find_tag('fury')
    if fury and opponent.creatures:
        reds = [c for c in player.hand if 'R' in getattr(c, 'colors', set())
                and c.tag != 'fury']
        if reds:
            player.remove_from_hand(fury)
            player.remove_from_hand(reds[0])
            player.exile.append(reds[0])
            # Deal 4 damage split among creatures
            for target in sorted(opponent.creatures, key=lambda c: c.power,
                                 reverse=True)[:2]:
                if target.toughness <= 2:
                    opponent.remove_creature(target)
                    log_fn(f"Fury evoke → kills {target.card.name}", True)
            player.add_to_grave(fury)

    # ── Sling-Gang drain ──────────────────────────────────────────────────
    sling = next((c for c in player.creatures if c.card.tag == 'sling'), None)
    if sling and opponent.life <= 3 and goblin_count >= 3:
        drain = min(goblin_count - 1, opponent.life)
        opponent.life -= drain
        player.life += drain
        log_fn(f"★ Sling-Gang drains {drain} — opp at {opponent.life}", True)
        if opponent.life <= 0:
            gs.game_over = True
            gs.winner = 'p1' if player is gs.p1 else 'p2'
            gs.win_reason = f"Goblins: Sling-Gang drain for {drain}"
            gs.kill_turn = gs.turn
        gs.check_life_totals()

    # ── Combat ──────────────────────────────────────────────────────────────
    if not gs.game_over:
        attackers = [c for c in player.creatures if not c.summoning_sick]
        # Lackey combat damage trigger: put a Goblin from hand into play
        lackey_atk = next((c for c in attackers if c.card.tag == 'lackey'), None)
        if lackey_atk:
            # Check if lackey would be blocked
            blockers = [c for c in opponent.creatures if not c.summoning_sick]
            lackey_blocked = len(blockers) > 0 and not any(
                c.card.tag == 'lackey' for c in attackers if c is not lackey_atk)
            if not lackey_blocked or len(attackers) > len(blockers):
                # Lackey gets through — put best Goblin from hand
                best = next((c for c in player.hand if c.tag == 'muxus'), None)
                if not best:
                    best = next((c for c in player.hand if c.tag == 'ringleader'), None)
                if not best:
                    best = next((c for c in player.hand if c.is_creature()), None)
                if best:
                    player.remove_from_hand(best)
                    perm = player.put_creature_in_play(best)
                    perm.summoning_sick = False
                    goblin_count += 1
                    log_fn(f"★ Lackey trigger → free {best.name}!", True)
                    # Muxus ETB from Lackey
                    if best.tag == 'muxus':
                        hits = 0
                        revealed = player.library[:6]
                        for card in revealed:
                            if card.is_creature() and card.tag in (
                                'lackey', 'matron', 'ringleader', 'warchief',
                                'expert', 'sling', 'cratermaker', 'pashalik',
                                'prospector'):
                                player.library.remove(card)
                                p2 = player.put_creature_in_play(card)
                                p2.summoning_sick = False
                                goblin_count += 1
                                hits += 1
                        if hits:
                            log_fn(f"★ Muxus from Lackey → {hits} more Goblins!", True)

        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


# ─── Test suite ───────────────────────────────────────────────────────────────

def test_goblins():
    results = []

    # Test 1: Deck size
    deck = make_goblins_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("OK Deck size = 60")

    # Test 2: Key cards
    tags = {c.tag for c in deck}
    for req in ['lackey', 'muxus', 'matron', 'vial', 'cratermaker']:
        assert req in tags, f"Missing: {req}"
    results.append("OK All key cards present")

    # Test 3: Bo3 smoke test
    try:
        from sim import run_any_bo3
        from cards import DECKS
        from sim import STRATEGIES
        DECKS['goblins'] = make_goblins_deck
        STRATEGIES['goblins'] = _strategy_goblins
        r = run_any_bo3('goblins', 'dimir', 10)
        results.append(f"OK Goblins vs Dimir (10 matches): {r['match_wr']*100:.0f}%")
    except Exception as e:
        results.append(f"FAIL Bo3: {e}")

    return results


if __name__ == '__main__':
    print("Running Goblins tests...")
    for r in test_goblins():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_goblins(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    has_t1 = 'lackey' in tags or 'vial' in tags
    threats = sum(1 for c in nonlands if c.is_creature())
    # Lackey/Vial hands keep on 1 land. Otherwise need 2.
    if has_t1: return lc >= 1 and threats >= 1
    if len(hand) <= 5: return lc >= 1 and threats >= 1
    return 1 <= lc <= 4 and threats >= 2

DECK_META = {
    'key':        'goblins',
    'name':       'Goblins',
    'make_deck':  make_goblins_deck,
    'strategy':   _strategy_goblins,
    'keep':       _keep_goblins,
    'categories': {'aggro', 'tribal', 'vial_decks'},
    'interaction': {'speed': 2, 'resilience': 5, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': True, 'opp_threats': 12},
    'meta_share': 0.03,
}
