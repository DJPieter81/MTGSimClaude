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
from combo_engine import TribalPath


# Tag set used as the "Goblin tribe" filter for the Lackey-style cheat trigger.
# Lives in the deck plugin (not engine), per the ABSTRACTION CONTRACT —
# tribe membership is deck-private knowledge expressed as tag strings.
GOBLIN_TRIBE_TAGS = frozenset({
    'lackey', 'matron', 'ringleader', 'warchief', 'expert', 'sling',
    'cratermaker', 'pashalik', 'prospector', 'fury', 'muxus',
})


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
                          tag='fury', haste=True, trample=True))

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

    # Bloodstained Mire (fetch) — searches for Swamp or Mountain
    for _ in range(2):
        c = Card('Bloodstained Mire', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land',
                 fetch_targets={'Swamp', 'Mountain'})
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # Wooded Foothills (fetch) — searches for Mountain or Forest
    for _ in range(2):
        c = Card('Wooded Foothills', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land',
                 fetch_targets={'Mountain', 'Forest'})
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # Mountain (basic)
    for _ in range(2):
        c = Card('Mountain', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='basic', produces={'R'}, gy_type='land',
                 is_basic=True, subtypes={'Mountain'})
        d.append(c)

    # Swamp (basic)
    for _ in range(2):
        c = Card('Swamp', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='basic', produces={'B'}, gy_type='land',
                 is_basic=True, subtypes={'Swamp'})
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
    from engine import _try_counter_any, bowmasters_triggers, combat_declare, cast_spell

    rem = total_mana
    goblin_count = len(player.creatures)

    # ── Aether Vial T1-T2 ──────────────────────────────────────────────────
    vial = player.find_tag('vial')
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial and not vial_on_board and rem >= 1 and gs.turn <= 3:
        _b = [rem]
        def _resolve_vial(c):
            player.put_artifact_in_play(c)
            gs.vial_counters = 0
            gs._vial_entered_last_turn = True
            log_fn("Aether Vial enters play")
        cast_spell(player, opponent, gs, vial, _b, log_fn, log_entries,
                   on_resolve=_resolve_vial, cost_override=1)
        rem = _b[0]

    # ── Vial tick (upkeep) ──────────────────────────────────────────────────
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial_on_board and not getattr(gs, '_vial_entered_last_turn', False):
        gs.vial_counters = getattr(gs, 'vial_counters', 0) + 1
        if gs.vial_counters <= 6:
            log_fn(f"Vial ticks to {gs.vial_counters}")
    gs._vial_entered_last_turn = False

    # ── Thoughtseize T1-T2 (if no Lackey/Vial) ─────────────────────────────
    # Cast BEFORE Chrome Mox so TS isn't pitched as Mox fuel. Goblins
    # prefers Lackey on T1 (faster clock); TS fires when no Lackey and
    # mana is available. Pre-restructure the shared preamble cast TS
    # before strategy dispatch; this branch preserves that ordering.
    ts = player.find_tag('ts')
    if ts and rem >= 1 and gs.turn <= 2 and not player.find_tag('lackey'):
        _b = [rem]
        def _resolve_ts(c):
            player.add_to_grave(c)
            player.life -= 2
            target = (opponent.find_any(lambda cc: cc.free_cast_if_blue) or
                      opponent.find_any(lambda cc: cc.is_creature()) or
                      next((cc for cc in opponent.hand if not cc.is_land()), None))
            if target:
                opponent.hand.remove(target)
                opponent.add_to_grave(target)
                gs.strat_log.log_disruption(
                    gs.turn, gs, player, 'discard',
                    target.tag or 'card', 'ts',
                    reason=f'TS strips {target.tag} from opponent')
                log_fn(f"Thoughtseize strips {target.name}", True)
        cast_spell(player, opponent, gs, ts, _b, log_fn, log_entries,
                   on_resolve=_resolve_ts, cost_override=1)
        rem = _b[0]

    # ── Chrome Mox for fast mana ────────────────────────────────────────────
    mox = player.find_tag('chrome_mox')
    if mox and not any(p.card.tag == 'chrome_mox' for p in player.artifacts):
        # Mox needs a colored pitch. Goblins protects its tutors (matron,
        # ringleader, recruiter), Vial enabler, and finishers (muxus, sling)
        # from being exiled — picking them was the documented audit bug
        # (docs/audits/goblins_vs_burn.md).
        from engine import select_pitch_target
        _gob_protected = frozenset({'chrome_mox', 'muxus', 'lackey', 'matron',
                                    'ringleader', 'recruiter', 'sling',
                                    'warchief', 'pashalik'})
        pitch = (select_pitch_target(player.hand, 'R', mox, _gob_protected)
                 or select_pitch_target(player.hand, 'B', mox, _gob_protected))
        if pitch:
            player.remove_from_hand(mox)
            player.put_artifact_in_play(mox)
            player.remove_from_hand(pitch)
            player.exile.append(pitch)
            rem += 1
            log_fn(f"Chrome Mox (exile {pitch.name}) → +1 mana")

    # ── Goblin Lackey T1 ───────────────────────────────────────────────────
    lackey = player.find_tag('lackey')
    lackey_in_play = any(c.card.tag == 'lackey' for c in player.creatures)
    if lackey and not lackey_in_play and rem >= 1:
        _b = [rem]
        def _resolve_lackey(c):
            perm = player.put_creature_in_play(c)
            # Mark the Lackey-class trigger so the engine can find it generically.
            # (See rules.Permanent.cheat_on_combat_damage docstring.)
            if perm is not None:
                perm.cheat_on_combat_damage = True
            log_fn("Goblin Lackey (attacks next turn)")
        if cast_spell(player, opponent, gs, lackey, _b, log_fn, log_entries,
                      on_resolve=_resolve_lackey, cost_override=1):
            goblin_count += 1
        rem = _b[0]

    # ── Deploy creatures (Matron, Cratermaker, Warchief, etc.) ──────────────
    # Matron: tutor Muxus on ETB
    matron = player.find_tag('matron')
    if matron and rem >= 3 and not player.find_tag('muxus'):
        _b = [rem]
        def _resolve_matron(c):
            player.put_creature_in_play(c)
            muxus_lib = next((cc for cc in player.library if cc.tag == 'muxus'), None)
            if muxus_lib:
                player.library.remove(muxus_lib)
                player.hand.append(muxus_lib)
                log_fn("Goblin Matron → tutors Muxus!", True)
            else:
                ringleader = next((cc for cc in player.library if cc.tag == 'ringleader'), None)
                if ringleader:
                    player.library.remove(ringleader)
                    player.hand.append(ringleader)
                    log_fn("Goblin Matron → tutors Ringleader", True)
                else:
                    log_fn("Goblin Matron ETB (no target)")
        if cast_spell(player, opponent, gs, matron, _b, log_fn, log_entries,
                      on_resolve=_resolve_matron, cost_override=3):
            goblin_count += 1
        rem = _b[0]

    # ── Muxus (the payoff) ─────────────────────────────────────────────────
    muxus = player.find_tag('muxus')
    warchief_discount = 1 if any(c.card.tag == 'warchief' for c in player.creatures) else 0
    muxus_cost = max(1, 6 - warchief_discount)
    if muxus and rem >= muxus_cost:
        _b = [rem]
        def _resolve_muxus(c, _mc=muxus_cost):
            nonlocal goblin_count
            player.put_creature_in_play(c)
            goblin_count += 1
            hits = 0
            revealed = player.library[:6]
            for card in revealed:
                if card.is_creature() and card.tag in ('lackey', 'matron', 'ringleader',
                    'warchief', 'expert', 'sling', 'cratermaker', 'pashalik',
                    'prospector', 'fury'):
                    player.library.remove(card)
                    perm = player.put_creature_in_play(card)
                    perm.summoning_sick = False
                    goblin_count += 1
                    hits += 1
            if hits > 0:
                expert_perm = next((cc for cc in player.creatures
                                    if cc.card.tag == 'expert'), None)
                if expert_perm:
                    expert_dmg = goblin_count
                    target = max(opponent.creatures, key=lambda cc: cc.power, default=None)
                    if target and expert_dmg >= target.toughness:
                        opponent.remove_creature(target)
                        log_fn(f"Munitions Expert deals {expert_dmg} → kills {target.card.name}", True)
            log_fn(f"★ Muxus reveals {hits} Goblins — {goblin_count} total!", True)
        cast_spell(player, opponent, gs, muxus, _b, log_fn, log_entries,
                   on_resolve=_resolve_muxus, cost_override=muxus_cost)
        rem = _b[0]

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

    # ── Deploy remaining creatures (cheap → mid → big) ────────────────────
    # Ringleader (CMC 4): hard-cast for value; reveals top 4, all goblins to
    # hand. Critical engine card — was missing from this loop, so Ringleader
    # sat in hand all game vs aggro matchups (goblins vs burn 8.5 % at iter
    # 10 confirms catastrophic outcome).
    # Pashalik Mons (CMC 3 zombie): also a goblin, attacks/blocks.
    for tag in ('cratermaker', 'warchief', 'expert', 'prospector',
                'pashalik', 'sling', 'ringleader'):
        crea = player.find_tag(tag)
        if crea and rem >= crea.cmc:
            _b = [rem]
            def _resolve_crea(c):
                player.put_creature_in_play(c)
                log_fn(f"{c.name}")
                # Ringleader ETB: reveal top 4, take all goblins to hand
                if c.tag == 'ringleader':
                    GOB_TAGS = {'lackey', 'matron', 'ringleader', 'warchief',
                                'expert', 'sling', 'cratermaker', 'pashalik',
                                'prospector', 'fury', 'muxus'}
                    revealed = player.library[:4]
                    taken = []
                    for card in revealed:
                        if card.is_creature() and card.tag in GOB_TAGS:
                            player.library.remove(card)
                            player.hand.append(card)
                            taken.append(card.name)
                    if taken:
                        log_fn(f"  Ringleader reveals → takes {', '.join(taken)}", True)
            if cast_spell(player, opponent, gs, crea, _b, log_fn, log_entries,
                          on_resolve=_resolve_crea):
                goblin_count += 1
            rem = _b[0]

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
        # ── Cheat-on-combat-damage triggers (CR 603) ────────────────────────
        # Generic across any Permanent.cheat_on_combat_damage attacker. For
        # each such attacker that connects, pick the highest-CMC matching-
        # tribe creature from hand using Card.cmc (property comparison, not
        # name matching). The "tribe" is deck-private — Goblins uses
        # GOBLIN_TRIBE_TAGS at the top of this module.
        blockers = [c for c in opponent.creatures if not c.summoning_sick]
        unblocked_slots = max(0, len(attackers) - len(blockers))
        cheat_attackers = [c for c in attackers if getattr(c, 'cheat_on_combat_damage', False)]
        # Each cheat attacker that lands in an unblocked slot triggers once.
        cheat_triggers = min(len(cheat_attackers), unblocked_slots)
        for _ in range(cheat_triggers):
            tribe_in_hand = [c for c in player.hand
                             if c.is_creature() and c.tag in GOBLIN_TRIBE_TAGS]
            if not tribe_in_hand:
                break
            # Pick the highest-Card.cmc piece (property comparison — rule-level,
            # no card-name == anywhere). Ties broken by name for determinism.
            best = max(tribe_in_hand, key=lambda c: (c.cmc, c.name))
            candidates = [f"{c.name}(cmc={c.cmc})" for c in tribe_in_hand]
            n_attackers = len(attackers)
            gs.strat_log.log_decision(
                gs.turn, 'goblins',
                candidates=candidates,
                chosen=f'attack with {n_attackers} goblins',
                reason=f'lackey trigger cheats {best.tag}',
                phase='combat',
            )
            player.remove_from_hand(best)
            perm = player.put_creature_in_play(best)
            perm.summoning_sick = False
            goblin_count += 1
            log_fn(f"★ Cheat-on-combat-damage → free {best.name}!", True)
            # Cascade: if the cheated piece was Muxus, fire its ETB now.
            if best.tag == 'muxus':
                hits = 0
                revealed = player.library[:6]
                for card in revealed:
                    if card.is_creature() and card.tag in GOBLIN_TRIBE_TAGS - {'muxus'}:
                        player.library.remove(card)
                        p2 = player.put_creature_in_play(card)
                        p2.summoning_sick = False
                        goblin_count += 1
                        hits += 1
                if hits:
                    log_fn(f"★ Muxus from cheat trigger → {hits} more Goblins!", True)

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
    'meta_share': 0.01,
    # ── Combo metadata (consumed by combo_engine.py) ─────────────────────────
    # Goblins is aggro-with-combo-finish: Lackey/Vial cheat → Muxus ETB →
    # board-flood. Declaring combo metadata lets the heuristic grader key on
    # the 'attack' / 'lackey' decision lines emitted in combat. See
    # docs/design/2026-05-09_combo_engine_architecture.md.
    'combo': {
        'pieces': frozenset({
            'lackey', 'vial',                                  # cheat enablers
            'muxus', 'matron', 'ringleader', 'warchief',       # payoffs / engine
            'expert', 'sling', 'cratermaker', 'pashalik',
            'prospector', 'fury',
        }),
        'protection_tags': frozenset({'cavern'}),  # uncounterable creatures
        'assembly_paths': (
            # Lackey-cheat line: Lackey ({R}) + any tribe piece in hand →
            # combat damage triggers free play. Mana_cost=1 = Lackey itself.
            # Phase B2 migrated to TribalPath: `cheat_enabler_tag` names
            # the Lackey-class trigger, `tribe_tags` lists the payoffs
            # reachable via the cheat.
            TribalPath(
                tag='lackey_cheat_muxus',
                required_tags=frozenset({'lackey'}),
                mana_cost=1,
                turns_to_kill=2,    # T1 Lackey → T2 attack triggers
                target_tags=frozenset({'muxus', 'ringleader', 'matron'}),
                tribe_tags=frozenset({'muxus', 'ringleader', 'matron'}),
                cheat_enabler_tag='lackey',
            ),
            # Hard-cast Muxus line: 6 mana for direct cast. No cheat
            # enabler — `cheat_enabler_tag=''` falls back to the base
            # `required_tags` check.
            TribalPath(
                tag='hardcast_muxus',
                required_tags=frozenset({'muxus'}),
                mana_cost=6,
                turns_to_kill=1,
                tribe_tags=frozenset(),
                cheat_enabler_tag='',
            ),
        ),
    },
}
