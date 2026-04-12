"""
Eldrazi Aggro — Legacy colorless aggro/lock deck.

Game plan: T1 Chalice on 1 (via Tomb/City), then deploy undercosted
Eldrazi threats (Temple gives +1 for Eldrazi spells). Cavern of Souls
makes creatures uncounterable. One Ring for protection + draw.

Key interactions:
- Chalice on 1: blanks Brainstorm, Ponder, Fatal Push, Daze, Thoughtseize
- Ancient Tomb: 2 colorless for 2 life
- Eldrazi Temple: +1 for Eldrazi creature spells
- Cavern of Souls: Eldrazi creatures can't be countered
- Simian Spirit Guide: exile from hand for +1 mana
- The One Ring: indestructible, protection on ETB, escalating draw
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cards import make_eldrazi_deck


def _eldrazi_effective_mana(player, base_mana, for_eldrazi=False):
    """Calculate effective mana including sol lands, Temple, and SSG."""
    extra = 0
    for l in player.lands:
        if l.card.tag == 'tomb' and not l.tapped:
            extra += 1  # Tomb produces 2, base counts 1
        elif l.card.tag == 'city' and not l.tapped:
            extra += 1  # City produces 2, base counts 1
        elif l.card.tag == 'temple' and not l.tapped and for_eldrazi:
            extra += 1  # Temple gives +1 for Eldrazi spells only
    ssg_count = sum(1 for c in player.hand if c.tag == 'ssg')
    return base_mana + extra, ssg_count


def _strategy_eldrazi(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Eldrazi Aggro — lock + undercosted threats.

    Priority:
    1. Chalice on 1 (blanks half of BUG's deck)
    2. The One Ring (protection + draw engine)
    3. TKS (hand disruption — exile their FoW)
    4. Deploy Eldrazi threats (Temple discount, Cavern uncounterable)
    5. Kozilek's Command (removal + tokens)
    6. Wasteland opponent's duals
    7. Attack with everything
    """
    from engine import _try_counter_any, combat_declare, update_goyf
    from rules import MTGRules
    import random

    mana, ssg_avail = _eldrazi_effective_mana(player, total_mana)

    # ── Track persistent effects ──
    if not hasattr(gs, 'eldrazi_ring_turns'):
        gs.eldrazi_ring_turns = 0

    # One Ring ongoing draw (escalating each turn)
    if gs.eldrazi_ring_turns > 0:
        gs.eldrazi_ring_turns += 1
        draws = min(gs.eldrazi_ring_turns, 3)
        player.draw(draws)
        player.life -= draws
        log_fn(f"The One Ring — draw {draws}, lose {draws} life ({player.life})")
        gs.check_life_totals()
        if gs.game_over:
            return

    # Helpers
    def crack_ssg():
        nonlocal mana, ssg_avail
        ssg = player.find_tag('ssg')
        if ssg and ssg_avail > 0:
            player.remove_from_hand(ssg)
            player.exile.append(ssg)
            mana += 1
            ssg_avail -= 1
            log_fn("SSG → +1 mana")
            return True
        return False

    def crack_petal():
        nonlocal mana
        petal = player.find_tag('petal')
        if petal:
            player.remove_from_hand(petal)
            player.add_to_grave(petal)
            mana += 1
            log_fn("Lotus Petal → +1 mana")
            return True
        return False

    has_cavern = any(l.card.tag == 'cavern' for l in player.lands)

    def try_cast(card, cost, is_creature=True):
        nonlocal mana
        player.remove_from_hand(card)
        # Cavern makes Eldrazi creatures uncounterable
        if is_creature and has_cavern:
            player.put_creature_in_play(card)
            mana -= cost
            log_fn(f"{card.name} ({card.base_power}/{card.base_toughness}) [Cavern — uncounterable]")
            return True
        if not _try_counter_any(player, opponent, gs, card, log_entries):
            if is_creature:
                player.put_creature_in_play(card)
            else:
                player.add_to_grave(card)
            mana -= cost
            log_fn(f"{card.name}")
            return True
        else:
            player.add_to_grave(card)
            mana -= cost
            return False

    # ── 1. Chalice on 1 (highest priority) ───────────────────────────────
    ch = player.find_tag('chalice')
    if ch and gs.chalice_x is None:
        while mana < 2:
            if not crack_petal() and not crack_ssg():
                break
        if mana >= 2:
            player.remove_from_hand(ch)
            if not _try_counter_any(player, opponent, gs, ch, log_entries):
                player.put_artifact_in_play(ch)
                gs.chalice_x = 1
                mana -= 2
                log_fn("★ Chalice on 1 — blanks Push, Brainstorm, Ponder, Daze", True)
            else:
                player.add_to_grave(ch)
                mana -= 2

    # ── 2. The One Ring (4 mana) ─────────────────────────────────────────
    ring = player.find_tag('ring')
    if ring and gs.eldrazi_ring_turns == 0:
        while mana < 4:
            if not crack_petal() and not crack_ssg():
                break
        if mana >= 4:
            player.remove_from_hand(ring)
            if not _try_counter_any(player, opponent, gs, ring, log_entries):
                player.add_to_grave(ring)
                mana -= 4
                gs.eldrazi_ring_turns = 1
                player.life += 5  # protection proxy
                log_fn("★ The One Ring — protection + draw engine", True)
            else:
                player.add_to_grave(ring)
                mana -= 4

    # ── 3. TKS (4 mana with Temple discount = 3) ────────────────────────
    tks = player.find_tag('tks')
    if tks:
        eldrazi_mana = max(mana, _eldrazi_effective_mana(player, total_mana, True)[0])
        while eldrazi_mana < 4:
            if not crack_ssg():
                break
            eldrazi_mana = max(mana, _eldrazi_effective_mana(player, total_mana, True)[0])
        if eldrazi_mana >= 4:
            if try_cast(tks, min(4, mana)):
                # ETB: exile best nonland
                nonlands = [c for c in opponent.hand if not c.is_land()]
                if nonlands:
                    prio = {'fow': 0, 'fon': 0, 'daze': 1, 'bowm': 2, 'murk': 3}
                    target = min(nonlands, key=lambda c: prio.get(c.tag, 5))
                    opponent.hand.remove(target)
                    opponent.exile.append(target)
                    log_fn(f"  TKS exiles {target.name}", True)

    # ── 4. Deploy remaining Eldrazi ──────────────────────────────────────
    for _ in range(4):
        eldrazi_mana = max(mana, _eldrazi_effective_mana(player, total_mana, True)[0])
        affordable = [c for c in player.hand if c.is_creature() and c.cmc <= eldrazi_mana]
        if not affordable:
            break
        threat = max(affordable, key=lambda c: c.base_power)
        cost = min(threat.cmc, mana)  # Temple discount means effective cost may be lower
        try_cast(threat, cost)
        if gs.game_over:
            return

    # ── 5. Kozilek's Command (3 mana) ────────────────────────────────────
    kcmd = player.find_tag('kcommand')
    if kcmd and mana >= 3:
        player.remove_from_hand(kcmd)
        if not _try_counter_any(player, opponent, gs, kcmd, log_entries):
            player.add_to_grave(kcmd)
            mana -= 3
            small = [c for c in opponent.creatures if c.toughness <= 3]
            if small:
                target = max(small, key=lambda c: c.power)
                opponent.creatures.remove(target)
                log_fn(f"Kozilek's Command — kill {target.card.name} + Spawn", True)
                update_goyf(gs)
            else:
                player.draw(2)
                log_fn("Kozilek's Command — draw 2")
        else:
            player.add_to_grave(kcmd)
            mana -= 3

    # ── 6. Wasteland ────────────────────────────────────────────────────
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl and len(player.lands) >= 3:
        targets = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if targets:
            target = max(targets, key=lambda l: 3 if l.card.tag == 'dual' else 2 if l.is_fetch else 1)
            player.lands.remove(wl)
            player.add_to_grave(wl.card)
            opponent.lands.remove(target)
            opponent.add_to_grave(target.card)
            log_fn(f"Wasteland → {target.card.name}")
            update_goyf(gs)

    # ── 7. Combat ───────────────────────────────────────────────────────
    attackers = [c for c in player.creatures if not c.summoning_sick]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()


def _keep_eldrazi(hand, matchup=''):
    """Eldrazi keeps hands with fast mana + lock or threat."""
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    tags = {c.tag for c in hand}
    lock = any(t in tags for t in ('chalice', 'ring'))
    thr = sum(1 for c in nonlands if c.is_creature())
    fast = any(c.tag in ('tomb', 'city', 'temple') for c in lands)
    ssg = 'ssg' in tags
    petal = 'petal' in tags
    has_mana = fast or ssg or petal
    if len(hand) <= 5:
        return (lc >= 1 or has_mana) and (lock or thr >= 1)
    return lc >= 1 and has_mana and (lock or thr >= 1)


def test_eldrazi():
    results = []
    deck = make_eldrazi_deck()
    assert len(deck) == 60
    results.append("OK  Deck size = 60")
    return results


DECK_META = {
    'key':        'eldrazi',
    'name':       'Eldrazi Aggro',
    'make_deck':  make_eldrazi_deck,
    'strategy':   _strategy_eldrazi,
    'keep':       _keep_eldrazi,
    'categories': {'aggro'},
    'interaction': {'speed': 3, 'resilience': 4, 'uses_graveyard': False,
                    'uses_veil': False, 'soft_to_wasteland': False,
                    'creature_based': True},
    'meta_share': 0.02,
}
