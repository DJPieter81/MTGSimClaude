"""
TES (The Epic Storm) — Legacy fast Storm variant.

vs ANT differences:
- Chrome Mox: exile a non-artifact, non-land card from hand, add 1 mana of its color (fast mana)
- Burning Wish: sorcery, tutor any sorcery from sideboard into hand
- Rite of Flame: {R}, add {R}{R}{R} if 2+ Rites in GY, else {R}{R} — storm count builder
- Echo of Eons: {3}{U}{U} or flashback from GY by discarding Lion's Eye Diamond
- Lion's Eye Diamond: {0}, sacrifice it BEFORE using the mana: add {R}{R}{R}, {G}{G}{G}, or {B}{B}{B}
  — key interaction: LED can be cracked in response to your OWN Burning Wish to pay for the Wish's result
- Empty the Warrens: alternate win — create 2 Goblin tokens per storm count
- Veil of Summer: protects from blue/black disruption (key: cast BEFORE Tendrils)

T1 kill line:
  LED + Mox + Burning Wish → sideboard Tendrils → crack LED for BBB → Tendrils

T1 pass line (opponent goes first):
  Same but with more setup time
"""

import sys
sys.path.insert(0, '/home/claude/mtg_sim')

import random
from cards import instant, sorcery, creature, artifact

# ─── Deck construction ────────────────────────────────────────────────────────

def make_tes_deck():
    d = []

    # ── Lands (14) ────────────────────────────────────────────────────────────
    from rules import Card, CardType
    # Volcanic Island: U/R dual
    for _ in range(4):
        c = Card('Volcanic Island', CardType.LAND, cmc=0, mana_cost={},
                 colors={'U','R'}, tag='dual', produces={'U','R'}, gy_type='land')
        d.append(c)
    # Underground Sea: U/B dual
    for _ in range(4):
        c = Card('Underground Sea', CardType.LAND, cmc=0, mana_cost={},
                 colors={'U','B'}, tag='dual', produces={'U','B'}, gy_type='land')
        d.append(c)
    # Scalding Tarn / Polluted Delta (fetches)
    for _ in range(6):
        c = Card('Scalding Tarn', CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), tag='fetch', gy_type='land')
        c.is_fetch = True
        c.produces = set()
        d.append(c)

    # ── Fast Mana (16) ────────────────────────────────────────────────────────
    # Lion's Eye Diamond: {0}, sac → {R}{R}{R}/{G}{G}{G}/{B}{B}{B}, discard hand
    for _ in range(4):
        c = artifact("Lion's Eye Diamond", 0, {}, tag='led', is_combo_piece=True)
        c.led = True
        d.append(c)

    # Chrome Mox: exile nonartifact nonland → add 1 mana of its color
    for _ in range(4):
        c = artifact('Chrome Mox', 0, {}, tag='chrome_mox', is_combo_piece=True)
        c.chrome_mox = True
        d.append(c)

    # Lotus Petal: exile → add any color
    for _ in range(4):
        d.append(artifact('Lotus Petal', 0, {}, tag='petal'))

    # Dark Ritual: {B} → {B}{B}{B}
    for _ in range(4):
        d.append(sorcery('Dark Ritual', 1, {'B':1}, {'B'}, tag='darkrit'))

    # ── Storm Engine (16) ─────────────────────────────────────────────────────
    # Burning Wish: {1R} tutor sorcery from SB
    for _ in range(4):
        d.append(sorcery('Burning Wish', 2, {'R':1,'generic':1}, {'R'},
                         tag='burning_wish', is_combo_piece=True))

    # Echo of Eons: {3UU} or flashback by discarding LED
    for _ in range(3):
        c = sorcery('Echo of Eons', 5, {'U':2,'generic':3}, {'U'},
                    tag='echo', is_combo_piece=True)
        c.has_flashback = True
        d.append(c)

    # Brainstorm: cantrip
    for _ in range(4):
        d.append(instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True))

    # Ponder: cantrip
    for _ in range(2):
        d.append(sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True))

    # Ad Nauseam: draw cards until you hit CMC you can't pay
    for _ in range(1):
        d.append(instant('Ad Nauseam', 5, {'B':2,'generic':3}, {'B'},
                         tag='adnaus', is_combo_piece=True))

    # Tendrils of Agony: storm win condition
    for _ in range(2):
        d.append(sorcery('Tendrils of Agony', 4, {'B':2,'generic':2}, {'B'},
                         tag='tendrils', win_condition=True, is_combo_piece=True))

    # ── Protection (8) ───────────────────────────────────────────────────────
    # Veil of Summer: {G}, can't be countered, protects your spells
    for _ in range(4):
        d.append(instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos',
                         is_removal=True))  # is_removal used as 'disruptive' flag

    # Force of Will
    for _ in range(4):
        d.append(instant('Force of Will', 5, {'U':1,'generic':4}, {'U'},
                         tag='fow', free_cast_if_blue=True))

    # ── Tutor (6) ────────────────────────────────────────────────────────────
    # Infernal Tutor: {1B}, hellbent → tutor any card; else tutor copy of card in hand
    for _ in range(4):
        d.append(sorcery('Infernal Tutor', 2, {'B':1,'generic':1}, {'B'},
                         tag='infernal', is_combo_piece=True))

    # Gitaxian Probe: 2 life, look at opp hand, draw 1
    for _ in range(2):
        d.append(instant('Gitaxian Probe', 0, {}, set(), tag='probe',
                         life_cost=2, is_cantrip=True))

    assert len(d) == 60, f"TES deck: {len(d)} cards (expected 60)"
    return d


def make_tes_sideboard():
    sb = []
    # The key SB target for Burning Wish:
    for _ in range(1):
        sb.append(sorcery('Tendrils of Agony', 4, {'B':2,'generic':2}, {'B'},
                          tag='tendrils', win_condition=True, is_combo_piece=True))
    for _ in range(1):
        sb.append(sorcery('Empty the Warrens', 4, {'R':1,'generic':3}, {'R'},
                          tag='empty', win_condition=True))
    for _ in range(1):
        sb.append(sorcery('Echo of Eons', 5, {'U':2,'generic':3}, {'U'},
                          tag='echo', is_combo_piece=True))
    for _ in range(2):
        sb.append(instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster'))
    for _ in range(2):
        sb.append(instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos'))
    for _ in range(2):
        sb.append(sorcery('Grapeshot', 2, {'R':1,'generic':1}, {'R'}, tag='grape'))
    for _ in range(6):
        sb.append(instant('Galvanic Relay', 2, {'R':1,'generic':1}, {'R'}, tag='relay'))
    return sb


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _count_storm(player):
    """Approximate storm count from GY spells cast this turn."""
    return getattr(player, 'spells_cast_this_turn', 0)


def _crack_led(player, mana_pool):
    """
    Lion's Eye Diamond: {0}, sacrifice → add {B}{B}{B} but discard your hand.
    In TES: crack LED BEFORE resolving Burning Wish — the wish's resolution
    lets you search for a card before you have to discard, so hand is empty anyway.
    Simplified: if LED in hand and no other spells left to cast that need hand,
    crack it for +3 mana.
    """
    led = player.find_tag('led')
    if not led:
        return mana_pool, False
    # Only crack LED if we have a target to cast with the mana
    has_target = (player.find_tag('infernal') or player.find_tag('tendrils') or
                  player.find_tag('echo') or player.find_tag('adnaus'))
    if has_target:
        player.remove_from_hand(led)
        player.exile.append(led)
        # Discard hand (LED's cost)
        discarded = list(player.hand)
        for c in discarded:
            player.hand.remove(c)
            player.graveyard.append(c)
        if discarded:
            pass  # log elsewhere
        return mana_pool + 3, True
    return mana_pool, False


def _chrome_mox_mana(player, mana_pool):
    """Chrome Mox: exile nonartifact nonland card, add 1 mana of its color."""
    moxen = [c for c in player.hand if c.tag == 'chrome_mox']
    for mox in moxen:
        # Find best card to exile (prefer high-cmc spells we have multiples of)
        pitch_candidates = [c for c in player.hand
                            if c is not mox and not c.is_land()
                            and not getattr(c, 'is_artifact_type', False)
                            and c.tag != 'chrome_mox']
        if not pitch_candidates:
            break
        # Prefer to pitch: cantrip > ritual > other (keep combo pieces)
        pref = sorted(pitch_candidates, key=lambda c: (
            0 if c.tag in ('bs','ponder','probe') else
            1 if c.tag == 'darkrit' else
            2 if c.tag == 'vos' else 3
        ))
        pitch = pref[0]
        color = next(iter(pitch.colors)) if pitch.colors else 'B'
        player.remove_from_hand(mox)
        player.put_artifact_in_play(mox)
        player.remove_from_hand(pitch)
        player.exile.append(pitch)
        mana_pool += 1
        return mana_pool
    return mana_pool


# ─── Strategy ─────────────────────────────────────────────────────────────────

def _strategy_tes(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    TES strategy — fast Legacy storm combo.

    Key lines:
    - T1: LED + Petal + Ritual + Burning Wish → crack LED → Tendrils
    - T2+: accumulate mana, cantrip into combo, fire when ready

    Real TES is aggressive — it fires when it has a tutor + enough mana for
    Tendrils (4BB), not when it can guarantee lethal. Storm 4-5 Tendrils
    (10-12 damage) is often enough, especially with follow-up turns.
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare
    import random as _rnd

    storm = 0
    mana = total_mana

    # ── Assess hand ──────────────────────────────────────────────────────────
    hand_tags = {c.tag for c in player.hand}
    has_tutor    = 'burning_wish' in hand_tags or 'infernal' in hand_tags
    has_tendrils = 'tendrils' in hand_tags
    petals_in_hand  = sum(1 for c in player.hand if c.tag == 'petal')
    rituals_in_hand = sum(1 for c in player.hand if c.tag == 'darkrit')
    led_in_hand     = sum(1 for c in player.hand if c.tag == 'led')
    chrome_in_hand  = sum(1 for c in player.hand if c.tag == 'chrome_mox')
    cantrips        = sum(1 for c in player.hand if c.tag in ('bs', 'ponder', 'probe'))

    # Projected mana: count ALL mana sources including artifacts
    # LED provides 3 but discards hand; count as 3 for projection
    proj_mana = mana + petals_in_hand + chrome_in_hand + (led_in_hand * 3) + (rituals_in_hand * 2)

    # Storm projection: each fast mana piece is +1 storm when cast
    proj_storm = petals_in_hand + chrome_in_hand + rituals_in_hand + led_in_hand + cantrips

    # TES goes off when it has a kill line:
    # Line 1: Tutor + LED (Wish costs 0 with LED, Tendrils needs 4 from LED+lands)
    # Line 2: Tutor + enough mana (no LED, need 2 for Wish + 4 for Tendrils = 6 total)
    # Line 3: Raw Tendrils in hand + 4 mana
    # Line 4: Ad Nauseam + 5 mana
    has_adnaus = 'adnaus' in hand_tags

    can_go_off = False
    if has_tutor and led_in_hand and proj_mana >= 1:
        can_go_off = True  # LED line: always go
    elif has_tutor and proj_mana >= 6:
        can_go_off = True  # Hard-cast line
    elif has_tendrils and proj_mana >= 4:
        can_go_off = True
    elif has_adnaus and proj_mana >= 5:
        can_go_off = True

    # Also go off if we have Ad Nauseam + 5 mana
    # On later turns, be even more aggressive — go off with less
    if gs.turn >= 2 and (has_tutor or has_tendrils) and proj_mana >= 3:
        can_go_off = True

    # If we have Veil + tutor/tendrils, always go off (protected combo)
    has_veil = 'vos' in hand_tags
    if has_veil and (has_tutor or has_tendrils) and proj_mana >= 3:
        can_go_off = True

    if not can_go_off:
        # ── Develop turn: chain cantrips aggressively to find combo ──────────
        # Cast Gitaxian Probe (free) — information + storm + draw
        probe = player.find_tag('probe')
        if probe:
            player.remove_from_hand(probe); player.add_to_grave(probe)
            player.life -= 2; player.draw(1)
            player.spells_cast_this_turn += 1
            log_fn(f"Gitaxian Probe (−2 life, {player.life})")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            gs.check_life_totals()
            if gs.game_over: return

        # Crack Lotus Petals for mana to cantrip more
        while mana < 1:
            petal = player.find_tag('petal')
            if not petal: break
            player.remove_from_hand(petal); player.exile.append(petal)
            mana += 1; player.spells_cast_this_turn += 1
            log_fn(f"Petal (mana={mana}, storm={player.spells_cast_this_turn})")

        # Cast ALL cantrips to dig aggressively (not just one)
        for _ in range(3):  # up to 3 cantrips per develop turn
            bs = next((c for c in player.hand if c.tag in ('bs', 'ponder') and mana >= 1), None)
            if not bs: break
            player.remove_from_hand(bs); player.add_to_grave(bs)
            mana -= 1; player.draw(1)
            player.spells_cast_this_turn += 1
            log_fn(f"{bs.name} (dig for combo)")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            gs.check_life_totals()
            if gs.game_over: return

            # Re-check: did we find combo pieces?
            hand_tags = {c.tag for c in player.hand}
            has_tutor_now = 'burning_wish' in hand_tags or 'infernal' in hand_tags
            has_led_now = sum(1 for c in player.hand if c.tag == 'led')
            fast_now = sum(1 for c in player.hand if c.tag in ('petal','led','chrome_mox','darkrit'))
            proj_now = mana + fast_now + has_led_now * 2  # rough projection
            if has_tutor_now and proj_now >= 3:
                break  # found pieces — next turn we'll go off

        gs.state_based_actions()
        return

    # ── Going off — execute combo chain ──────────────────────────────────────
    # Model storm count from hand composition rather than tracking each spell.
    # Real TES storm count = fast_mana_pieces + cantrips + tutor + tendrils.
    # Each fast mana cast = +1 storm, each cantrip = +1, tutor = +1, Tendrils = +1.
    combo_storm = (petals_in_hand + chrome_in_hand + rituals_in_hand +
                   led_in_hand + cantrips +
                   (1 if has_tutor else 0) +  # Wish/Infernal
                   (1 if 'vos' in hand_tags else 0))  # Veil
    # Tendrils adds +1 to storm when cast
    projected_damage = (combo_storm + 1) * 2

    def cast_spell(card, cost, label):
        nonlocal storm, mana
        player.remove_from_hand(card)
        player.add_to_grave(card)
        mana -= cost
        storm += 1
        player.spells_cast_this_turn += 1
        log_fn(f"{label} (mana={mana}, storm={storm})")

    def crack_all_fast_mana():
        """Crack all fast mana in hand for maximum storm + mana."""
        nonlocal storm, mana
        # Lotus Petals first (free +1 each)
        for p in [c for c in list(player.hand) if c.tag == 'petal']:
            player.remove_from_hand(p); player.exile.append(p)
            mana += 1; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"Petal (mana={mana}, storm={storm})")
        # Chrome Mox (exile card for +1)
        for mox in [c for c in list(player.hand) if c.tag == 'chrome_mox']:
            pitch = next((c for c in player.hand
                          if c is not mox and not c.is_land()
                          and c.tag not in ('chrome_mox', 'tendrils', 'burning_wish',
                                            'led', 'vos', 'infernal', 'adnaus')
                          and c.colors), None)
            if pitch:
                player.remove_from_hand(mox); player.hand.append(mox)  # stays in play conceptually
                player.remove_from_hand(pitch); player.exile.append(pitch)
                mana += 1; storm += 1; player.spells_cast_this_turn += 1
                log_fn(f"Chrome Mox (exile {pitch.name}) → mana={mana} storm={storm}")
                break  # one mox per combo
        # Dark Rituals (cost B, add BBB = net +2)
        for rit in [c for c in list(player.hand) if c.tag == 'darkrit']:
            if mana >= 1:
                player.remove_from_hand(rit); player.add_to_grave(rit)
                mana += 2; storm += 1; player.spells_cast_this_turn += 1
                log_fn(f"Dark Ritual +2 (mana={mana}, storm={storm})")

    # ── Step 1: Gitaxian Probe (free storm + draw) ──────────────────────────
    probe = player.find_tag('probe')
    if probe:
        player.remove_from_hand(probe); player.add_to_grave(probe)
        player.life -= 2; player.draw(1)
        storm += 1; player.spells_cast_this_turn += 1
        log_fn(f"Gitaxian Probe (−2 life, {player.life}) storm={storm}")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')
        gs.check_life_totals()
        if gs.game_over: return

    # ── Step 2: Crack all fast mana ─────────────────────────────────────────
    crack_all_fast_mana()

    # ── Step 3: Cantrips for storm + draw (Brainstorm/Ponder) ───────────────
    for _ in range(3):
        bs = next((c for c in player.hand if c.tag in ('bs', 'ponder') and mana >= 1), None)
        if not bs: break
        player.remove_from_hand(bs); player.add_to_grave(bs)
        mana -= 1; storm += 1; player.spells_cast_this_turn += 1
        player.draw(1)
        log_fn(f"{bs.name} (storm={storm})")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.p1 else 'b')
        gs.check_life_totals()
        if gs.game_over: return
    # Crack any newly drawn fast mana
    crack_all_fast_mana()

    # ── Step 4: Veil of Summer (protect combo — ALWAYS cast if available) ──
    vos = player.find_tag('vos')
    if vos and not getattr(gs, 'veil_active', False):
        # Veil costs G but we treat mana generically. If mana is 0, crack a petal/LED
        if mana < 1:
            emergency = player.find_tag('petal') or player.find_tag('led')
            if emergency and emergency.tag == 'petal':
                player.remove_from_hand(emergency); player.exile.append(emergency)
                mana += 1; storm += 1; player.spells_cast_this_turn += 1
            elif emergency and emergency.tag == 'led':
                player.remove_from_hand(emergency); player.exile.append(emergency)
                discarded = [c for c in player.hand if c is not vos]
                for c in discarded:
                    player.remove_from_hand(c); player.graveyard.append(c)
                mana += 3; storm += 1; player.spells_cast_this_turn += 1
        if mana >= 1:
            player.remove_from_hand(vos); player.add_to_grave(vos)
            gs.veil_active = True
            mana -= 1; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"★ Veil of Summer — spells can't be countered (storm={storm})", True)

            # With Veil active + tutor/tendrils, TES combos unimpeded.
            # Kill rate derived from interaction model (speed + Veil)
            if has_tutor or has_tendrils:
                import random as _r
                from interaction_model import get_or_infer_interaction, compute_veil_kill_rate
                _tes_int = get_or_infer_interaction('tes')
                _tes_veil_rate = compute_veil_kill_rate(_tes_int)
                if _r.random() < _tes_veil_rate:
                    final_storm = storm + combo_storm + 1
                    final_dmg = (final_storm + 1) * 2
                    if final_dmg < 20: final_dmg = 20  # at least lethal
                    opponent.life -= final_dmg
                    player.life += final_dmg
                    log_fn(f"★ Veil + combo chain → Tendrils storm {final_storm}, {final_dmg} dmg, opp at {opponent.life}", True)
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = f"TES: Veil + Tendrils storm={final_storm} deals {final_dmg}"
                    gs.kill_turn = gs.turn
                    return

    # ── Step 5: Cast ALL remaining spells for storm before Tendrils ────────
    # Force of Will (cast normally for 5 mana for storm, or skip if mana-tight)
    for fow in [c for c in list(player.hand) if c.tag == 'fow' and mana >= 5]:
        player.remove_from_hand(fow); player.add_to_grave(fow)
        mana -= 5; storm += 1; player.spells_cast_this_turn += 1
        log_fn(f"FoW (hard-cast for storm={storm})")
    # Extra Burning Wishes / Infernal Tutors for storm
    for extra in [c for c in list(player.hand) if c.tag in ('burning_wish', 'infernal') and mana >= 2]:
        # Don't cast if we need it for tutor later and don't have Tendrils yet
        if player.find_tag('tendrils'): break
        # Cast for storm if we already have tendrils or won't need this tutor
        if sum(1 for x in player.hand if x.tag in ('burning_wish', 'infernal')) > 1:
            player.remove_from_hand(extra); player.add_to_grave(extra)
            mana -= 2; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"{extra.name} (storm padding, storm={storm})")

    # ── Step 6: Echo of Eons line (LED → discard → flashback Echo → 7 new cards)
    echo = player.find_tag('echo')
    led_for_echo = player.find_tag('led')
    if echo and led_for_echo and storm < 5:
        # Crack LED: discard hand (including Echo to GY), add 3 mana
        player.remove_from_hand(led_for_echo); player.exile.append(led_for_echo)
        discarded = list(player.hand)
        for c in discarded:
            player.remove_from_hand(c); player.graveyard.append(c)
        mana += 3; storm += 1; player.spells_cast_this_turn += 1
        log_fn(f"★ LED cracked for Echo — mana={mana}, storm={storm}, hand discarded", True)
        # Flashback Echo of Eons from GY (costs 3 generic)
        echo_in_gy = next((c for c in player.graveyard if c.tag == 'echo'), None)
        if echo_in_gy and mana >= 3:
            player.graveyard.remove(echo_in_gy); player.exile.append(echo_in_gy)
            mana -= 3; storm += 1; player.spells_cast_this_turn += 1
            # Both players draw 7 (shuffle hands+GY into libraries first)
            player.library.extend(player.graveyard); player.graveyard.clear()
            import random as _rnd
            _rnd.shuffle(player.library)
            player.draw(7)
            # Opponent also draws 7 (but that helps them too)
            opponent.library.extend(opponent.graveyard); opponent.graveyard.clear()
            _rnd.shuffle(opponent.library)
            opponent.draw(7)
            log_fn(f"★ Echo of Eons flashback — both draw 7! storm={storm}", True)
            bowmasters_triggers(7, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            gs.check_life_totals()
            if gs.game_over: return
            # Now chain the new hand's fast mana
            crack_all_fast_mana()
            # Cast any new cantrips
            for _ in range(2):
                bs = next((c for c in player.hand if c.tag in ('bs', 'ponder') and mana >= 1), None)
                if not bs: break
                player.remove_from_hand(bs); player.add_to_grave(bs)
                mana -= 1; storm += 1; player.spells_cast_this_turn += 1
                player.draw(1)
                log_fn(f"{bs.name} post-Echo (storm={storm})")
            crack_all_fast_mana()

    # ── Step 6: Burning Wish → Tendrils from sideboard ──────────────────────
    wish = player.find_tag('burning_wish')
    led_for_wish = player.find_tag('led')
    wish_cost = 0 if led_for_wish else 2
    if wish and mana >= wish_cost:
        # Crack LED in response to Wish — standard TES line
        if led_for_wish:
            player.remove_from_hand(led_for_wish); player.exile.append(led_for_wish)
            discarded = [c for c in player.hand if c is not wish]
            for c in discarded:
                player.remove_from_hand(c); player.graveyard.append(c)
            mana += 3; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"★ LED cracked — +3 mana={mana}, storm={storm}", True)

        player.remove_from_hand(wish); player.add_to_grave(wish)
        mana -= wish_cost; storm += 1; player.spells_cast_this_turn += 1

        # Choose target: Tendrils for lethal, Empty if storm is low
        proj_tendrils_dmg = (storm + 2) * 2
        matchup = getattr(gs, 'matchup', '')
        fair_non_blue = matchup in ('mardu', 'dnt', 'boros', 'eldrazi',
                                     'mono_black', 'prison', 'lands')
        use_empty = (fair_non_blue and storm >= 4 and
                     proj_tendrils_dmg < opponent.life and mana >= 4)
        if use_empty:
            empty_card = sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3},
                                 {'R'}, tag='empty', win_condition=True)
            player.hand.append(empty_card)
            log_fn(f"Burning Wish → Empty the Warrens (storm={storm})", True)
        else:
            tens = sorcery('Tendrils of Agony', 4, {'B': 2, 'generic': 2},
                           {'B'}, tag='tendrils', win_condition=True,
                           is_combo_piece=True)
            player.hand.append(tens)
            log_fn(f"Burning Wish → Tendrils (storm={storm}, mana={mana})", True)

    # ── Step 7: Infernal Tutor (hellbent → any card) ────────────────────────
    infernal = player.find_tag('infernal')
    if infernal and mana >= 2 and not player.find_tag('tendrils'):
        # Crack LED first to achieve hellbent
        led = player.find_tag('led')
        if led:
            player.remove_from_hand(led); player.exile.append(led)
            discarded = [c for c in player.hand if c is not infernal]
            for c in discarded:
                player.remove_from_hand(c); player.graveyard.append(c)
            mana += 3; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"★ LED cracked for Infernal — mana={mana}, storm={storm}", True)

        hellbent = len(player.hand) <= 1
        if hellbent:
            if not _try_counter_any(player, opponent, gs, infernal, log_entries):
                player.remove_from_hand(infernal); player.add_to_grave(infernal)
                mana -= 2; storm += 1; player.spells_cast_this_turn += 1
                tens = sorcery('Tendrils of Agony', 4, {'B': 2, 'generic': 2},
                               {'B'}, tag='tendrils', win_condition=True,
                               is_combo_piece=True)
                player.hand.append(tens)
                log_fn(f"Infernal Tutor (hellbent) → Tendrils storm={storm}", True)
            else:
                player.add_to_grave(infernal)
                log_fn("Infernal Tutor countered")

    # ── Step 8: Ad Nauseam (draw cards, lose life = cmc) ────────────────────
    adnaus = player.find_tag('adnaus')
    if adnaus and mana >= 5 and not player.find_tag('tendrils') and not gs.game_over:
        if not _try_counter_any(player, opponent, gs, adnaus, log_entries):
            player.remove_from_hand(adnaus); player.add_to_grave(adnaus)
            mana -= 5; storm += 1; player.spells_cast_this_turn += 1
            # Simulate Ad Nauseam: reveal cards, lose life = CMC each
            cards_drawn = 0; total_life_lost = 0
            for _ in range(20):
                if not player.library: break
                c = player.library.pop(0)
                player.hand.append(c)
                total_life_lost += c.cmc
                cards_drawn += 1
                if player.life - total_life_lost <= 1: break
            player.life -= total_life_lost
            log_fn(f"★ Ad Nauseam — drew {cards_drawn}, lost {total_life_lost} life → {player.life}", True)
            gs.check_life_totals()
            if not gs.game_over:
                # Chain the fresh hand
                crack_all_fast_mana()
        else:
            player.add_to_grave(adnaus)
            log_fn("Ad Nauseam countered")

    # ── Step 9: Fire Tendrils ───────────────────────────────────────────────
    tendrils = player.find_tag('tendrils')
    if tendrils and not gs.game_over:
        # Crack any remaining fast mana for storm + mana
        crack_all_fast_mana()
        # Crack remaining LEDs
        while True:
            extra_led = player.find_tag('led')
            if not extra_led: break
            player.remove_from_hand(extra_led); player.exile.append(extra_led)
            discarded = [c for c in player.hand if c is not tendrils]
            for c in discarded:
                player.remove_from_hand(c); player.graveyard.append(c)
            mana += 3; storm += 1; player.spells_cast_this_turn += 1
            log_fn(f"★ LED cracked — mana={mana}, storm={storm}", True)

        # Use the higher of running storm or projected combo_storm
        effective_storm = max(storm, combo_storm)
        damage = (effective_storm + 1) * 2
        veil_up = getattr(gs, 'veil_active', False)
        lethal = damage >= opponent.life
        good_storm = effective_storm >= 5 and damage >= 12
        protected_ok = veil_up and effective_storm >= 3
        desperate = player.life <= 6 or gs.turn >= 4

        if mana >= 4 and (lethal or good_storm or protected_ok or desperate):
            if not _try_counter_any(player, opponent, gs, tendrils, log_entries):
                player.remove_from_hand(tendrils); player.add_to_grave(tendrils)
                effective_storm += 1; player.spells_cast_this_turn += 1
                # With Veil protection, TES can chain spells freely → model as lethal storm
                # Real TES with Veil resolving = 95%+ kill rate (no interaction)
                if veil_up and effective_storm < 9:
                    effective_storm = max(effective_storm, 9)  # Veil = free to chain → high storm
                final_damage = (effective_storm + 1) * 2
                opponent.life -= final_damage
                player.life += final_damage
                log_fn(f"★ Tendrils — storm {storm}, {final_damage} dmg, opp at {opponent.life}", True)
                if opponent.life <= 0:
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = f"TES: Tendrils storm={storm} deals {final_damage}"
                    gs.kill_turn = gs.turn
                else:
                    gs.check_life_totals()
            else:
                player.add_to_grave(tendrils)
                log_fn("Tendrils countered")

    # ── Alternate win: Empty the Warrens ─────────────────────────────────────
    empty = player.find_tag('empty')
    if not gs.game_over and empty and mana >= 4 and storm >= 3:
        if not _try_counter_any(player, opponent, gs, empty, log_entries):
            player.remove_from_hand(empty); player.add_to_grave(empty)
            storm += 1; player.spells_cast_this_turn += 1
            token_count = (storm + 1) * 2
            log_fn(f"★ Empty the Warrens — storm {storm}, {token_count} Goblins", True)
            if token_count >= 6:
                gs.game_over = True
                gs.winner = 'p1' if player is gs.p1 else 'p2'
                gs.win_reason = f"TES: Empty the Warrens ({token_count} goblins)"
                gs.kill_turn = gs.turn + 1
        else:
            player.add_to_grave(empty)

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_tes():
    results = []

    # Test 1: Deck size
    deck = make_tes_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("✓ Deck size = 60")

    # Test 2: Key cards
    tags = {c.tag for c in deck}
    for req in ['led','burning_wish','tendrils','darkrit','infernal','vos','fow']:
        assert req in tags, f"Missing: {req}"
    results.append("✓ All key cards present")

    # Test 3: Sideboard
    sb = make_tes_sideboard()
    assert len(sb) > 0
    results.append(f"✓ Sideboard: {len(sb)} cards")

    # Test 4: Bo3 smoke test
    from sim import STRATEGIES
    from cards import DECKS
    DECKS['tes'] = make_tes_deck
    STRATEGIES['tes'] = _strategy_tes
    try:
        from sim import run_any_bo3
        r = run_any_bo3('tes', 'dimir', 10)
        results.append(f"✓ TES vs Dimir (10 matches): {r['match_wr']*100:.0f}%")
    except Exception as e:
        results.append(f"✗ Bo3 failed: {e}")

    return results


if __name__ == '__main__':
    print("Running TES tests...")
    for r in test_tes():
        print(f"  {r}")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_tes(hand, matchup=''):
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    if len(nonlands) < 1: return False
    tags = {c.tag for c in hand}
    has_tutor = any(t in tags for t in ('burning_wish', 'infernal'))
    has_cantrip = any(c.tag in ('bs', 'ponder', 'probe') for c in nonlands)
    fast_mana = sum(1 for c in nonlands if c.tag in ('petal', 'led', 'chrome_mox', 'darkrit'))
    has_mana = lc >= 1 or fast_mana >= 2
    has_action = has_tutor or has_cantrip
    if len(hand) <= 5: return has_mana and has_action
    return has_mana and fast_mana >= 1 and has_action


DECK_META = {
    'key':        'tes',
    'name':       'The Epic Storm',
    'make_deck':  make_tes_deck,
    'strategy':   _strategy_tes,
    'keep':       _keep_tes,
    'categories': {'combo', 'fast_combo'},
    'interaction': {'speed': 2, 'resilience': 2, 'uses_graveyard': False, 'uses_veil': True, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.02,
}
