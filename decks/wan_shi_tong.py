"""
Wan Shi Tong Control — UW Chalice Control for Legacy.
Adapted from Modern UW Control shell with full Legacy conversion.
Key: Chalice on 1 + wraths + counters + Wan Shi Tong as card advantage engine.
No Brainstorm/Ponder (anti-synergy with own Chalice on 1).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import (creature, instant, sorcery, artifact, planeswalker,
                   fetch_land, dual_land, basic_land, utility_land)


def make_wst_deck():
    d = []
    # Creatures (10)
    d += [creature('Wan Shi Tong, Librarian', 4, {'W':1,'U':1,'generic':2}, {'W','U'}, 3, 5,
                   tag='wst', engine=True, flying=True)] * 4
    # Sanctifier en-Vec (4 — was 3, originally 2).  Real Bo1 Wan Shi Tong
    # runs 3-4 main; 4 is the canonical hate density for Burn-heavy metas.
    # At 4 copies the deck draws one in opener ~40% of the time (vs ~32% at
    # 3, ~22% at 2).  The card is already wired via `pro_red=True` and
    # burn's deal_face_damage checks for opponent-side pro_red creatures.
    d += [creature('Sanctifier en-Vec', 2, {'W':1,'generic':1}, {'W'}, 2, 2,
                   tag='sanctifier', pro_red=True)] * 4
    d += [creature('Snapcaster Mage', 2, {'U':1,'generic':1}, {'U'}, 2, 1,
                   tag='snap', flash=True)] * 2
    # Lock piece (4)
    d += [artifact('Chalice of the Void', 0, {}, tag='chalice', lock_piece=True,
                   is_combo_piece=True)] * 4
    # Removal (8)
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp',
                  is_removal=True)] * 4
    d += [instant('March of Otherworldly Light', 1, {'W':1}, {'W'}, tag='march',
                  is_removal=True)] * 4
    # Wraths (5)
    d += [sorcery('Wrath of the Skies', 2, {'W':1,'generic':1}, {'W'}, tag='wrath',
                  is_removal=True, is_mass_removal=True)] * 3
    d += [sorcery('Supreme Verdict', 4, {'W':2,'U':1,'generic':1}, {'W','U'}, tag='verdict',
                  is_removal=True, is_mass_removal=True)] * 2
    # Counters (8 — trimmed 1 Counterspell to fit 4th Sanctifier).
    # Counterspell at 2UU is the lowest-leverage counter in the list vs an
    # all-instant aggro deck; FoW/FoN/Veto remain at full counts.
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow',
                  free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                  free_cast_if_blue=True)] * 1
    d += [instant('Counterspell', 2, {'U':2}, {'U'}, tag='counter')] * 1
    d += [instant("Dovin's Veto", 2, {'W':1,'U':1}, {'W','U'}, tag='veto')] * 1
    # Planeswalker (3)
    d += [planeswalker('Teferi, Time Raveler', 3, {'W':1,'U':1,'generic':1}, {'W','U'},
                       tag='teferi', engine=True)] * 3
    # Lands (23)
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 4
    d += [fetch_land('Marsh Flats', ['Swamp','Plains'])] * 4
    d += [dual_land('Tundra', ['U','W'], ['Island','Plains'])] * 3
    d += [basic_land('Island', 'U', 'Island')] * 2
    d += [basic_land('Plains', 'W', 'Plains')] * 2
    d += [dual_land('Plateau', ['R','W'], ['Mountain','Plains'])] * 1
    d += [utility_land('Karakas', ['W'], 'karakas')] * 1
    # Wasteland bumped 1 → 3 to disrupt nonbasic-heavy manabases
    # (Cloudpost, Lands, Dimir Bayou/Underground Sea). Real Legacy WST
    # Control lists run 3-4. See docs/audits/wan_shi_tong_vs_cloudpost.md.
    d += [utility_land('Wasteland', ['C'], 'wl')] * 3
    d += [utility_land('Meticulous Archive', ['W','U'], 'archive')] * 1
    d += [utility_land('Ancient Tomb', ['C','C'], 'tomb', mana_ritual=True)] * 1
    d += [utility_land('Mystic Sanctuary', ['U'], 'sanctuary')] * 1
    assert len(d) == 60, f"WST deck: {len(d)}"
    return d


def _strategy_wst(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Wan Shi Tong Control — UW Chalice Control.
    Priority: Chalice on 1 → removal → wraths → Teferi → WST → counters → combat.
    """
    from engine import (combat_declare, update_goyf, _resolve_lock,
                        MTGRules, cast_spell)

    budget = [total_mana]

    # ── 1. Chalice of the Void on 1 — T1 priority ──
    # CR 113.6 — Chalice@1 counters every CMC-1 spell on cast, including
    # the controller's own. Two layered gates:
    #
    # (a) Matchup gate (`opp_is_cantrip_combo`): vs combo decks whose
    #     engine spell is CMC-1 (storm cantrips, doomsday cantrips, oops
    #     petals/probe, cephalid Brainstorm/Ponder), Chalice@1 is high-EV
    #     and locking out own STP/March is acceptable collateral.
    # (b) Library-drained gate (`library_safe`): vs everything else,
    #     require most of the controller's own CMC-1 pool to be already
    #     drawn before firing — otherwise the bug from
    #     docs/audits/wan_shi_tong_vs_dnt.md / mono_black.md occurs (turn-1
    #     Chalice locks out 4 STP + 4 March still in library).
    opp_deck = gs.p2_deck if player is gs.p1 else gs.p1_deck
    # Cantrip-combo subset of MC.COMBO — these decks rely on CMC-1 spells
    # (Brainstorm, Ponder, Petal, Probe, Ritual etc.) for engine velocity.
    # Decks like show/sneak land their payoff at CMC ≥ 3, so they're in
    # MC.COMBO but not cantrip-engine-driven.
    _cantrip_combo_keys = frozenset({
        'storm', 'tes', 'doomsday', 'oops', 'cephalid', 'belcher',
    })
    opp_is_cantrip_combo = opp_deck in _cantrip_combo_keys

    ch = player.find_tag('chalice')
    own_cmc1_hand = sum(1 for c in player.hand
                        if c is not ch and not c.is_land() and c.cmc == 1)
    own_cmc1_lib = sum(1 for c in player.library
                       if not c.is_land() and c.cmc == 1)
    # Threshold derived from deck composition: WST runs 8 CMC-1 spells
    # (4 STP + 4 March). The lock is positive-EV only when most of the
    # pool is already spent / drawn (≥6 of 8).
    LATE_GAME_CMC1_REMAINING = 2
    library_safe = own_cmc1_lib <= LATE_GAME_CMC1_REMAINING
    gate_ok = opp_is_cantrip_combo or library_safe
    if (ch and gs.chalice_x is None and budget[0] >= 2
            and own_cmc1_hand == 0 and gate_ok):
        def _resolve_ch(c):
            player.put_artifact_in_play(c)
            _resolve_lock(gs, c, log_fn)
        cast_spell(player, opponent, gs, ch, budget, log_fn, log_entries,
                   on_resolve=_resolve_ch, cost_override=2)

    # ── 2. Swords to Plowshares — remove biggest threat ──
    stp = player.find_tag('stp')
    if stp and opponent.creatures and budget[0] >= 1:
        target = max(opponent.creatures, key=lambda c: c.power + c.toughness)
        if target.power >= 2:
            def _resolve_stp(c, _t=target):
                player.add_to_grave(c)
                if _t in opponent.creatures:
                    lg = MTGRules.stp_life_gain(_t)
                    opponent.remove_creature(_t, to_exile=True)
                    opponent.life += lg
                    log_fn(f"Swords to Plowshares → exiles {_t.card.name}")
                    update_goyf(gs)
            cast_spell(player, opponent, gs, stp, budget, log_fn, log_entries,
                       on_resolve=_resolve_stp)

    # March of Otherworldly Light — exile removal
    march = player.find_tag('march')
    if march and opponent.creatures and budget[0] >= 2:
        target = max(opponent.creatures, key=lambda c: c.power + c.toughness)
        if target.power >= 2:
            def _resolve_march(c, _t=target):
                player.add_to_grave(c)
                if _t in opponent.creatures:
                    opponent.remove_creature(_t, to_exile=True)
                    log_fn(f"March of Otherworldly Light → exiles {_t.card.name}")
                    update_goyf(gs)
            cast_spell(player, opponent, gs, march, budget, log_fn, log_entries,
                       on_resolve=_resolve_march, cost_override=2)

    # ── 3. Wraths — clear board when opponent has 2+ creatures ──
    opp_threat = sum(c.power for c in opponent.creatures)
    wst_on_board = any(c.card.tag == 'wst' for c in player.creatures)

    if len(opponent.creatures) >= 2 and (not wst_on_board or opp_threat >= player.life):
        wrath = player.find_tag('verdict') or player.find_tag('wrath')
        if wrath and budget[0] >= wrath.cmc:
            def _resolve_wrath(c):
                player.add_to_grave(c)
                for cc in list(opponent.creatures):
                    opponent.add_to_grave(cc.card); opponent.revolt_this_turn = True
                opponent.creatures.clear()
                for cc in list(player.creatures):
                    player.add_to_grave(cc.card)
                player.creatures.clear()
                log_fn(f"★ {c.name} — all creatures destroyed", True)
                update_goyf(gs)
            cast_spell(player, opponent, gs, wrath, budget, log_fn, log_entries,
                       on_resolve=_resolve_wrath)

    # ── 4. Teferi, Time Raveler ──
    teferi = player.find_tag('teferi')
    teferi_on_board = any(p.card.tag == 'teferi' for p in player.artifacts)
    if teferi and not teferi_on_board and budget[0] >= 3:
        def _resolve_teferi(c):
            player.put_artifact_in_play(c)
            if opponent.creatures:
                tgt = max(opponent.creatures, key=lambda cc: cc.power)
                opponent.remove_creature(tgt)
                opponent.hand.append(tgt.card)
                log_fn(f"Teferi, Time Raveler — bounces {tgt.card.name}, draw 1", True)
            else:
                log_fn("Teferi, Time Raveler — opponent can't cast at instant speed", True)
            player.draw(1)
        cast_spell(player, opponent, gs, teferi, budget, log_fn, log_entries,
                   on_resolve=_resolve_teferi, cost_override=3)

    # ── 5. Wan Shi Tong — deploy the engine ──
    wst = player.find_tag('wst')
    if wst and not wst_on_board and budget[0] >= 4:
        def _resolve_wst(c):
            player.put_creature_in_play(c)
            log_fn("★ Wan Shi Tong, Librarian (3/5 flying) — draws on each opponent draw", True)
        cast_spell(player, opponent, gs, wst, budget, log_fn, log_entries,
                   on_resolve=_resolve_wst, cost_override=4)

    # ── 5b. Karakas — bounce opponent's legendary creatures ──
    # CR 109.3 + audit (docs/audits/wan_shi_tong_vs_dnt.md): WST runs 1
    # Karakas; the existing _strategy_dnt Karakas block only targets
    # Murktide. WST needs its own bounce block for Thalia and any other
    # tag in the shared `LEGENDARY_CREATURE_TAGS` set.
    from game import LEGENDARY_CREATURE_TAGS as _LEGEND_TAGS
    karakas = next((l for l in player.lands
                    if l.card.tag == 'karakas' and not l.tapped), None)
    if karakas and opponent.creatures:
        legend = next((c for c in opponent.creatures
                       if c.card.tag in _LEGEND_TAGS), None)
        if legend is not None:
            karakas.tapped = True
            opponent.creatures.remove(legend)
            opponent.hand.append(legend.card)
            log_fn(f"★ Karakas → returns {legend.card.name}", True)
            gs.strat_log.log_disruption(
                gs.turn, gs, player, 'remove',
                legend.card.tag or 'creature', 'karakas',
                reason=f'karakas bounces {legend.card.tag or "legendary"}')

    # ── 6. Sanctifier en-Vec ──
    sanc = player.find_tag('sanctifier')
    if sanc and budget[0] >= 2:
        def _resolve_sanc(c):
            player.put_creature_in_play(c)
            log_fn("Sanctifier en-Vec (2/2, pro black/red)")
        cast_spell(player, opponent, gs, sanc, budget, log_fn, log_entries,
                   on_resolve=_resolve_sanc, cost_override=2)

    # ── 7. Snapcaster Mage — flashback value ──
    snap = player.find_tag('snap')
    if snap and budget[0] >= 2:
        fb_target = next((c for c in player.graveyard
                          if c.is_removal and not c.is_mass_removal and opponent.creatures), None)
        if fb_target:
            def _resolve_snap(c, _fb=fb_target):
                player.put_creature_in_play(c)
                if opponent.creatures:
                    tgt = max(opponent.creatures, key=lambda cc: cc.power)
                    if tgt.power >= 2:
                        lg = MTGRules.stp_life_gain(tgt)
                        opponent.remove_creature(tgt, to_exile=True)
                        opponent.life += lg
                        if _fb in player.graveyard:
                            player.graveyard.remove(_fb)
                        log_fn(f"Snapcaster Mage — flashback {_fb.name} → exiles {tgt.card.name}")
                        update_goyf(gs)
            cast_spell(player, opponent, gs, snap, budget, log_fn, log_entries,
                       on_resolve=_resolve_snap, cost_override=2)

    # ── 8. Combat — attack with non-summoning-sick creatures ──
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


def _keep_wst(hand, matchup=''):
    lands = sum(1 for c in hand if c.is_land())
    counters = sum(1 for c in hand if c.tag in ('fow', 'fon', 'counter', 'veto'))
    removal = sum(1 for c in hand if c.is_removal)
    chalice = sum(1 for c in hand if c.tag == 'chalice')
    action = counters + removal + chalice
    return 2 <= lands <= 4 and action >= 1


DECK_META = {
    'key':        'wan_shi_tong',
    'name':       'Wan Shi Tong Control',
    'make_deck':  make_wst_deck,
    'strategy':   _strategy_wst,
    'keep':       _keep_wst,
    'categories': {'control', 'prison'},
    'meta_share': 0.02,
}
