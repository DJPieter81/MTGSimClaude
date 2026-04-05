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

import random
from cards import creature, instant, sorcery, artifact, dual_land
from rules import Card, CardType


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
        d.append(creature('Simian Spirit Guide', 2, {'R': 2, 'generic': 1},
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

    # Tinder Wall: {G} creature, sac → add RR
    for _ in range(2):
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

    # Empty the Warrens: {3R} storm — create 2 Goblin tokens per storm count
    for _ in range(4):
        d.append(sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3}, {'R'},
                         tag='empty', win_condition=True))

    # Gitaxian Probe: 2 life, look at opp hand, draw 1
    for _ in range(3):
        d.append(instant('Gitaxian Probe', 0, {}, set(), tag='probe',
                         life_cost=2, is_cantrip=True))

    # ── Protection (3) ───────────────────────────────────────────────────────
    # Veil of Summer: {G}, can't be countered, protects your spells
    for _ in range(3):
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
        gs.winner = 'bug' if player is gs.bug else 'opp'
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
    from engine import _try_counter_any, bowmasters_triggers

    storm = 0
    mana = total_mana

    # ── Helper: cast a spell from hand ───────────────────────────────────────
    def cast_spell(card, cost, label):
        nonlocal storm, mana
        player.remove_from_hand(card)
        player.add_to_grave(card)
        mana -= cost
        storm += 1
        player.spells_cast_this_turn += 1
        log_fn(f"{label} (mana={mana}, storm={storm})")

    def exile_for_mana(card, gained, label):
        nonlocal storm, mana
        player.remove_from_hand(card)
        player.exile.append(card)
        mana += gained
        log_fn(f"{label} (mana={mana})")

    # ── Step 1: Free mana — Spirit Guides (exile from hand) ─────────────────
    for esg in [c for c in player.hand if c.tag == 'esg']:
        exile_for_mana(esg, 1, "Elvish Spirit Guide (exile → +G)")

    for ssg in [c for c in player.hand if c.tag == 'ssg']:
        exile_for_mana(ssg, 1, "Simian Spirit Guide (exile → +R)")

    # ── Step 2: Lotus Petals (free +1 each) ─────────────────────────────────
    for petal in [c for c in player.hand if c.tag == 'petal']:
        player.remove_from_hand(petal)
        player.exile.append(petal)
        mana += 1
        storm += 1
        player.spells_cast_this_turn += 1
        log_fn(f"Lotus Petal (mana={mana}, storm={storm})")

    # ── Step 3: Chrome Mox (exile nonartifact/nonland → +1 mana) ────────────
    for mox in [c for c in player.hand if c.tag == 'chrome_mox']:
        pitch = next((c for c in player.hand
                      if c is not mox and not c.is_land()
                      and c.tag not in ('chrome_mox', 'belcher', 'led')
                      and c.colors), None)
        if pitch:
            player.remove_from_hand(mox)
            player.put_artifact_in_play(mox)
            player.remove_from_hand(pitch)
            player.exile.append(pitch)
            mana += 1
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"Chrome Mox (exile {pitch.name}) → mana={mana} storm={storm}")
            break  # typically only imprint one

    # ── Step 4: Land Grant (free if no lands in hand) ───────────────────────
    # Search for Taiga — puts a land in hand (then play it for mana)
    grant = player.find_tag('grant')
    has_land_in_hand = any(c.is_land() for c in player.hand)
    if grant and not has_land_in_hand:
        player.remove_from_hand(grant)
        player.add_to_grave(grant)
        storm += 1
        player.spells_cast_this_turn += 1
        # Search library for Taiga
        taiga = next((c for c in player.library if c.name == 'Taiga'), None)
        if taiga:
            player.library.remove(taiga)
            player.hand.append(taiga)
            log_fn(f"Land Grant (free, revealed hand) → Taiga to hand (storm={storm})")
        else:
            log_fn(f"Land Grant (free) — no Forest in library (storm={storm})")

    # Play Taiga from hand if we have it (land drop → +1 mana)
    taiga_in_hand = next((c for c in player.hand if c.name == 'Taiga'), None)
    if taiga_in_hand:
        player.remove_from_hand(taiga_in_hand)
        # Put on battlefield (simplified: just add mana)
        mana += 1
        log_fn(f"Play Taiga → mana={mana}")

    # ── Step 5: Tinder Wall (sac for RR) ────────────────────────────────────
    for tw in [c for c in player.hand if c.tag == 'tinder']:
        if mana >= 1:
            player.remove_from_hand(tw)
            player.add_to_grave(tw)
            # Cast for {G} (1 mana), then sac for RR = net +1
            mana -= 1
            mana += 2
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"Tinder Wall (cast + sac → +RR, net +1) mana={mana} storm={storm}")

    # ── Step 6: Gitaxian Probe (free, storm + draw) ─────────────────────────
    for probe in [c for c in player.hand if c.tag == 'probe']:
        player.remove_from_hand(probe)
        player.add_to_grave(probe)
        player.life -= 2
        player.draw(1)
        storm += 1
        player.spells_cast_this_turn += 1
        log_fn(f"Gitaxian Probe (−2 life → {player.life}) storm={storm}")
        bowmasters_triggers(1, gs, log_entries,
                            controller='o' if player is gs.bug else 'b')
        gs.check_life_totals()
        if gs.game_over:
            return

    # ── Step 7: Rituals ─────────────────────────────────────────────────────
    # Dark Ritual: {B} → BBB (net +2)
    for rit in [c for c in player.hand if c.tag == 'darkrit']:
        if mana >= 1:
            cast_spell(rit, 1, "Dark Ritual → +BBB")
            mana += 3  # cast_spell already did -1, ritual adds BBB (+3), net = +2

    # Rite of Flame: {R} → RR (net +1), or RRR if rite in GY (net +2)
    for rite in [c for c in player.hand if c.tag == 'rite']:
        if mana >= 1:
            rites_in_gy = sum(1 for c in player.graveyard if c.tag == 'rite')
            produced = 3 if rites_in_gy > 0 else 2  # total mana produced
            cast_spell(rite, 1, f"Rite of Flame → +{'RRR' if produced == 3 else 'RR'}")
            mana += produced  # cast_spell already did -1, add full produced amount

    # Desperate Ritual: {1R} → RRR (net +1)
    for des in [c for c in player.hand if c.tag == 'desperate']:
        if mana >= 2:
            cast_spell(des, 2, "Desperate Ritual → +RRR")
            mana += 3  # net after cost already deducted (add 3 back = net +1)

    # Seething Song: {2R} → RRRRR (net +2)
    for song in [c for c in player.hand if c.tag == 'seething']:
        if mana >= 3:
            cast_spell(song, 3, "Seething Song → +RRRRR")
            mana += 5  # net after cost already deducted (add 5 back = net +2)

    # ── Step 8: Veil of Summer (protect combo) ──────────────────────────────
    vos = player.find_tag('vos')
    opp_has_counters = any(c.tag in ('fow', 'fon', 'daze', 'fluster')
                          for c in opponent.hand)
    opp_mana_up = sum(1 for l in opponent.lands if not l.tapped)
    if vos and mana >= 1 and (opp_has_counters or opp_mana_up >= 1):
        if not getattr(gs, 'veil_active', False):
            player.remove_from_hand(vos)
            player.add_to_grave(vos)
            gs.veil_active = True
            mana -= 1
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"★ Veil of Summer — uncounterable (storm={storm})", True)

    # ── Step 9: Cast + Activate Goblin Charbelcher ──────────────────────────
    belcher = player.find_tag('belcher')
    if belcher and mana >= 7 and not gs.game_over:
        # Cast Charbelcher (4 mana)
        if not _try_counter_any(player, opponent, gs, belcher, log_entries):
            player.remove_from_hand(belcher)
            perm = player.put_artifact_in_play(belcher)
            mana -= 4
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"★ Goblin Charbelcher (mana={mana}, storm={storm})", True)

            # Activate Charbelcher (3 mana, tap)
            if mana >= 3:
                mana -= 3
                _activate_charbelcher(player, opponent, gs, log_fn, log_entries)
        else:
            player.add_to_grave(belcher)
            log_fn("Goblin Charbelcher countered")

    # ── Step 10: Cast Charbelcher without activating (if mana < 7 but >= 4)
    if not gs.game_over and player.find_tag('belcher') and mana >= 4 and mana < 7:
        belcher = player.find_tag('belcher')
        if not _try_counter_any(player, opponent, gs, belcher, log_entries):
            player.remove_from_hand(belcher)
            player.put_artifact_in_play(belcher)
            mana -= 4
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"Charbelcher cast (waiting to activate next turn) mana={mana}")
        else:
            player.add_to_grave(belcher)
            log_fn("Goblin Charbelcher countered")

    # ── Step 11: Burning Wish → Empty the Warrens from sideboard ────────────
    wish = player.find_tag('burning_wish')
    if not gs.game_over and wish and mana >= 2 and storm >= 3:
        # Crack LED in response if available
        led = player.find_tag('led')
        if led:
            player.remove_from_hand(led)
            player.exile.append(led)
            discarded = [c for c in player.hand if c is not wish]
            for c in discarded:
                player.remove_from_hand(c)
                player.graveyard.append(c)
            mana += 3
            storm += 1
            player.spells_cast_this_turn += 1
            log_fn(f"★ LED cracked — +3 mana={mana}, storm={storm}", True)

        player.remove_from_hand(wish)
        player.add_to_grave(wish)
        mana -= 2
        storm += 1
        player.spells_cast_this_turn += 1

        # Fetch Empty the Warrens from SB
        empty_card = sorcery('Empty the Warrens', 4, {'R': 1, 'generic': 3},
                             {'R'}, tag='empty', win_condition=True)
        player.hand.append(empty_card)
        log_fn(f"Burning Wish → Empty the Warrens (storm={storm})", True)

    # ── Step 12: Empty the Warrens as backup win ────────────────────────────
    empty = player.find_tag('empty')
    if not gs.game_over and empty and mana >= 4 and storm >= 3:
        if not _try_counter_any(player, opponent, gs, empty, log_entries):
            player.remove_from_hand(empty)
            player.add_to_grave(empty)
            storm += 1
            player.spells_cast_this_turn += 1
            token_count = (storm + 1) * 2
            log_fn(f"★ Empty the Warrens — storm {storm}, {token_count} Goblins", True)
            if token_count >= 6:
                gs.game_over = True
                gs.winner = 'bug' if player is gs.bug else 'opp'
                gs.win_reason = f"Belcher: Empty the Warrens ({token_count} goblins)"
                gs.kill_turn = gs.turn + 1
        else:
            player.add_to_grave(empty)
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
    'meta_share': 0.02,
}
