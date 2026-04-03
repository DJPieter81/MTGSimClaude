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
    TES strategy — models the actual combo chain within a single turn.

    TES goldfish kill (T1 on play):
      Swamp → Lotus Petal → Lotus Petal → Chrome Mox (exile cantrip) →
      Dark Ritual → Dark Ritual → Burning Wish (crack LED in response) →
      Tendrils (storm 7-8) → lethal.

    Key sequencing:
    1. Deploy free mana (Petal, Chrome Mox) first — each counts for storm
    2. Cast Rituals — each +2 mana and +1 storm  
    3. Probe if available — free info and +1 storm
    4. Veil of Summer if opp has counters and mana allows
    5. Burning Wish → fetches Tendrils from SB (crack LED in response if available)
    6. Infernal Tutor (hellbent) if no Wish
    7. Tendrils when (storm+1)*2 >= opponent life

    Storm resets each turn. This strategy fires in one burst when conditions met.
    """
    from engine import _try_counter_any, bowmasters_triggers, combat_declare
    import random as _rnd

    # Reset storm counter (accumulated this turn only)
    storm = 0
    mana = total_mana

    # ── Pre-check: can we actually go off this turn? ─────────────────────────
    # Only fire mana accelerants if we have a realistic kill line this turn.
    # Kill line requires: tutor (Wish or Infernal) + enough mana to cast it + LED or Rituals
    hand_tags = {c.tag for c in player.hand}
    has_tutor  = 'burning_wish' in hand_tags or 'infernal' in hand_tags
    has_tendrils = 'tendrils' in hand_tags
    petals_in_hand   = sum(1 for c in player.hand if c.tag == 'petal')
    rituals_in_hand  = sum(1 for c in player.hand if c.tag == 'darkrit')
    led_in_hand      = sum(1 for c in player.hand if c.tag == 'led')
    chrome_in_hand   = sum(1 for c in player.hand if c.tag == 'chrome_mox')
    # Projected storm this turn: petals + chrome + rituals + probe + vos + tutor + LED
    storm_potential = petals_in_hand + chrome_in_hand + rituals_in_hand +                       (1 if 'probe' in hand_tags else 0) +                       (1 if 'vos' in hand_tags else 0) +                       (1 if has_tutor else 0) + (1 if led_in_hand else 0)
    # Projected mana: land + petals + chrome + LED*3 + rituals*2
    proj_mana = mana + petals_in_hand + chrome_in_hand + (led_in_hand * 3) + (rituals_in_hand * 2)
    # Lethal check: (storm_potential+2)*2 >= opponent life (approximate)
    proj_damage = (storm_potential + 2) * 2
    can_go_off = (has_tutor or has_tendrils) and proj_mana >= 4 and (
        proj_damage >= max(10, opponent.life - 4) or  # within 4 life of lethal
        player.life <= 8 or storm_potential >= 6     # or have huge storm
    )
    if not can_go_off:
        # Not going off this turn — just play land (handled by protagonist_turn), pass
        gs.state_based_actions()
        return

    def cast_spell(card, cost, label):
        nonlocal storm, mana
        player.remove_from_hand(card)
        player.add_to_grave(card)
        mana -= cost
        storm += 1
        log_fn(f"{label} (mana={mana}, storm={storm})")

    def cast_spell_exile(card, label):
        nonlocal storm, mana
        player.remove_from_hand(card)
        player.exile.append(card)
        mana += 1
        storm += 1
        log_fn(f"{label} (mana={mana}, storm={storm})")

    # ── Step 1: Lotus Petals (free +1 mana each) ─────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        cast_spell_exile(petal, "Lotus Petal")

    # ── Step 2: Chrome Mox (exile cantrip/ritual for +1 mana) ────────────────
    for mox in [c for c in player.hand if c.tag == 'chrome_mox']:
        pitch = next((c for c in player.hand
                      if c is not mox and not c.is_land()
                      and c.tag not in ('chrome_mox','tendrils','infernal','burning_wish','led')
                      and c.colors), None)
        if pitch:
            player.remove_from_hand(mox); player.put_artifact_in_play(mox)
            player.remove_from_hand(pitch); player.exile.append(pitch)
            mana += 1; storm += 1
            log_fn(f"Chrome Mox (exile {pitch.name}) → +1 mana={mana} storm={storm}")
            break  # one Mox at a time

    # ── Step 2b: Brainstorm/Ponder — cast BEFORE combo for storm count ──────────
    if can_go_off:
        for bs in [c for c in player.hand if c.tag in ('bs','ponder') and mana >= 1]:
            player.remove_from_hand(bs); player.add_to_grave(bs)
            mana -= 1; storm += 1
            drawn = player.draw(1)
            log_fn(f"{bs.name} (storm={storm})")
            from engine import bowmasters_triggers
            bowmasters_triggers(1, gs, log_entries, controller='o' if player is gs.bug else 'b')
            break  # one cantrip per turn is enough

    # ── Step 3: Gitaxian Probe (free, draw + storm) ───────────────────────────
    probe = player.find_tag('probe')
    if probe:
        player.remove_from_hand(probe); player.add_to_grave(probe)
        player.life -= 2
        player.draw(1)
        storm += 1
        log_fn(f"Gitaxian Probe (−2 life, {player.life}) storm={storm}")
        bowmasters_triggers(1, gs, log_entries, controller='o' if player is gs.bug else 'b')
        gs.check_life_totals()

    # ── Step 4: Dark Rituals (spend 1B, add 3B = +2 net) ─────────────────────
    if mana >= 1:
        for rit in [c for c in player.hand if c.tag == 'darkrit']:
            if mana >= 1:
                cast_spell(rit, 1, f"Dark Ritual +2")
                mana += 2  # net effect after cost already deducted

    # ── Step 5: Veil of Summer (protect combo if opp has open mana) ──────────
    vos = player.find_tag('vos')
    opp_has_counters = any(c.tag in ('fow','fon','daze','fluster') for c in opponent.hand)
    opp_mana_up = sum(1 for l in opponent.lands if not l.tapped)
    if vos and mana >= 1 and opp_has_counters and not getattr(gs, 'veil_active', False):
        player.remove_from_hand(vos); player.add_to_grave(vos)
        gs.veil_active = True
        mana -= 1; storm += 1
        log_fn(f"★ Veil of Summer — spells uncounterable (storm={storm})", True)

    # ── Step 6: Burning Wish → Tendrils from sideboard ───────────────────────
    wish = player.find_tag('burning_wish')
    safe = getattr(gs, 'veil_active', False) or opp_mana_up == 0 or gs.turn >= 2 or player.life <= 6
    if wish and mana >= 2 and safe:
        # Crack LED in response — but only if resulting Tendrils will be lethal
        led = player.find_tag('led')
        # After LED: storm includes petal+chrome+probe+veil+ritual+led+wish+tendrils
        storm_after_led = storm + 1 + 1 + 1  # +LED, +Wish, +Tendrils
        led_damage = (storm_after_led + 1) * 2
        if led and (led_damage >= opponent.life or storm_after_led >= 5 or player.life <= 8):
            player.remove_from_hand(led); player.exile.append(led)
            # Discard rest of hand (LED's cost, paid before Wish resolves)
            discarded = [c for c in player.hand if c is not wish]
            for c in discarded:
                player.remove_from_hand(c); player.graveyard.append(c)
            mana += 3; storm += 1
            log_fn(f"★ LED cracked — +3 mana={mana}, hand discarded, storm={storm}", True)

        player.remove_from_hand(wish); player.add_to_grave(wish)
        mana -= 2; storm += 1
        # Smart target: Tendrils (lethal) or Empty the Warrens (vs fair decks)
        matchup = getattr(gs, 'matchup', '')
        fair_non_blue = matchup in ('mardu','dnt','boros','eldrazi','mono_black','prison','lands')
        proj_damage = (storm + 2) * 2  # after Wish + Tendrils
        use_empty = fair_non_blue and storm >= 3 and proj_damage < opponent.life
        if use_empty:
            empty_card = sorcery('Empty the Warrens', 4, {'R':1,'generic':3}, {'R'},
                                 tag='empty', win_condition=True)
            player.hand.append(empty_card)
            log_fn(f"Burning Wish → Empty the Warrens (storm={storm})", True)
        else:
            tens = (next((c for c in player.library if c.tag == 'tendrils'), None) or
                    sorcery('Tendrils of Agony', 4, {'B':2,'generic':2}, {'B'},
                            tag='tendrils', win_condition=True, is_combo_piece=True))
            if tens in player.library: player.library.remove(tens)
            player.hand.append(tens)
            log_fn(f"Burning Wish → Tendrils (storm={storm}, mana={mana})", True)

    # ── Step 7: Infernal Tutor (hellbent = hand empty) ───────────────────────
    infernal = player.find_tag('infernal')
    hellbent = len(player.hand) <= 1  # only Tendrils left counts as near-hellbent
    if infernal and mana >= 2 and hellbent and not player.find_tag('tendrils'):
        if not _try_counter_any(player, opponent, gs, infernal, log_entries):
            player.remove_from_hand(infernal); player.add_to_grave(infernal)
            mana -= 2; storm += 1
            tens = (next((c for c in player.library if c.tag == 'tendrils'), None) or
                    sorcery('Tendrils of Agony', 4, {'B':2,'generic':2}, {'B'},
                            tag='tendrils', win_condition=True, is_combo_piece=True))
            if tens in player.library: player.library.remove(tens)
            player.hand.append(tens)
            log_fn(f"Infernal Tutor (hellbent) → Tendrils storm={storm}", True)

    # ── Step 8: Fire Tendrils when lethal ────────────────────────────────────
    tendrils = player.find_tag('tendrils')
    damage   = (storm + 1) * 2   # each copy drains 2
    # Fire only when lethal: (storm+1)*2 >= opp life, or storm>=9 (should be ~18 damage)
    if tendrils and mana >= 4 and (damage >= opponent.life or storm >= 9):
        if not _try_counter_any(player, opponent, gs, tendrils, log_entries):
            player.remove_from_hand(tendrils); player.add_to_grave(tendrils)
            storm += 1
            final_damage = (storm + 1) * 2
            opponent.life -= final_damage
            player.life   += final_damage
            log_fn(f"★ Tendrils — storm {storm}, {final_damage} damage, opp at {opponent.life}", True)
            if opponent.life <= 0:
                gs.game_over = True
                gs.winner    = 'bug' if player is gs.bug else 'opp'
                gs.win_reason = f"TES: Tendrils storm={storm} deals {final_damage}"
                gs.kill_turn  = gs.turn
            else:
                gs.check_life_totals()
        else:
            player.add_to_grave(tendrils)
            log_fn("Tendrils countered")
    elif tendrils and mana >= 4 and storm >= 9:
        # Fire anyway if storm is high even if not technically lethal — real players do this
        if not _try_counter_any(player, opponent, gs, tendrils, log_entries):
            player.remove_from_hand(tendrils); player.add_to_grave(tendrils)
            storm += 1
            final_damage = (storm + 1) * 2
            opponent.life -= final_damage; player.life += final_damage
            log_fn(f"★ Tendrils — storm {storm}, {final_damage} damage, opp at {opponent.life}", True)
            gs.check_life_totals()
            if opponent.life <= 0:
                gs.game_over = True; gs.winner = 'bug' if player is gs.bug else 'opp'
                gs.win_reason = f"TES: Tendrils storm={storm}"; gs.kill_turn = gs.turn

    # ── Alternate win: Empty the Warrens → 2N Goblin tokens ─────────────
    # Use when storm is high but damage not lethal (vs high life totals)
    empty = player.find_tag('empty')
    if not gs.game_over and empty and mana >= 4 and storm >= 4:
        if not _try_counter_any(player, opponent, gs, empty, log_entries):
            player.remove_from_hand(empty); player.add_to_grave(empty)
            storm += 1
            token_count = (storm + 1) * 2  # 2 tokens per copy
            log_fn(f"★ Empty the Warrens — storm {storm}, {token_count} Goblins", True)
            # Model: with 8+ goblins opponents die in 1-2 attacks
            if token_count >= 8:
                gs.game_over = True
                gs.winner = 'bug' if player is gs.bug else 'opp'
                gs.win_reason = f"TES: Empty the Warrens ({token_count} goblins)"
                gs.kill_turn = gs.turn + 1  # attacks next turn
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
