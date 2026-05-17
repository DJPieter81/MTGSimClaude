"""
Mana Drain Control — UW Drain.dec.

The deck is built around 4 Mana Drains: a UU hard counter that grants the
controller {C} mana equal to the countered spell's mana value at the start
of their next main phase.  Engine wiring lives in:

  * config.py     — `'drain'` listed in `CounterLogic.COUNTER_TAGS`.
  * engine.py     — `try_reactive_counter` has a Drain branch (preferred over
                    Counterspell when both available) that, on a successful
                    counter, adds `spell.cmc` to the defender's `treasure`
                    attr.  The treasure attr is consumed at the start of the
                    next main phase (sim.py:686-695), giving the controller
                    extra colourless mana to spend.

Drain payoffs in the list:
  * Jace, the Mind Sculptor (4 cmc planeswalker — perfect post-drain T3 drop).
  * Sphinx of the Final Word (6 cmc uncounterable hexproof flyer).
  * Emrakul, the Aeons Torn (15 cmc dream finisher — Drain a Show & Tell or
    a Karn for {C}{C}{C}{C} and Emrakul becomes castable a turn earlier).
  * Snapcaster Mage — flashbacks a Drain, STP, or Brainstorm from the yard.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import (creature, instant, sorcery, planeswalker,
                   fetch_land, dual_land, basic_land)


# ─── Deck builder ────────────────────────────────────────────────────────────

def make_mana_drain_deck():
    d = []
    # ── Counters (14) ──
    # Mana Drain — 4 copies, the centrepiece.  Tagged 'drain' so engine.py
    # picks it via try_reactive_counter and stores spell.cmc into treasure.
    d += [instant('Mana Drain', 2, {'U':2}, {'U'}, tag='drain')] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Counterspell', 2, {'U':2}, {'U'}, tag='counter')] * 3
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'},
                  tag='fon', free_cast_if_blue=True)] * 2

    # ── Removal (7) ──
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'},
                  tag='stp', is_removal=True)] * 4
    # Terminus — miracle wrath at {W}.  Critical vs cmc-1/2 aggro (Ocelot,
    # Delver) where the engine's counter gate treats every threat as "minor"
    # and our 14 counter slots otherwise sit dead in hand.  Hardcast cost {6W}
    # also makes Terminus a legitimate drain-mana sink (drain a 6-cmc spell
    # → Terminus free) for the late game.
    d += [sorcery('Terminus', 6, {'W':1,'generic':5}, {'W'},
                  tag='terminus', is_removal=True, is_mass_removal=True)] * 3

    # ── Cantrips (10) ──
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [sorcery('Preordain', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 2

    # ── Threats / drain payoffs (5) ──
    # Cut 1 Snapcaster (marginal under aggro pressure — needs a useful flashback
    # target in yard) and 1 Emrakul (15 cmc never realistically cast).
    d += [creature('Snapcaster Mage', 2, {'U':1,'generic':1}, {'U'},
                   2, 1, tag='snap', flash=True)] * 1
    d += [planeswalker('Jace, the Mind Sculptor', 4, {'U':2,'generic':2}, {'U'},
                       tag='jace', engine=True, draw_trigger=True)] * 3
    d += [creature('Sphinx of the Final Word', 6, {'U':2,'generic':4}, {'U'},
                   5, 5, tag='sphinx', flying=True, indestructible=True,
                   win_condition=True)] * 2

    # ── Lands (24) ──
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 4
    d += [fetch_land('Scalding Tarn',  ['Island','Mountain'])] * 2
    d += [fetch_land('Misty Rainforest',['Forest','Island'])] * 2
    d += [dual_land('Tundra', ['U','W'], ['Island','Plains'])] * 3
    d += [basic_land('Island', 'U', 'Island')] * 8
    d += [basic_land('Plains', 'W', 'Plains')] * 5

    assert len(d) == 60, f"Mana Drain deck: {len(d)}"
    return d


# ─── Strategy ────────────────────────────────────────────────────────────────

def _strategy_mana_drain(player, opponent, gs, total_mana, log_fn, log_entries):
    """Drain Control.

    Reactive counter selection (Mana Drain, FoW, FoN, Counterspell) is handled
    by engine.try_reactive_counter automatically — this function only drives
    proactive plays.  Bonus mana from Drains arrives as treasure (consumed
    at start of main, see sim.py:686-695), so it's already folded into
    `total_mana` by the time this function runs.

    Order of operations:
      1. Swords to Plowshares any creature ≥ 2 power.
      2. Snapcaster Mage flashbacks Mana Drain, STP, or Brainstorm.
      3. Jace, the Mind Sculptor (4 cmc) — primary drain payoff.
      4. Sphinx of the Final Word (6 cmc) — uncounterable finisher.
      5. Emrakul (15 cmc) — only when drain-ramp gets you there.
      6. Cantrips up to 2 per turn.
      7. Combat with anything not summoning-sick.
    """
    from engine import (opp_can_cast, combat_declare, cast_spell, update_goyf,
                        bowmasters_triggers)
    from rules import MTGRules
    from config import MatchupCategory as _MC, CombatThresholds as _CT

    mana_ref = [total_mana]

    def can_cast(card):
        return opp_can_cast(card, mana_ref[0], gs, caster=player)

    # ── 1. Swords to Plowshares — remove biggest threat ──
    # Vs aggro / burn, STP fires on ANY creature ≥ 1 power (Bowmasters,
    # Ocelot Pride, Guide of Souls are all 1/1s that snowball if left
    # unanswered).  Vs fair / combo, STP holds for ≥ 2-power threats.
    p2_deck = getattr(gs, 'p2_deck', '') or getattr(gs, 'matchup', '')
    opp_is_aggro = p2_deck in _MC.AGGRO or p2_deck == 'burn'
    stp_threshold = _CT.STP_THRESHOLD_AGGRO if opp_is_aggro else _CT.STP_THRESHOLD_FAIR
    _mom_protected = getattr(gs, '_mom_protected_tag', None)
    while opponent.creatures and mana_ref[0] >= 1:
        stp = player.find_tag('stp')
        if not stp or not can_cast(stp):
            break
        valid = [c for c in opponent.creatures if c.card.tag != _mom_protected]
        if not valid:
            break
        target = max(valid, key=lambda c: c.power)
        if target.power < stp_threshold:
            break
        def _resolve_stp(c, _t=target):
            player.add_to_grave(c)
            if _t in opponent.creatures:
                lg = MTGRules.stp_life_gain(_t)
                opponent.remove_creature(_t, to_exile=True)
                opponent.life += lg
                log_fn(f"Swords to Plowshares → exiles {_t.card.name}, opp gains {lg}")
                update_goyf(gs)
        cast_spell(player, opponent, gs, stp, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_stp)

    # ── 1b. Terminus (Miracle wrath, {W} cost-override) ──
    # Fires when opp has 2+ creatures (the snowball state — Bowmasters + tokens,
    # Ocelot Pride + copies, multiple Delver/Goblins).  We sweep our own
    # board too (including Jace via summoning sickness on creatures) but
    # mana_drain is creature-light so this is acceptable.
    term = player.find_tag('terminus')
    if term and len(opponent.creatures) >= 2:
        def _resolve_term(c):
            player.add_to_grave(c)
            for cc in list(opponent.creatures):
                opponent.exile.append(cc.card)
                opponent.revolt_this_turn = True
            opponent.creatures.clear()
            for cc in list(player.creatures):
                player.library.append(cc.card)
            player.creatures.clear()
            log_fn("★ Terminus (Miracle {W}) — all creatures to bottom of library",
                   True)
            update_goyf(gs)
        cast_spell(player, opponent, gs, term, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_term, cost_override=1)

    # ── 2. Snapcaster Mage — flashback Drain / STP / Brainstorm ──
    snap = player.find_tag('snap')
    if snap and can_cast(snap):
        drain_fb = next((c for c in player.graveyard if c.tag == 'drain'), None)
        term_fb = (next((c for c in player.graveyard if c.tag == 'terminus'), None)
                   if len(opponent.creatures) >= 2 else None)
        stp_fb = next((c for c in player.graveyard
                       if c.tag == 'stp' and opponent.creatures
                       and max(cc.power for cc in opponent.creatures) >= stp_threshold), None)
        bs_fb = next((c for c in player.graveyard if c.is_cantrip), None)
        fb = drain_fb or term_fb or stp_fb or bs_fb
        if fb:
            def _resolve_snap(c, _fb=fb, _drain=drain_fb, _term=term_fb,
                              _stp=stp_fb, _bs=bs_fb):
                player.put_creature_in_play(c)
                log_fn(f"Snapcaster Mage (2/1) — flashback {_fb.name}")
                if _fb is _drain:
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                elif _fb is _term and opponent.creatures:
                    for cc in list(opponent.creatures):
                        opponent.exile.append(cc.card)
                        opponent.revolt_this_turn = True
                    opponent.creatures.clear()
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    log_fn("  Snapcaster flashback Terminus — board cleared")
                    update_goyf(gs)
                elif _fb is _stp and opponent.creatures:
                    t = max(opponent.creatures, key=lambda cc: cc.power)
                    lg = MTGRules.stp_life_gain(t)
                    opponent.remove_creature(t, to_exile=True); opponent.life += lg
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    log_fn(f"  Snapcaster flashback STP → exiles {t.card.name}")
                    update_goyf(gs)
                elif _fb is _bs:
                    player.graveyard.remove(_fb); player.exile.append(_fb)
                    drawn = player.draw(MTGRules.brainstorm_draws()
                                        if _fb.tag == 'bs' else 1)
                    log_fn(f"  Snapcaster flashback {_fb.name} ({len(drawn)} draw)")
                    bowmasters_triggers(len(drawn), gs, log_entries,
                                        controller='o' if player is gs.p1 else 'b')
            cast_spell(player, opponent, gs, snap, mana_ref, log_fn, log_entries,
                       on_resolve=_resolve_snap)

    # ── 3. Jace, the Mind Sculptor — primary drain payoff at 4 mana ──
    jace = player.find_tag('jace')
    jace_on_board = any(p.card.tag == 'jace' for p in player.planeswalkers)
    if jace and not jace_on_board and can_cast(jace):
        def _resolve_jace(c):
            player.put_planeswalker_in_play(c)
            log_fn("Jace, the Mind Sculptor — draw engine + bounce", True)
            # +0 Brainstorm-style draw on resolution (simplified passive).
            if not getattr(player, '_narset_lock', False):
                drawn = player.draw(1)
                bowmasters_triggers(len(drawn), gs, log_entries,
                                    controller='o' if player is gs.p1 else 'b')
        cast_spell(player, opponent, gs, jace, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_jace)

    # Per-turn Jace +0 (Brainstorm-style): if already on board, draw a card.
    jace_perm = next((p for p in player.planeswalkers
                      if p.card.tag == 'jace' and not p.tapped), None)
    if jace_perm and not getattr(player, '_narset_lock', False):
        jace_perm.tapped = True
        drawn = player.draw(1)
        log_fn(f"Jace +0 (Brainstorm-style): draw {len(drawn)}")
        bowmasters_triggers(len(drawn), gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')

    # ── 4. Sphinx of the Final Word — 6 cmc uncounterable finisher ──
    sphinx = player.find_tag('sphinx')
    sphinx_on_board = any(c.card.tag == 'sphinx' for c in player.creatures)
    if sphinx and not sphinx_on_board and can_cast(sphinx):
        def _resolve_sphinx(c):
            player.put_creature_in_play(c)
            log_fn("★ Sphinx of the Final Word (5/5 flying, uncounterable)", True)
            update_goyf(gs)
        cast_spell(player, opponent, gs, sphinx, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_sphinx)

    # ── 5. Emrakul, the Aeons Torn — 15 cmc dream finisher ──
    emrakul = player.find_tag('emrakul')
    if emrakul and mana_ref[0] >= emrakul.cmc:
        def _resolve_emrakul(c):
            player.put_creature_in_play(c)
            log_fn("★★★ Emrakul, the Aeons Torn (15/15 flying trample haste)", True)
            update_goyf(gs)
        cast_spell(player, opponent, gs, emrakul, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_emrakul)

    # ── 6. Cantrips — up to 2 per turn ──
    for _ in range(2):
        if mana_ref[0] < 1:
            break
        cant = next((c for c in player.hand if c.is_cantrip and can_cast(c)), None)
        if not cant:
            break
        def _resolve_cant(c):
            draws = MTGRules.brainstorm_draws() if c.tag == 'bs' else 1
            player.add_to_grave(c)
            drawn = player.draw(draws)
            log_fn(f"{c.name} ({len(drawn)} draw{'s' if len(drawn) > 1 else ''})")
            bowmasters_triggers(len(drawn), gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
        cast_spell(player, opponent, gs, cant, mana_ref, log_fn, log_entries,
                   on_resolve=_resolve_cant)

    # ── 7. Combat ──
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


# ─── Mulligan ────────────────────────────────────────────────────────────────

def _keep_mana_drain(hand, matchup=''):
    """Mana Drain keep — values lands + cantrips + at least one counter or
    removal.  A Drain in opener is gravy but not required (4-of, ~32% in 7)."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
    counters = sum(1 for c in nonlands
                   if c.tag in ('drain', 'fow', 'fon', 'counter', 'daze', 'fluster'))
    removal = sum(1 for c in nonlands if c.tag in ('stp', 'terminus'))
    threats = sum(1 for c in nonlands
                  if c.tag in ('jace', 'sphinx', 'snap'))
    action = cantrips + counters + removal + threats

    if lc < 2 or lc > 5:
        return False
    if action == 0:
        return False
    if lc <= 3:
        return action >= 1
    # 4-5 lands: need ≥ 2 action cards
    return action >= 2


# ─── DECK_META ───────────────────────────────────────────────────────────────

DECK_META = {
    'key':        'mana_drain',
    'name':       'Mana Drain Control',
    'make_deck':  make_mana_drain_deck,
    'strategy':   _strategy_mana_drain,
    'keep':       _keep_mana_drain,
    'categories': {'control'},
    'interaction': {'speed': 5, 'resilience': 5, 'uses_graveyard': False,
                    'uses_veil': False, 'soft_to_wasteland': False,
                    'creature_based': False},
    'meta_share': 0.02,
}
