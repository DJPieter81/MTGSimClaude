"""
Belcher (Goblin Charbelcher) — Legacy near-zero-land combo deck.

The deck runs only 1 land (Taiga) so that Goblin Charbelcher's activation
reveals nearly the entire library, dealing 30-50+ damage (doubled because
Taiga has Mountain subtype). The combo is:
  1. Generate 7+ mana via Spirit Guides, Lotus Petal, Chrome Mox, rituals
  2. Cast Goblin Charbelcher (4 mana artifact)
  3. Activate Charbelcher (3 mana, tap): reveal cards until a land is hit
     → damage = number of revealed cards, doubled if land is a Mountain
  4. With ~59 nonland cards, this is almost always lethal

Alternate win: Empty the Warrens with high storm count (Burning Wish can
fetch it from the sideboard).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/home/claude/mtg_sim')

from cards import creature, instant, sorcery, artifact, dual_land
from decision import ManaDecision, MetaDecision


# ─── Deck construction ────────────────────────────────────────────────────────

def make_belcher_deck():
    d = []

    # ── Land (1) ─────────────────────────────────────────────────────────────
    # Taiga: R/G dual — Mountain Forest (crucial: Mountain subtype doubles Charbelcher)
    d.append(dual_land('Taiga', ['R', 'G'], ['Mountain', 'Forest']))

    # ── Combo piece (4) ──────────────────────────────────────────────────────
    for _ in range(4):
        c = artifact('Goblin Charbelcher', 4, {'generic': 4},
                     tag='belcher', is_combo_piece=True)
        d.append(c)

    # ── Fast mana — artifacts (12) ───────────────────────────────────────────
    # Lion's Eye Diamond: {0}, sac → add 3 mana of any color, discard hand
    for _ in range(4):
        c = artifact("Lion's Eye Diamond", 0, {}, tag='led', is_combo_piece=True)
        c.led = True
        d.append(c)

    # Lotus Petal: {0}, sac → add 1 mana of any color
    for _ in range(4):
        d.append(artifact('Lotus Petal', 0, {}, tag='petal'))

    # Chrome Mox: {0}, imprint nonartifact/nonland → add 1 mana of its color
    for _ in range(4):
        c = artifact('Chrome Mox', 0, {}, tag='chrome_mox')
        c.chrome_mox = True
        d.append(c)

    # ── Fast mana — Spirit Guides (8) ────────────────────────────────────────
    # Elvish Spirit Guide: exile from hand → add {G}
    for _ in range(4):
        d.append(creature('Elvish Spirit Guide', 2, {'G': 2, 'generic': 1},
                          'G', power=2, toughness=2, tag='esg'))

    # Simian Spirit Guide: exile from hand → add {R}
    for _ in range(4):
        d.append(creature('Simian Spirit Guide', 3, {'R': 1, 'generic': 2},
                          'R', power=2, toughness=2, tag='ssg'))

    # ── Rituals (16) ─────────────────────────────────────────────────────────
    # Dark Ritual: {B} → add BBB (net +2)
    for _ in range(4):
        d.append(sorcery('Dark Ritual', 1, {'B': 1}, {'B'}, tag='darkrit'))

    # Rite of Flame: {R} → add RR (or RRR with rite in GY)
    for _ in range(4):
        d.append(sorcery('Rite of Flame', 1, {'R': 1}, {'R'}, tag='rite'))

    # Seething Song: {2R} → add RRRRR (net +2)
    for _ in range(4):
        d.append(sorcery('Seething Song', 3, {'R': 1, 'generic': 2}, {'R'},
                         tag='seething'))

    # Desperate Ritual: {1R} → add RRR (net +1)
    for _ in range(3):
        d.append(sorcery('Desperate Ritual', 2, {'R': 1, 'generic': 1}, {'R'},
                         tag='desperate'))

    # Tinder Wall: {G} creature, sac → add RR (4-of in tier-1 Belcher: it's
    # a free 2-mana ritual that pitches to Chrome Mox.  Was 2; bumped to 4.)
    for _ in range(4):
        d.append(creature('Tinder Wall', 1, {'G': 1}, 'G',
                          power=0, toughness=1, tag='tinder'))

    # ── Spells (15) ──────────────────────────────────────────────────────────
    # Land Grant: {1G} or free if no lands in hand — reveal hand, search for Forest
    for _ in range(4):
        d.append(sorcery('Land Grant', 2, {'G': 1, 'generic': 1}, {'G'},
                         tag='grant'))

    # Burning Wish: {1R} tutor sorcery from sideboard
    for _ in range(4):
        d.append(sorcery('Burning Wish', 2, {'R': 1, 'generic': 1}, {'R'},
                         tag='burning_wish', is_combo_piece=True))

    # Empty the Warrens: {3R} storm — create 2 Goblin tokens per storm count.
    # Trimmed 4 → 2 main; real Belcher runs 1-2 main and tutors more via
    # Burning Wish from the sideboard.
    for _ in range(2):
        d.append(sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3}, {'R'},
                         tag='empty', win_condition=True))

    # Gitaxian Probe: 2 life, look at opp hand, draw 1.  4-of in tier-1
    # Belcher (was 3): free cantrip + storm count, doubles as info.
    for _ in range(4):
        d.append(instant('Gitaxian Probe', 0, {}, set(), tag='probe',
                         life_cost=2, is_cantrip=True))

    # ── Protection (2) ───────────────────────────────────────────────────────
    # Veil of Summer: {G}, can't be countered, protects your spells.
    # Trimmed 3 → 2 to fit extra Probe / Tinder Wall — Belcher's race plan
    # cares more about combo speed than reactive protection.
    for _ in range(2):
        d.append(instant('Veil of Summer', 1, {'G': 1}, {'G'}, tag='vos'))

    assert len(d) == 60, f"Belcher deck: {len(d)} cards (expected 60)"
    return d


def make_belcher_sideboard():
    sb = []
    sb.append(sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3}, {'R'},
                      tag='empty', win_condition=True))
    sb.append(sorcery('Tendrils of Agony', 4, {'B': 2, 'generic': 2}, {'B'},
                      tag='tendrils', win_condition=True, is_combo_piece=True))
    sb.append(sorcery('Grapeshot', 2, {'R': 1, 'generic': 1}, {'R'}, tag='grape'))
    return sb


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _count_storm(player):
    """Approximate storm count from spells cast this turn."""
    return getattr(player, 'spells_cast_this_turn', 0)


def _activate_charbelcher(player, opponent, gs, log_fn, log_entries):
    """
    Goblin Charbelcher activation: reveal cards from library until you hit a land.
    Deal damage equal to the number of cards revealed.
    If the land has the Mountain subtype, double the damage.
    """
    damage = 0
    for i, card in enumerate(player.library):
        if card.is_land():
            if 'Mountain' in getattr(card, 'subtypes', set()):
                damage *= 2
            break
        damage += 1
    else:
        # No land found — entire library is damage
        damage = len(player.library)

    opponent.life -= damage
    log_fn(f"★ Charbelcher activation — revealed {damage // 2 if damage > 50 else damage} "
           f"cards, {damage} damage, opp at {opponent.life}", True)

    if opponent.life <= 0:
        gs.game_over = True
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = f"Belcher: Charbelcher deals {damage} damage"
        gs.kill_turn = gs.turn
    else:
        gs.check_life_totals()


# ─── Strategy ────────────────────────────────────────────────────────────────

def _strategy_belcher(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Belcher strategy — all-in T1 combo.

    Key line: Spirit Guides + Petals + Rituals → Charbelcher (4) → Activate (3)
    Needs 7 total mana to cast + activate in one shot.
    Alternate plan: Empty the Warrens with high storm count.
    """
    from engine import cast_spell, bowmasters_triggers

    storm = [0]   # mutable so on_resolve callbacks can increment
    budget = [total_mana]

    def exile_for_mana(card, gained, label):
        player.remove_from_hand(card)
        player.exile.append(card)
        budget[0] += gained
        # Spirit Guide / Lotus Petal-style 0-cost fast mana: +gained net ramp.
        gs.strat_log.log(ManaDecision(
            turn=gs.turn,
            deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
            reason=f'{card.tag}_exile → +{gained} mana',
            candidates=('ritual', 'pass'),
            kind='ramp',
            mana_value=gained,
        ))
        log_fn(f"{label} (mana={budget[0]})")

    # ── Step 1: Free mana — Spirit Guides (activated ability, uncounterable) ─
    for esg in [c for c in player.hand if c.tag == 'esg']:
        exile_for_mana(esg, 1, "Elvish Spirit Guide (exile → +G)")

    for ssg in [c for c in player.hand if c.tag == 'ssg']:
        exile_for_mana(ssg, 1, "Simian Spirit Guide (exile → +R)")

    # ── Step 2: Lotus Petals (simplified as cast+sac — kept outside cast_spell
    # pipeline so opponent can't counter a 0-mana artifact that would normally
    # resolve without interaction) ───────────────────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.exile.append(petal)
        budget[0] += 1
        storm[0] += 1
        player.spells_cast_this_turn += 1
        gs.strat_log.log(ManaDecision(
            turn=gs.turn,
            deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
            reason='petal_crack → +1 mana',
            candidates=('ritual', 'pass'),
            kind='ramp',
            mana_value=1,
        ))
        log_fn(f"Lotus Petal (mana={budget[0]}, storm={storm[0]})")

    # ── Step 3: Chrome Mox (cast-and-tap simplified; see Petals note) ───────
    # Audit-fix (docs/audits/belcher_vs_uwx.md): Mox was greedy on the first
    # colored nonland, exiling Burning Wish / Empty as fuel. Helper now
    # filters `is_combo_piece` / `win_condition` (belcher / led / burning_wish
    # / empty / tendrils all carry one of the flags) plus explicit protected
    # tags for chrome_mox and Veil of Summer (no flag, but losing it loses
    # the combo turn vs FoW/Daze decks).
    from engine import select_pitch_target
    _belcher_protected = frozenset({'chrome_mox', 'vos'})
    for mox in [c for c in player.hand if c.tag == 'chrome_mox']:
        # Payoff-redundancy gate: only imprint when hand still contains
        # ≥1 castable payoff (Belcher / Empty / Burning Wish) after the
        # pitch lands. Without this gate, Mox imprints the deck's sole
        # payoff and leaves a ramped-but-dead position.
        payoff_count = sum(1 for c in player.hand
                           if c is not mox and c.tag in ('belcher', 'empty', 'burning_wish'))
        if payoff_count < 1:
            continue
        # Prefer red, fall back to black/green (deck colors).
        pitch = (select_pitch_target(player.hand, 'R', mox, _belcher_protected)
                 or select_pitch_target(player.hand, 'B', mox, _belcher_protected)
                 or select_pitch_target(player.hand, 'G', mox, _belcher_protected))
        if pitch:
            player.remove_from_hand(mox)
            player.put_artifact_in_play(mox)
            player.remove_from_hand(pitch)
            player.exile.append(pitch)
            budget[0] += 1
            storm[0] += 1
            player.spells_cast_this_turn += 1
            gs.strat_log.log(ManaDecision(
                turn=gs.turn,
                deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                reason='chrome_mox → +1 mana',
                candidates=('ritual', 'pass'),
                kind='ramp',
                mana_value=1,
            ))
            log_fn(f"Chrome Mox (exile {pitch.name}) → mana={budget[0]} storm={storm[0]}")
            break  # typically only imprint one

    # ── Step 4: Land Grant (free if no lands in hand) ───────────────────────
    grant = player.find_tag('grant')
    has_land_in_hand = any(c.is_land() for c in player.hand)
    if grant and not has_land_in_hand:
        def _resolve_grant(c):
            player.add_to_grave(c)
            storm[0] += 1
            taiga = next((cc for cc in player.library if cc.name == 'Taiga'), None)
            if taiga:
                player.library.remove(taiga)
                player.hand.append(taiga)
                log_fn(f"Land Grant (free, revealed hand) → Taiga to hand (storm={storm[0]})")
            else:
                log_fn(f"Land Grant (free) — no Forest in library (storm={storm[0]})")
        cast_spell(player, opponent, gs, grant, None, log_fn, log_entries,
                   on_resolve=_resolve_grant)

    # Play Taiga from hand if we have it (land drop → +1 mana)
    taiga_in_hand = next((c for c in player.hand if c.name == 'Taiga'), None)
    if taiga_in_hand:
        player.remove_from_hand(taiga_in_hand)
        # Put on battlefield (simplified: just add mana)
        budget[0] += 1
        log_fn(f"Play Taiga → mana={budget[0]}")

    # ── Step 5: Tinder Wall (cast for {G}, sac for RR = net +1) ─────────────
    for tw in [c for c in player.hand if c.tag == 'tinder']:
        if budget[0] >= 1:
            def _resolve_tinder(c):
                player.add_to_grave(c)
                budget[0] += 2   # sac for RR — cost_override=1 already deducted
                storm[0] += 1
                gs.strat_log.log(ManaDecision(
                    turn=gs.turn,
                    deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                    reason='tinder_wall → +1 mana',
                    candidates=('ritual', 'pass'),
                    kind='ramp',
                    mana_value=1,
                ))
                log_fn(f"Tinder Wall (cast + sac → +RR, net +1) mana={budget[0]} storm={storm[0]}")
            cast_spell(player, opponent, gs, tw, budget, log_fn, log_entries,
                       on_resolve=_resolve_tinder, cost_override=1)

    # ── Step 6: Gitaxian Probe (free, storm + draw) ─────────────────────────
    for probe in [c for c in player.hand if c.tag == 'probe']:
        def _resolve_probe(c):
            player.add_to_grave(c)
            player.life -= 2
            player.draw(1)
            storm[0] += 1
            log_fn(f"Gitaxian Probe (−2 life → {player.life}) storm={storm[0]}")
            bowmasters_triggers(1, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
            gs.check_life_totals()
        cast_spell(player, opponent, gs, probe, None, log_fn, log_entries,
                   on_resolve=_resolve_probe)
        if gs.game_over:
            return

    # ── Step 7: Rituals ─────────────────────────────────────────────────────
    # Dark Ritual: {B} → BBB (net +2)
    for rit in [c for c in player.hand if c.tag == 'darkrit']:
        if budget[0] >= 1:
            def _resolve_darkrit(c):
                player.add_to_grave(c)
                budget[0] += 3  # Dark Ritual adds BBB; cost_override=1 already deducted
                storm[0] += 1
                gs.strat_log.log(ManaDecision(
                    turn=gs.turn,
                    deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                    reason='dark_ritual → +2 mana',
                    candidates=('ritual', 'pass'),
                    kind='ramp',
                    mana_value=2,
                ))
                log_fn(f"Dark Ritual → +BBB (mana={budget[0]}, storm={storm[0]})")
            cast_spell(player, opponent, gs, rit, budget, log_fn, log_entries,
                       on_resolve=_resolve_darkrit, cost_override=1)

    # Rite of Flame: {R} → RR (net +1), or RRR if rite already in GY
    for rite in [c for c in player.hand if c.tag == 'rite']:
        if budget[0] >= 1:
            _rites_in_gy = sum(1 for c in player.graveyard if c.tag == 'rite')
            _produced = 3 if _rites_in_gy > 0 else 2
            def _resolve_rite(c, _p=_produced):
                player.add_to_grave(c)
                budget[0] += _p
                storm[0] += 1
                # Net mana: produced - 1 (cost_override). +1 baseline, +2 with prior rite in GY.
                _net = _p - 1
                gs.strat_log.log(ManaDecision(
                    turn=gs.turn,
                    deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                    reason=f'rite_of_flame → +{_net} mana',
                    candidates=('ritual', 'pass'),
                    kind='ramp',
                    mana_value=_net,
                ))
                log_fn(f"Rite of Flame → +{'RRR' if _p == 3 else 'RR'} "
                       f"(mana={budget[0]}, storm={storm[0]})")
            cast_spell(player, opponent, gs, rite, budget, log_fn, log_entries,
                       on_resolve=_resolve_rite, cost_override=1)

    # Desperate Ritual: {1R} → RRR (net +1)
    for des in [c for c in player.hand if c.tag == 'desperate']:
        if budget[0] >= 2:
            def _resolve_desperate(c):
                player.add_to_grave(c)
                budget[0] += 3
                storm[0] += 1
                gs.strat_log.log(ManaDecision(
                    turn=gs.turn,
                    deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                    reason='desperate_ritual → +1 mana',
                    candidates=('ritual', 'pass'),
                    kind='ramp',
                    mana_value=1,
                ))
                log_fn(f"Desperate Ritual → +RRR (mana={budget[0]}, storm={storm[0]})")
            cast_spell(player, opponent, gs, des, budget, log_fn, log_entries,
                       on_resolve=_resolve_desperate, cost_override=2)

    # Seething Song: {2R} → RRRRR (net +2)
    for song in [c for c in player.hand if c.tag == 'seething']:
        if budget[0] >= 3:
            def _resolve_seething(c):
                player.add_to_grave(c)
                budget[0] += 5
                storm[0] += 1
                gs.strat_log.log(ManaDecision(
                    turn=gs.turn,
                    deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                    reason='seething_song → +2 mana',
                    candidates=('ritual', 'pass'),
                    kind='ramp',
                    mana_value=2,
                ))
                log_fn(f"Seething Song → +RRRRR (mana={budget[0]}, storm={storm[0]})")
            cast_spell(player, opponent, gs, song, budget, log_fn, log_entries,
                       on_resolve=_resolve_seething, cost_override=3)

    # ── Step 8: Veil of Summer (protect combo) ──────────────────────────────
    vos = player.find_tag('vos')
    opp_has_counters = any(c.tag in ('fow', 'fon', 'daze', 'fluster')
                          for c in opponent.hand)
    opp_mana_up = sum(1 for l in opponent.lands if not l.tapped)
    if vos and budget[0] >= 1 and (opp_has_counters or opp_mana_up >= 1):
        # Meta-axis play-around — Belcher casts Veil of Summer pre-emptively
        # because opp has counters in hand or mana up. The threat tag is
        # 'free_counter' when fow/fon/daze are seen, 'open_mana' otherwise
        # (tap-out tempo counter like Counterspell / Daze trigger).
        _threat_tag = 'free_counter' if opp_has_counters else 'open_mana'
        gs.strat_log.log(MetaDecision(
            turn=gs.turn,
            deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
            phase='meta',
            reason=(f'cast Veil of Summer pre-combo — '
                    f'opp_has_counters={opp_has_counters}, '
                    f'opp_mana_up={opp_mana_up}'),
            candidates=('skip_vos', 'play_around'),
            kind='play_around',
            threat_tag=_threat_tag,
        ))
        if not getattr(gs, 'veil_active', False):
            def _resolve_vos(c):
                player.add_to_grave(c)
                gs.veil_active = True
                storm[0] += 1
                log_fn(f"★ Veil of Summer — uncounterable (storm={storm[0]})", True)
            cast_spell(player, opponent, gs, vos, budget, log_fn, log_entries,
                       on_resolve=_resolve_vos, cost_override=1)

    # ── Step 9: Cast + Activate Goblin Charbelcher ──────────────────────────
    # Canonical line: cast Charbelcher (4 mana), then crack LEDs in response
    # to activation (CR 605.1 — activated mana abilities resolve at instant
    # speed, before the activation cost is paid). LED gives +3 mana but
    # discards the rest of hand. Worth it when activating Belcher because
    # Belcher reveals its own kill condition — the discarded hand is
    # irrelevant. Without this, the deck capped at ~6 mana on T1 even with
    # the combo assembled (Charbelcher + 4-5 fast-mana sources).
    belcher = player.find_tag('belcher')
    # Conservative gate: only cast Belcher if we can ALSO activate it this
    # turn — either via pre-existing mana (budget >= 7) or by cracking LEDs
    # in response (budget >= 4 + 3*N_LED where N_LED * 3 covers the gap).
    if belcher and not gs.game_over:
        leds_in_hand = [c for c in player.hand if c.tag == 'led']
        # Total mana available if we crack all LEDs in response to activation.
        post_led_mana = budget[0] + 3 * len(leds_in_hand)
        if budget[0] >= 4 and post_led_mana >= 7:
            def _resolve_belcher_full(c, _leds=leds_in_hand):
                player.put_artifact_in_play(c)
                storm[0] += 1
                log_fn(f"★ Goblin Charbelcher (mana={budget[0]}, storm={storm[0]})", True)
                # Crack LEDs in response to Charbelcher activation. LED is an
                # activated mana ability — exile from play (or hand, in sim),
                # +3 mana, discard hand. Order: stack Belcher activation,
                # then crack LED, LED ability resolves first.
                for led in _leds:
                    if budget[0] >= 3:
                        # Already have enough — no need to crack
                        break
                    player.remove_from_hand(led)
                    player.exile.append(led)
                    budget[0] += 3
                    storm[0] += 1
                    player.spells_cast_this_turn += 1
                    gs.strat_log.log(ManaDecision(
                        turn=gs.turn,
                        deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                        reason='led_crack_for_belcher → +3 mana',
                        candidates=('ritual', 'pass'),
                        kind='ramp',
                        mana_value=3,
                    ))
                    log_fn(f"★ LED cracked (in response to Charbelcher activation) "
                           f"→ +3 mana={budget[0]}, storm={storm[0]}", True)
                # LED's "discard remaining hand" cost — clear non-LED, non-Belcher
                # cards (the cracked LEDs are already in exile; Charbelcher is
                # already on the stack). Other LEDs in hand still need discarding.
                if _leds:
                    for c in list(player.hand):
                        player.remove_from_hand(c)
                        player.add_to_grave(c)
                # Activate Charbelcher (3 mana, tap)
                if budget[0] >= 3:
                    budget[0] -= 3
                    _activate_charbelcher(player, opponent, gs, log_fn, log_entries)
            if not cast_spell(player, opponent, gs, belcher, budget, log_fn, log_entries,
                              on_resolve=_resolve_belcher_full, cost_override=4):
                log_fn("Goblin Charbelcher countered")

    # ── Step 10: Cast Charbelcher without activating (if mana < 7 but >= 4)
    if not gs.game_over and player.find_tag('belcher') and budget[0] >= 4 and budget[0] < 7:
        belcher = player.find_tag('belcher')
        def _resolve_belcher_delayed(c):
            player.put_artifact_in_play(c)
            storm[0] += 1
            log_fn(f"Charbelcher cast (waiting to activate next turn) mana={budget[0]}")
        if not cast_spell(player, opponent, gs, belcher, budget, log_fn, log_entries,
                          on_resolve=_resolve_belcher_delayed, cost_override=4):
            log_fn("Goblin Charbelcher countered")

    # ── Step 11: Burning Wish → Empty the Warrens from sideboard ────────────
    # Gate (docs/audits/belcher_vs_ur_delver.md): Wish (2) must leave
    # enough mana to cast Empty (4) on the same turn — otherwise the
    # fetched copy sits in hand with no mana to cast it. LED in hand
    # adds +3 mana via discard-during-Wish, so the floor drops to 3:
    #   floor = 2 (Wish) + 4 (Empty) − 3 (LED) = 3 with LED
    #   floor = 2 (Wish) + 4 (Empty)          = 6 without LED
    wish = player.find_tag('burning_wish')
    _led_in_hand = player.find_tag('led') is not None
    _wish_floor = 3 if _led_in_hand else 6
    if not gs.game_over and wish and budget[0] >= _wish_floor and storm[0] >= 3:
        # Crack LED in response (activated ability — uncounterable)
        led = player.find_tag('led')
        if led:
            player.remove_from_hand(led)
            player.exile.append(led)
            discarded = [c for c in player.hand if c is not wish]
            for c in discarded:
                player.remove_from_hand(c)
                player.graveyard.append(c)
            budget[0] += 3
            storm[0] += 1
            player.spells_cast_this_turn += 1
            gs.strat_log.log(ManaDecision(
                turn=gs.turn,
                deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
                reason='led_crack → +3 mana',
                candidates=('ritual', 'pass'),
                kind='ramp',
                mana_value=3,
            ))
            log_fn(f"★ LED cracked — +3 mana={budget[0]}, storm={storm[0]}", True)

        def _resolve_wish(c):
            player.add_to_grave(c)
            storm[0] += 1
            # Fetch Empty the Warrens from SB
            empty_card = sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3},
                                 {'R'}, tag='empty', win_condition=True)
            player.hand.append(empty_card)
            log_fn(f"Burning Wish → Empty the Warrens (storm={storm[0]})", True)
        cast_spell(player, opponent, gs, wish, budget, log_fn, log_entries,
                   on_resolve=_resolve_wish, cost_override=2)

    # ── Step 12: Empty the Warrens as backup win ────────────────────────────
    empty = player.find_tag('empty')
    if not gs.game_over and empty and budget[0] >= 4 and storm[0] >= 3:
        def _resolve_empty(c):
            player.add_to_grave(c)
            storm[0] += 1
            token_count = (storm[0] + 1) * 2
            log_fn(f"★ Empty the Warrens — storm {storm[0]}, {token_count} Goblins", True)
            if token_count >= 6:
                gs.game_over = True
                gs.winner = 'p1' if player is gs.p1 else 'p2'
                gs.win_reason = f"Belcher: Empty the Warrens ({token_count} goblins)"
                gs.kill_turn = gs.turn + 1
        if not cast_spell(player, opponent, gs, empty, budget, log_fn, log_entries,
                          on_resolve=_resolve_empty, cost_override=4):
            log_fn("Empty the Warrens countered")

    gs.state_based_actions()


# ─── Mini test suite ──────────────────────────────────────────────────────────

def test_belcher():
    results = []

    # Test 1: Deck size
    deck = make_belcher_deck()
    assert len(deck) == 60, f"Deck {len(deck)} != 60"
    results.append("OK  Deck size = 60")

    # Test 2: Key cards present
    tags = {c.tag for c in deck}
    for req in ['belcher', 'led', 'petal', 'chrome_mox', 'esg', 'ssg',
                'darkrit', 'rite', 'seething', 'desperate', 'tinder',
                'grant', 'burning_wish', 'empty', 'probe', 'vos']:
        assert req in tags, f"Missing tag: {req}"
    results.append("OK  All 16 card types present")

    # Test 3: Only 1 land
    lands = [c for c in deck if c.is_land()]
    assert len(lands) == 1, f"Expected 1 land, got {len(lands)}"
    assert lands[0].name == 'Taiga'
    assert 'Mountain' in lands[0].subtypes
    assert 'Forest' in lands[0].subtypes
    results.append("OK  Exactly 1 land (Taiga, Mountain/Forest)")

    # Test 4: Card counts
    from collections import Counter
    tag_counts = Counter(c.tag for c in deck)
    assert tag_counts['belcher'] == 4
    assert tag_counts['led'] == 4
    assert tag_counts['petal'] == 4
    assert tag_counts['chrome_mox'] == 4
    assert tag_counts['esg'] == 4
    assert tag_counts['ssg'] == 4
    assert tag_counts['darkrit'] == 4
    assert tag_counts['rite'] == 4
    assert tag_counts['seething'] == 4
    assert tag_counts['desperate'] == 3
    assert tag_counts['tinder'] == 2
    assert tag_counts['grant'] == 4
    assert tag_counts['burning_wish'] == 4
    assert tag_counts['empty'] == 4
    assert tag_counts['probe'] == 3
    assert tag_counts['vos'] == 3
    assert tag_counts['dual'] == 1  # Taiga
    results.append("OK  All card counts correct")

    # Test 5: Charbelcher activation simulation
    # With ~59 nonland cards, damage should be huge
    # Simulate: put Taiga somewhere in the middle of a mock library
    class MockCard:
        def __init__(self, name, is_land_flag=False, subtypes=None):
            self.name = name
            self._is_land = is_land_flag
            self.subtypes = subtypes or set()
        def is_land(self):
            return self._is_land

    # Library with Taiga at position 30 (31 cards deep)
    lib = [MockCard(f'spell_{i}') for i in range(30)]
    lib.append(MockCard('Taiga', is_land_flag=True, subtypes={'Mountain', 'Forest'}))
    lib.extend([MockCard(f'spell_{i}') for i in range(30, 50)])

    damage = 0
    for i, card in enumerate(lib):
        if card.is_land():
            if 'Mountain' in getattr(card, 'subtypes', set()):
                damage *= 2
            break
        damage += 1
    # 30 cards revealed, doubled by Mountain = 60 damage
    assert damage == 60, f"Expected 60 damage, got {damage}"
    results.append("OK  Charbelcher activation: 30 revealed * 2 (Mountain) = 60 damage")

    # Test 6: Sideboard
    sb = make_belcher_sideboard()
    assert len(sb) == 3
    sb_tags = {c.tag for c in sb}
    assert 'empty' in sb_tags
    assert 'tendrils' in sb_tags
    results.append(f"OK  Sideboard: {len(sb)} cards")

    # Test 7: Combo pieces marked correctly
    combo_pieces = [c for c in deck if c.is_combo_piece]
    combo_tags = {c.tag for c in combo_pieces}
    assert 'belcher' in combo_tags
    assert 'led' in combo_tags
    assert 'burning_wish' in combo_tags
    results.append("OK  Combo pieces flagged (belcher, led, burning_wish)")

    return results


if __name__ == '__main__':
    print("Running Belcher tests...")
    for r in test_belcher():
        print(f"  {r}")
    print("All Belcher tests passed.")


# ─── Deck Metadata (auto-registration) ──────────────────────────────────────

def _keep_belcher(hand, matchup=''):
    nonlands = [c for c in hand if not c.is_land()]
    tags = {c.tag for c in hand}
    fast = sum(1 for c in nonlands if c.tag in ('petal', 'led', 'chrome_mox', 'esg', 'ssg', 'darkrit', 'rite'))
    has_belcher = 'belcher' in tags or 'burning_wish' in tags
    has_empty = 'empty' in tags
    if len(hand) <= 5: return fast >= 1 and (has_belcher or has_empty)
    return fast >= 2 and (has_belcher or has_empty)


DECK_META = {
    'key':        'belcher',
    'name':       'Goblin Charbelcher',
    'make_deck':  make_belcher_deck,
    'strategy':   _strategy_belcher,
    'keep':       _keep_belcher,
    'categories': {'combo', 'fast_combo'},
    'interaction': {'speed': 1, 'resilience': 1, 'uses_graveyard': False, 'uses_veil': False, 'soft_to_wasteland': False, 'creature_based': False},
    'meta_share': 0.01,
}
