"""
engine.py — Turn execution v2.

v2 fixes applied:
  C1  Every spell cast now checks mana availability and pays the cost.
  C2  Attacking creatures are tapped via MTGRules.tap_attacker().
  S3  Blood Moon: set_moon() propagates to all lands; they only produce R.
  S4  Back to Basics: set_b2b() propagates; nonbasic lands don't untap.
  S5  Force of Negation free only on opponent's turn.
  L1  STP life gain: only power (not 3+power).
  L2  Dismember: checks 1 mana available before casting.
  L3  Dismember: only kills if toughness - 5 <= 0.
  L4  Blocker deals damage back to attacking creature.
"""

import random
from typing import List, Optional
from rules import (Card, CardType, Permanent, LandPermanent, ManaPool,
                   StackObject, StackType, MTGRules)
from game import GameState, PlayerState, LogEntry, can_afford, tap_for_cost
from cards import DECKS, artifact, creature
from gameplan import GAMEPLANS, assess, active_goal, Goal
from interaction import (best_reactive_answer, best_proactive_target,
                         should_push_now, classify_threat, ThreatLevel)
from config import (CardRoles as CR, MatchupCategory as MC, InteractionParams as IP,
                    GameRules as GR, CombatThresholds as CT, CounterLogic as CL)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

# Shared token prototype — avoids repeated Card() construction in hot loops
_MONK_TOKEN = Card(name='Monk Token', card_type=CardType.CREATURE, cmc=0,
                   mana_cost={}, colors=set(), tag='monk_token',
                   base_power=1, base_toughness=1, gy_type='creature')

_ORC_ARMY_PROTO = Card(name='Orc Army', card_type=CardType.CREATURE, cmc=0,
                       mana_cost={}, colors=set(), tag='orc_army',
                       base_power=0, base_toughness=0, gy_type='creature')


def _select_attackers(player, opponent, hold_tags=CT.HOLD_ATTACK_TAGS, desperate_life=CT.DESPERATE_LIFE):
    """Shared attacker selection for aggro/midrange strategies.
    Returns list of creatures to attack with. Holds back value engines and 0-power."""
    opp_has_blockers = len(opponent.creatures) > 0
    desperate = player.life < desperate_life
    attackers = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.power == 0: continue
        if c.card.tag in hold_tags and opp_has_blockers and not desperate:
            continue
        attackers.append(c)
    return attackers


def _check_tamiyo_flip(gs, player, log):
    """Check if Tamiyo should flip (drew 3+ cards this turn)."""
    tam_perm = next((c for c in player.creatures if c.card.tag == 'tamiyo'), None)
    if tam_perm and not gs.tamiyo_flipped and not tam_perm.tapped:
        if player.draws_this_turn >= 3:
            gs.tamiyo_flipped = True
            tam_perm.power_mod = 3
            tam_perm.toughness_mod = 0
            log("★ Tamiyo flips → Tamiyo, Seasoned Scholar (drew 3rd card this turn)", key=True)


def _deduct(budget: list, cmc: int, card) -> bool:
    """Spend mana from budget. Returns True (cost always 0 for free spells)."""
    budget[0] = max(0, budget[0] - max(0, cmc))
    return True


class ManaManager:
    """Unified mana budget tracker for strategies.

    Replaces the three divergent patterns:
      - Pattern A: budget = [total_mana] + _deduct(budget, cost, card)
      - Pattern B: rem = total_mana + rem -= cost
      - Pattern C: mana_ref = [total_mana] + custom spend functions

    Usage in a strategy:
        mm = ManaManager(total_mana, gs, log_fn)
        if mm.can_pay(card.cmc):
            mm.spend(card)
            ...
        remaining = mm.available
    """

    def __init__(self, total_mana: int, gs: 'GameState', log_fn=None):
        self.mana = total_mana
        self.gs = gs
        self.log_fn = log_fn

    @property
    def available(self) -> int:
        return self.mana

    def can_pay(self, cost: int) -> bool:
        return self.mana >= cost

    def spend(self, card) -> None:
        """Deduct effective cost (respects Trinisphere/Thalia) and fire Eidolon."""
        cost = self.effective_cmc(card)
        self.mana = max(0, self.mana - cost)
        _eidolon_trigger(self.gs, card, self.log_fn)

    def spend_amount(self, amount: int) -> None:
        """Deduct a raw mana amount (for activated abilities, generic costs)."""
        self.mana = max(0, self.mana - amount)

    def effective_cmc(self, card) -> int:
        """Card's effective cost accounting for Trinisphere and Thalia."""
        base = max(card.cmc, 3 if self.gs.trinisphere_active else 0)
        if not card.is_creature() and self.gs.thalia_on_board:
            base += 1
        return base

    def refresh(self, player) -> None:
        """Refresh mana from current board state (e.g. after land drop)."""
        self.mana = player.available_mana_count()


def assess_board(player, opponent):
    """Shared board state assessment for tempo/midrange strategies.

    Returns (state, metrics) where state is one of:
      'racing'  — both players threaten lethal in ≤3 turns
      'ahead'   — player has board advantage
      'behind'  — opponent has board advantage
      'parity'  — roughly even

    Metrics dict contains: board_power, opp_power, threat_count, opp_threats,
    turns_to_kill, turns_to_die, has_threats_in_hand.
    """
    board_power  = sum(c.power for c in player.creatures)
    opp_power    = sum(c.power for c in opponent.creatures)
    threat_count = len(player.creatures)
    opp_threats  = len(opponent.creatures)
    ttk = (opponent.life / board_power) if board_power > 0 else 999
    ttd = (player.life / opp_power)    if opp_power > 0 else 999
    has_threats  = any(c.is_creature() for c in player.hand)

    if ttk <= 3 and ttd <= 3:
        state = 'racing'
    elif board_power > opp_power + 2 or threat_count > opp_threats + 1:
        state = 'ahead'
    elif opp_power > board_power + 2 or opp_threats > threat_count + 1:
        state = 'behind'
    else:
        state = 'parity'

    metrics = {
        'board_power': board_power, 'opp_power': opp_power,
        'threat_count': threat_count, 'opp_threats': opp_threats,
        'turns_to_kill': ttk, 'turns_to_die': ttd,
        'has_threats': has_threats,
    }
    return state, metrics


# ─────────────────────────────────────────────────────────────────────
# Shared lock/tax enforcement — used by protagonist_turn & opp_turn
# ─────────────────────────────────────────────────────────────────────
# These ensure every tax/lock effect is enforced in ONE place, preventing
# the asymmetry bugs where an effect works in one turn function but not
# another (see: Thalia fix, Eidolon fix, Trinisphere lesson).

def apply_lock_effects(gs, player, log):
    """Pre-strategy: apply continuous cost effects (Omniscience, Chalice, Trinisphere, Thalia).
    Returns a dict of adjustments to pass to restore_lock_effects().
    """
    hand = player.hand
    adjustments = {'chalice': [], 'trini': [], 'thalia': [], 'omni': []}

    # Omniscience: all spells cost 0 (CR 601.2f alternative cost)
    # Must come BEFORE Trinisphere — Omni sets to 0, Trini overrides to 3
    if getattr(gs, 'omniscience_active', False):
        for card in hand:
            if not card.is_land():
                adjustments['omni'].append((card, card.cmc))
                card.cmc = 0
        if adjustments['omni']:
            log(f"Omniscience active — {len(adjustments['omni'])} spells cost 0")

    # Chalice of the Void: remove spells with CMC == chalice_x from hand
    if gs.chalice_x is not None:
        for card in list(hand):
            if not card.is_land() and card.cmc == gs.chalice_x:
                adjustments['chalice'].append(card)
                hand.remove(card)
        if adjustments['chalice']:
            log(f"Chalice on {gs.chalice_x} — blocks: {', '.join(set(c.name for c in adjustments['chalice']))}")

    # Trinisphere: all spells cost at least 3 (CR 601.2f)
    if gs.trinisphere_active:
        for card in hand:
            if not card.is_land() and card.cmc < 3:
                adjustments['trini'].append((card, card.cmc))
                card.cmc = 3
        if adjustments['trini']:
            log(f"Trinisphere active — {len(adjustments['trini'])} spells taxed to 3 mana")

    # Thalia, Guardian of Thraben: noncreature spells cost +1 (CR 613)
    if gs.thalia_on_board:
        for card in hand:
            if not card.is_land() and not card.is_creature():
                adjustments['thalia'].append((card, card.cmc))
                card.cmc += 1
        if adjustments['thalia']:
            log(f"Thalia tax — {len(adjustments['thalia'])} noncreature spells cost +1")

    return adjustments


def restore_lock_effects(player, adjustments):
    """Post-strategy: restore Chalice-blocked cards and all adjusted CMCs."""
    player.hand.extend(adjustments['chalice'])
    for card, orig_cmc in adjustments.get('omni', []):
        card.cmc = orig_cmc
    for card, orig_cmc in adjustments['thalia']:
        card.cmc = orig_cmc
    for card, orig_cmc in adjustments['trini']:
        card.cmc = orig_cmc


def apply_eidolon_damage(gs, player, spells_before, log):
    """Post-strategy: apply Eidolon of the Great Revel damage for spells cast."""
    if gs.eidolon_active and not gs.game_over:
        spells_cast = player.spells_cast_this_turn - spells_before
        if spells_cast > 0:
            eidolon_dmg = spells_cast * 2
            player.life -= eidolon_dmg
            p_label = 'P1' if player is gs.p1 else 'P2'
            log(f"Eidolon trigger — {spells_cast} spell(s) cast, {eidolon_dmg} damage to {p_label} ({player.life})")
            gs.check_life_totals()


def _check_tamiyo_flip(gs: GameState, player, log_fn) -> None:
    """Oracle: Tamiyo flips when controller draws 3+ cards in a turn.
    Centralised so it works for ALL decks with Tamiyo, not just BUG."""
    tam_perm = next((c for c in player.creatures if c.card.tag == 'tamiyo'), None)
    if tam_perm and not gs.tamiyo_flipped and not tam_perm.tapped:
        if player.draws_this_turn >= 3:
            gs.tamiyo_flipped = True
            tam_perm.power_mod = 3   # flips to Tamiyo, Seasoned Scholar (3/3)
            tam_perm.toughness_mod = 0
            log_fn("★ Tamiyo flips → Tamiyo, Seasoned Scholar (drew 3rd card this turn)", key=True)


def _eidolon_trigger(gs: GameState, card, log_fn, caster=None) -> None:
    """CR 702.2: Eidolon of the Great Revel — whenever ANY player casts a spell with CMC≤3,
    Eidolon deals 2 damage to that spell's caster."""
    if not gs.eidolon_active:
        return
    if card is None or card.cmc > 3:
        return  # Eidolon only triggers on CMC ≤ 3
    # Damage goes to the caster, not always p1
    target = caster if caster is not None else gs.p1
    target.life -= 2
    label = 'P1' if target is gs.p1 else 'P2'
    log_fn(f"Eidolon trigger — {card.name} (CMC {card.cmc}) deals 2 to {label} ({target.life})", True)
    gs.check_life_totals()


def cast_obj(card: Card, controller: str) -> StackObject:
    return StackObject(name=card.name, stack_type=StackType.SPELL,
                       controller=controller, source_card=card,
                       cmc=card.cmc, card_type=card.card_type, colors=card.colors)


# ─── Unified Spell Pipeline ─────────────────────────────────────────────────

def cast_spell(player, opponent, gs, card, mana_budget, log_fn, log_entries,
               on_resolve=None, on_counter=None, cost_override=None) -> bool:
    """THE mandatory spell pipeline.  Every spell cast should go through here.

    Steps:
      1. Remove card from hand        (prevents cast-twice bug)
      2. Increment spells_cast_this_turn (storm count, Eidolon aggregate)
      3. Fire Eidolon trigger          (CMC ≤ 3, fires for ALL players)
      4. Counter window                (_try_counter_any)
      5a. Resolved → deduct mana, call on_resolve(card) if provided
      5b. Countered → card to graveyard, call on_counter(card) if provided

    Args:
        player:        caster PlayerState
        opponent:      defender PlayerState
        gs:            GameState
        card:          Card being cast
        mana_budget:   mutable list[int] — mana_budget[0] is deducted on resolve.
                       Pass None to skip mana deduction (free spells).
        log_fn:        logging function
        log_entries:   list for log messages
        on_resolve:    callable(card) — what to do when spell resolves
                       (e.g. put_creature_in_play, add_to_grave, deal damage).
                       If None, card goes to graveyard by default.
        on_counter:    callable(card) — optional override for counter handling.
                       If None, card goes to graveyard.
        cost_override: int — use instead of card.cmc for mana deduction.

    Returns:
        True if spell resolved, False if countered.
    """
    # Step 1: ALWAYS remove from hand first — prevents cast-twice bug
    player.remove_from_hand(card)

    # Step 2: Increment spell count (for storm, Eidolon aggregate tracking)
    player.spells_cast_this_turn = getattr(player, 'spells_cast_this_turn', 0) + 1

    # Step 3: Counter window (before Eidolon — countered spells shouldn't trigger)
    countered = _try_counter_any(player, opponent, gs, card, log_entries)

    if countered:
        # Step 3b: Countered — card to graveyard, NO Eidolon damage
        if on_counter:
            on_counter(card)
        else:
            player.add_to_grave(card)
        return False

    # Step 4: Eidolon trigger — only on resolved spells (CMC ≤ 3 deals 2 to caster)
    _eidolon_trigger(gs, card, log_fn, caster=player)

    # Step 5: Resolved — deduct mana and call resolution callback
    if mana_budget is not None:
        cost = cost_override if cost_override is not None else card.cmc
        mana_budget[0] = max(0, mana_budget[0] - cost)

    if on_resolve:
        on_resolve(card)
    else:
        player.add_to_grave(card)  # default: instants/sorceries go to GY

    return True


def resolve_cantrip(player, card, gs, log_fn, log_entries):
    """Dispatch cantrip resolution based on card identity.
    Brainstorm = draw 3, put 2 back.  Ponder/Preordain = draw 1.
    Fires bowmasters triggers for each draw."""
    if card.tag == 'bs':
        drawn = player.draw(MTGRules.brainstorm_draws())
        # Put back 2 worst cards (simplified: sort by keep-value)
        if len(player.hand) >= 2:
            from rules import CardType
            def keep_val(c):
                if c.is_land(): return 10  # put back extra lands
                if c.is_cantrip: return 8  # put back redundant cantrips
                return 0  # keep threats, interaction
            worst = sorted(player.hand, key=keep_val, reverse=True)[:2]
            for w in worst:
                player.hand.remove(w)
                player.library.insert(0, w)
        draws = len(drawn)
        log_fn(f"{card.name} ({draws} draw{'s' if draws > 1 else ''})")
    else:
        drawn = player.draw(1)
        log_fn(f"{card.name} (1 draw)")
        draws = 1
    # Fire bowmasters triggers for non-draw-step draws
    bowmasters_triggers(draws, gs, log_entries,
                        controller='o' if player is gs.p1 else 'b')
    player.add_to_grave(card)
    return drawn


# ─── Centralized Damage Router ──────────────────────────────────────────────

def deal_damage(gs, source_tag, target_player, amount, damage_type='normal',
                log_fn=None, source_card=None, attacker_player=None):
    """Centralized damage router.  ALL damage to players goes through here.

    damage_type:
      'normal'  — burn spells, Eidolon, etc.  Reduces life.
      'combat'  — combat damage.  Checks source for infect, routes accordingly.
      'infect'  — infect damage.  Routes to poison counters, not life.
      'loss'    — life loss (Thoughtseize, fetch).  Direct life change, no triggers.

    For 'combat': auto-detects infect on source_card and routes to poison.
    Returns actual damage dealt.
    """
    if amount <= 0:
        return 0

    # Infect routing: combat damage from infect creature → poison
    if damage_type == 'combat' and source_card and getattr(source_card, 'infect', False):
        damage_type = 'infect'

    if damage_type == 'infect':
        # Route to poison counters
        if target_player is gs.p1:
            gs.p1_poison = getattr(gs, 'p1_poison', 0) + amount
            poison = gs.p1_poison
        else:
            gs.p2_poison = getattr(gs, 'p2_poison', 0) + amount
            poison = gs.p2_poison
        if log_fn:
            log_fn(f"★ {source_tag} deals {amount} poison ({poison}/10)")
        if poison >= 10:
            gs.game_over = True
            gs.kill_turn = gs.turn
            gs.winner = 'p2' if target_player is gs.p1 else 'p1'
            gs.win_reason = f"Infect: {poison} poison counters"
            if log_fn:
                log_fn(f"★★★ LETHAL — {poison} poison counters on turn {gs.turn}!", True)
        return amount

    if damage_type == 'loss':
        # Direct life loss (not damage — can't be prevented)
        target_player.life -= amount
        return amount

    # Normal / combat damage — reduce life
    target_player.life -= amount
    gs.check_life_totals()
    return amount


# ─── Mana & Cost Checking ──────────────────────────────────────────────────

def opp_can_cast(card: Card, om: int, gs: GameState, caster=None) -> bool:
    """Single mana+colour gateway for any player casting a spell.
    caster: the PlayerState casting the spell. Defaults to gs.p2 for backward compat.
    Checks: Chalice, Trinisphere, Thalia tax, mana quantity, colour."""
    if gs.spell_blocked_by_chalice(card.cmc):
        return False
    effective = card.cmc
    # Trinisphere: all spells cost at least 3 (CR 601.2f)
    if gs.trinisphere_active:
        effective = max(effective, 3)
    # Thalia: noncreature spells cost +1 (CR 613)
    if gs.thalia_on_board and not card.is_creature():
        effective += 1
    if om < effective:
        return False
    caster = caster if caster is not None else gs.p2
    return can_afford(caster, card.mana_cost)


def _can_target(creature, caster_mana: int) -> bool:
    """Return True if a spell can legally target this creature.

    Checks:
    - Hexproof (CR 702.11b): creature cannot be targeted by opponent spells.
    - Ward (CR 702.143): targeting triggers a ward cost; if the caster can't
      pay the extra mana the spell is countered. We model this as: the spell
      can only target the creature when the caster has enough spare mana to
      cover the ward cost on top of the spell's own cost (already spent).
      caster_mana = mana *remaining after* paying the targeting spell itself.
    """
    if getattr(creature, 'hexproof', False):
        return False
    ward = getattr(creature.card, 'ward', 0)
    if ward and caster_mana < ward:
        return False
    return True


def update_goyf(gs: GameState):
    # Tarmogoyf / Barrowgoyf: P/T = card types in ALL graveyards
    pw, pt = MTGRules.tarmogoyf_pt(gs.p1.graveyard, gs.p2.graveyard)
    # Nethergoyf: P/T = types in CONTROLLER's own GY / same+1 (static ability)

    for c in gs.p1.creatures + gs.p2.creatures:
        if c.card.tag == 'goyf':
            c.power_mod = pw - c.card.base_power
            c.toughness_mod = pt - c.card.base_toughness
        elif c.card.tag == 'barrow':
            # Barrowgoyf: same formula as Tarmogoyf (all GYs)
            c.power_mod = pw - c.card.base_power
            c.toughness_mod = pt - c.card.base_toughness
        elif c.card.tag == 'nether':
            # Nethergoyf Oracle: P/T = */1+* where * = card types in controller's GY.
            # tarmogoyf_pt(gy, []) already returns (types, types+1) — no extra +1 needed.
            if c.controller == 'b':
                n_pw, n_pt = MTGRules.tarmogoyf_pt(gs.p1.graveyard, [])
            else:
                n_pw, n_pt = MTGRules.tarmogoyf_pt(gs.p2.graveyard, [])
            c.power_mod = n_pw - c.card.base_power
            c.toughness_mod = n_pt - c.card.base_toughness


def bowmasters_triggers(n_draws: int, gs: GameState, log_list: List[str],
                        controller: str = 'b'):
    """
    CR 603 — one trigger per draw event (NOT the first draw-step draw).
    Each trigger: deal 1 damage to any target; amass Orcs 1 (grow Orc Army token).
    controller='b': BUG controls Bowmasters (default) — checks gs.p1.creatures, pings gs.p2.
    controller='o': OPP controls Bowmasters — checks gs.p2.creatures, pings gs.p1.
    This allows the function to work when Elves is the protagonist (controller='o').
    """
    # Select which side has Bowmasters and who gets pinged
    if controller == 'b':
        has_bowm = any(c.card.tag == 'bowm' for c in gs.p1.creatures)
        victim = gs.p2
        army_owner = gs.p1
        army_ctrl = 'b'
    else:
        has_bowm = any(c.card.tag == 'bowm' for c in gs.p2.creatures)
        victim = gs.p1
        army_owner = gs.p2
        army_ctrl = 'o'

    if not has_bowm:
        return  # Bowmasters not in play on that side
    triggers = MTGRules.bowmasters_trigger_count(n_draws)
    for i in range(triggers):
        victim.life -= 1
        # Amass Orcs 1: create or grow Orc Army for the Bowmasters controller
        army = next((c for c in army_owner.creatures if c.card.tag == 'orc_army'), None)
        if army is None:
            from rules import Card, CardType, Permanent
            army_card = Card(
                name='Orc Army', card_type=CardType.CREATURE, cmc=0, mana_cost={},
                colors={'B'}, subtypes={'Orc','Army'},
                base_power=0, base_toughness=0, tag='orc_army', gy_type='creature'
            )
            army = Permanent(card=army_card, controller=army_ctrl, summoning_sick=True)
            army_owner.creatures.append(army)
        army.power_mod += 1
        army.toughness_mod += 1
        log_list.append(
            f"  Bowmasters T{i+1}/{triggers}: {victim.name} -{1} life → {victim.life}, "
            f"Orc Army {army.power}/{army.toughness}")
    gs.check_life_totals()



# ─────────────────────────────────────────────
# Combat helper — C2 + L4
# ─────────────────────────────────────────────

def resolve_combat(gs: GameState, attacker_player: PlayerState,
                   defender_player: PlayerState, log_list: List[str]):
    """
    C2: tap all attackers (CR 508.1f).
    L4: blocker deals damage back to the blocked attacker (CR 510.1).
    Defender chooses best blocker; all other attackers hit the player.
    """
    gs._combat_unblocked_tags = set()
    attackers = gs.get_attackers(attacker_player)
    if not attackers:
        return

    # C2 — tap every attacker
    for a in attackers:
        MTGRules.tap_attacker(a)

    total_power = sum(a.power for a in attackers)
    names = ', '.join(a.name for a in attackers)

    # Check indestructible blocker (Marit Lage)
    indestr = next((c for c in defender_player.creatures if c.card.indestructible), None)
    if indestr:
        log_list.append(f"Attack: {names} — {indestr.name} blocks (indestructible). "
                        f"No damage through.")
        # L4: attacker blocked by indestructible takes its power in damage
        # but since Marit Lage is 20/20, any attacker with less than 20 toughness dies
        blocked = max(attackers, key=lambda a: a.power, default=None)
        if blocked:
            blocked.damage_marked += indestr.power
            # indestructible doesn't die from damage; attacker might
        update_goyf(gs)
        gs.state_based_actions()
        return

    # CR 509.1b — flying creatures can only be blocked by creatures with flying or reach
    # Also: Brazen Borrower can only block creatures with flying (oracle)
    flying_attackers  = [a for a in attackers if a.card.flying]
    ground_attackers  = [a for a in attackers if not a.card.flying]

    # Determine which defender creatures can legally block at least one attacker
    can_block = []
    for c in defender_player.creatures:
        has_flying = c.card.flying
        has_reach  = getattr(c.card, 'reach', False)
        borrower   = c.card.tag == 'borrow'

        if borrower:
            # Borrower: "can block only creatures with flying"
            if flying_attackers:
                can_block.append(c)
        elif has_flying or has_reach:
            # Can block anything (flying or ground)
            can_block.append(c)
        else:
            # Ground creature: can only block ground attackers
            if ground_attackers:
                can_block.append(c)

    # ── Vial combat ambush (instant speed — CR 702.12a) ──
    # DnT/Boros can activate Vial during BUG's declare-attackers step to flash in
    # a creature as a surprise blocker. Real players do this to trade favourably:
    # Flickerwisp (3/1) blocks Tarmogoyf, Skyclave exiles BUG permanent on ETB,
    # Thalia (2/1) trades with a 2/2, etc.
    # Condition: Vial has matching counters, opp has a creature in hand at that CMC,
    # and the ambush creature can survive or trade favourably with an attacker.
    if MC.is_vial(gs) and attackers:
        # Vial ambush: the DEFENDER (DnT/Boros) flashes in a creature to block
        vial_owner = defender_player
        if True:  # fire whenever defender has Vial
            vial_perm = next((p for p in vial_owner.artifacts if p.card.tag == 'vial'), None)
            if vial_perm and gs.vial_counters > 0:
                ambush_tags = ('flickerwisp','skyclave','thalia','phelia',
                               'recruiter','solitude','orchid','dungeoneer','minsc')
                for tag in ambush_tags:
                    crea = vial_owner.find_tag(tag)
                    if not crea or crea.cmc != gs.vial_counters:
                        continue
                    # Check if this creature can profitably block any attacker:
                    # profitable = kills attacker, or survives, or is Skyclave/Solitude (ETB value)
                    high_value_etb = getattr(crea, 'is_removal', False)
                    can_trade = any(
                        crea.base_toughness > a.power or   # survives the block
                        crea.base_power >= a.toughness or  # kills the attacker
                        (a.card.deathtouch and crea.base_toughness > 0) or  # any dmg is lethal
                        high_value_etb  # ETB effect worth dying for
                        for a in attackers
                        if not a.card.flying or crea.flying or getattr(crea, 'reach', False)
                    )
                    if can_trade:
                        vial_owner.remove_from_hand(crea)
                        new_perm = vial_owner.put_creature_in_play(crea)
                        new_perm.summoning_sick = False  # instant-speed = can block immediately
                        # ETB effects (target the attacker's side)
                        if tag == 'skyclave' and attacker_player.creatures:
                            tgt = next((c for c in attacker_player.creatures if c.card.cmc <= 4), None)
                            if tgt:
                                attacker_player.remove_creature(tgt)
                                log_list.append(f"  Skyclave Apparition (Vial ambush) exiles {tgt.card.name}")
                                update_goyf(gs)
                        if tag == 'solitude' and attacker_player.creatures:
                            tgt = max(attacker_player.creatures, key=lambda c: c.power)
                            attacker_player.remove_creature(tgt)
                            log_list.append(f"  Solitude (Vial ambush) exiles {tgt.card.name}")
                            update_goyf(gs)
                        if tag == 'recruiter':
                            for ft in ('thalia','phelia','flickerwisp','skyclave'):
                                found = next((c for c in vial_owner.library if c.tag == ft), None)
                                if found:
                                    vial_owner.library.remove(found)
                                    vial_owner.hand.append(found)
                                    log_list.append(f"  Recruiter (ambush) tutors {found.name}")
                                    break
                        can_block.append(new_perm)
                        log_list.append(
                            f"★ Vial [{gs.vial_counters}] combat ambush → {crea.name} "
                            f"({new_perm.power}/{new_perm.toughness}) enters as blocker")
                        break  # one Vial activation per combat

    # ── Multi-blocker assignment (CR 509) ──────────────────────────────────────
    # Defender assigns one blocker per attacker, choosing to maximise board advantage:
    # - Kill the biggest attacker if possible
    # - Chump to prevent damage if outmatched
    # - Let unblockable attackers through (flying vs no flyers, etc.)
    # This logic is symmetric: same algorithm whether BUG or OPP is defending.

    def can_legally_block(blocker, attacker):
        """CR 509.1b: check block legality."""
        if blocker.card.tag == 'borrow':
            return attacker.card.flying  # Borrower blocks only flying
        if attacker.card.flying:
            return blocker.card.flying or getattr(blocker.card, 'reach', False)
        return True  # ground creature blocks ground

    # Sort attackers: biggest threats first (most dangerous if unblocked)
    sorted_atk = sorted(attackers, key=lambda a: a.power, reverse=True)
    available_blockers = list(can_block)
    assignments = {}  # id(attacker) -> blocker

    for atk in sorted_atk:
        # Skip unblockable attackers (e.g. Kappa Cannoneer with ward triggers)
        if getattr(atk, 'cant_be_blocked', False):
            continue
        legal = [b for b in available_blockers if can_legally_block(b, atk)]
        if not legal:
            continue  # no legal blocker — attacker gets through

        # Defender block priority:
        # 1. Kill attacker with smallest blocker that survives (favorable trade)
        # 2. If no favorable trade: chump the biggest attacker to prevent damage
        #    — but only chump if attacker would deal >= 3 unblocked damage
        # 3. Don't block if blocking loses the blocker for nothing

        def blocker_outcome(b):
            # Wall: high-toughness creature that survives combat and prevents damage
            if b.toughness > atk.power and atk.power > 0:
                return 0  # favorable — wall blocks indefinitely
            a_dies = (b.power >= atk.toughness or
                      (b.card.deathtouch and b.power > 0))
            b_dies = (atk.power >= b.toughness or
                      (atk.card.deathtouch and atk.power > 0))
            if a_dies and not b_dies:  return 0  # favorable
            if a_dies and b_dies:      return 1  # even trade
            if not a_dies and b_dies:  return 3  # chump
            return 2                              # both survive (chip)

        # Favorable or even trades: pick smallest blocker that achieves it
        favorable = [b for b in legal if blocker_outcome(b) <= 1]
        if favorable:
            # Use smallest toughness blocker — preserve high-toughness blockers
            best = min(favorable, key=lambda b: b.toughness)
            assignments[id(atk)] = best
            available_blockers.remove(best)
        elif atk.power >= 3:
            # Chump if attacker deals significant damage and we have spare blockers
            # Don't chump with our last creature unless defender near lethal
            spare_threshold = 1 if defender_player.life <= atk.power * 2 else 2
            if len(available_blockers) >= spare_threshold:
                # Pick lowest-value blocker (lowest power = least offensive value)
                chump = min(legal, key=lambda b: b.power)
                assignments[id(atk)] = chump
                available_blockers.remove(chump)

    # ── Resolve damage for each blocked pair + all unblocked ─────────────────
    total_unblocked_dmg = 0
    atk_names = ', '.join(a.name for a in attackers)
    block_parts = []

    for atk in attackers:
        blocker = assignments.get(id(atk))
        if blocker:
            # Mutual damage
            dmg_to_blocker  = atk.power
            dmg_to_attacker = blocker.power

            blocker.damage_marked  += dmg_to_blocker
            atk.damage_marked      += dmg_to_attacker

            atk_dt  = atk.card.deathtouch
            blk_dt  = blocker.card.deathtouch

            blocker_died = (blocker.is_destroyed() or
                            MTGRules.check_lethal_damage(blocker,  deathtouch_source=atk_dt) or
                            MTGRules.check_zero_toughness(blocker))
            attacker_died = (atk.is_destroyed() or
                             MTGRules.check_lethal_damage(atk, deathtouch_source=blk_dt) or
                             MTGRules.check_zero_toughness(atk))

            # Lifelink
            if atk.card.lifelink and dmg_to_blocker > 0:
                attacker_player.life += dmg_to_blocker
            if blocker.card.lifelink and dmg_to_attacker > 0:
                defender_player.life += dmg_to_attacker

            block_parts.append(
                f"{blocker.name} blocks {atk.name}. "                f"{atk.name} deals {dmg_to_blocker}, {blocker.name} deals {dmg_to_attacker} back. "                f"0 unblocked damage to player ({defender_player.name} at {defender_player.life})")

            if blocker_died:
                defender_player.remove_creature(blocker)
                block_parts.append(f"  {blocker.name} dies.")
            if attacker_died:
                attacker_player.remove_creature(atk)
                block_parts.append(f"  {atk.name} dies.")
        else:
            # Unblocked — route through deal_damage (handles infect → poison)
            gs._combat_unblocked_tags.add(atk.card.tag)
            if getattr(atk.card, 'infect', False):
                # Infect: damage as poison counters via deal_damage
                def _log_dmg(msg, key=False):
                    log_list.append(msg)
                deal_damage(gs, atk.card.tag, defender_player, atk.power,
                            damage_type='infect', log_fn=_log_dmg,
                            source_card=atk.card, attacker_player=attacker_player)
            else:
                total_unblocked_dmg += atk.power
            if atk.card.lifelink:
                attacker_player.life += atk.power

    if block_parts:
        log_list.append(f"Attack: {atk_names} — " + block_parts[0])
        for part in block_parts[1:]:
            log_list.append(f"  {part}")

    if total_unblocked_dmg > 0:
        defender_player.life -= total_unblocked_dmg
        if block_parts:
            log_list.append(f"  {total_unblocked_dmg} unblocked → {defender_player.name} at {defender_player.life}")
        else:
            log_list.append(f"Attack: {atk_names} — {total_unblocked_dmg} unblocked → {defender_player.name} at {defender_player.life}")
    elif not block_parts and total_unblocked_dmg == 0 and not any(getattr(a.card, 'infect', False) for a in attackers):
        log_list.append(f"Attack: {atk_names} — 0 damage (all blocked)")

    update_goyf(gs)

    gs.check_life_totals()
    gs.state_based_actions()


# ─────────────────────────────────────────────
# BUG TEMPO turn
# ─────────────────────────────────────────────


def _select_fow_pitch(hand, exclude_card):
    """Select least-valuable blue card for FoW/FoN pitch. Never exile blue threats."""
    never_exile = {'tamiyo', 'murk', 'kaito', 'borrow'}
    def pitch_value(c):
        if c is exclude_card: return 999
        if 'U' not in getattr(c, 'colors', set()): return 999
        if c.tag in never_exile: return 90
        if c.is_land(): return 95
        if c.tag == 'bauble':  return 1
        if c.tag == 'ponder':  return 2
        if c.tag == 'bs':      return 3
        if c.tag == 'daze':    return 4
        if c.tag == 'fluster': return 5
        return 10
    candidates = [c for c in hand
                  if 'U' in getattr(c, 'colors', set())
                  and c is not exclude_card
                  and c.tag not in never_exile
                  and not c.is_land()]
    return min(candidates, key=pitch_value) if candidates else None


def try_reactive_counter(gs: GameState, caster, defender, spell_card, log_list: list) -> bool:
    """
    Symmetric counter — defender tries to counter caster's spell.
    Works for either player slot (p1 or p2).

    Merges _opp_reactive_counter + _opp_try_counter into one function:
    - Full counter suite: FoW, FoN, Counterspell, Flusterstorm, Pyroblast, Consign, Daze
    - Threat assessment: major/minor classification, control deck awareness
    - Trinisphere check, Veil of Summer, Shepherd protection
    - Daze pay-through probability based on matchup type
    """
    import random
    matchup = getattr(gs, 'matchup', '')

    # ── Determine labels for trace ──
    if gs.trace:
        c_label = (getattr(gs, 'p1_deck', 'P1') if caster is gs.p1
                   else getattr(gs, 'p2_deck', 'P2')).upper()
        d_label = (getattr(gs, 'p1_deck', 'P1') if defender is gs.p1
                     else getattr(gs, 'p2_deck', 'P2')).upper()
        log_list.append(f"    → {spell_card.name} goes on the STACK")
        log_list.append(f"    → Priority passes to {d_label}")

    # ── Protection checks ──
    if getattr(gs, 'veil_active', False):
        if gs.trace:
            log_list.append(f"    → Veil of Summer active — spell cannot be countered")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False
    if getattr(gs, 'shepherd_in_play', False) and 'G' in getattr(spell_card, 'colors', set()):
        if gs.trace:
            log_list.append(f"    → Allosaurus Shepherd — green spells uncounterable")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False

    # ── Scan defender's hand for all counter types ──
    _COUNTER_TAGS = CL.COUNTER_TAGS
    counters_by_tag = {}
    for c in defender.hand:
        if c.tag in _COUNTER_TAGS and c.tag not in counters_by_tag:
            counters_by_tag[c.tag] = c

    if not counters_by_tag:
        if gs.trace:
            log_list.append(f"    → {d_label} has no counters — passes priority")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False

    d_fow = counters_by_tag.get('fow')
    d_fon = counters_by_tag.get('fon')
    d_daze = counters_by_tag.get('daze')
    d_consign = counters_by_tag.get('consign')
    d_cs = counters_by_tag.get('counter')
    d_fluster = counters_by_tag.get('fluster')
    d_pyro = counters_by_tag.get('pyro') or counters_by_tag.get('reb')

    # Trinisphere: alternate costs still need to pay at least 3 mana (CR 601.2f)
    if gs.trinisphere_active:
        d_fow = None
        d_fon = None
        d_daze = None  # Daze alternate cost = 0 mana, doesn't meet Trini minimum

    if not any([d_fow, d_fon, d_daze, d_consign, d_cs, d_fluster, d_pyro]):
        return False

    # ── Don't counter cantrips — save counters for threats ──
    if spell_card.tag in CL.NEVER_COUNTER_TAGS:
        if gs.trace:
            avail = [c.name for t, c in counters_by_tag.items()]
            log_list.append(f"    → {d_label} has [{', '.join(avail)}] but PASSES")
            log_list.append(f"      (cantrip — not worth a counter, saving for threats)")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False

    total_counters = sum(1 for c in defender.hand if c.tag in _COUNTER_TAGS)

    # ── Thoughtseize: only counter if defender has key threats to protect AND 2+ counters ──
    if spell_card.tag == 'ts':
        has_key_card = any(c.win_condition or c.is_combo_piece or c.tag in ('wst', 'mentor', 'dd', 'sat')
                          for c in defender.hand)
        if not (has_key_card and total_counters >= 2):
            return False

    # ── Threat assessment ──
    has_removal = any(c.tag == 'stp' for c in defender.hand)
    is_major_threat = (
        spell_card.win_condition or spell_card.is_combo_piece or
        spell_card.tag in ('murk', 'kaito') or spell_card.cmc >= 5 or  # was 4 — vanilla 4-drops not worth FoW
        getattr(spell_card, 'lock_piece', False) or  # lock pieces shut down entire strategies
        getattr(spell_card, 'engine', False)          # engines snowball if not answered
    )

    # Burn spells: major threat when defender is at low life or spell is lethal
    _BURN_TAGS = CL.BURN_TAGS
    if spell_card.tag in _BURN_TAGS and not is_major_threat:
        nonbasics = sum(1 for l in defender.lands if not l.card.is_basic)
        est_damage = 3  # default burn spell damage
        if spell_card.tag == 'pop':
            est_damage = nonbasics * 2
        elif spell_card.tag == 'fireblast':
            est_damage = 4
        elif spell_card.tag in ('bolt', 'chain', 'spike', 'rift'):
            est_damage = 3
        elif spell_card.tag == 'skullcrack':
            est_damage = 3
        # Counter if lethal, high damage (POP), or defender at low-ish life
        if est_damage >= defender.life or defender.life <= CT.BURN_COUNTER_LIFE or est_damage >= 6:
            is_major_threat = True

    # Eidolon of the Great Revel: major threat for any deck that casts CMC≤3 spells
    # (which is nearly every Legacy deck). Punishes cantrips, removal, counters.
    if spell_card.tag == 'eidolon':
        is_major_threat = True

    # Mirror/flash: Bowmasters + Nethergoyf are key threats worth FoWing
    from deck_registry import is_in_category
    is_mirror_or_flash = is_in_category(matchup, 'mirror') or is_in_category(matchup, 'dimir_only')
    if spell_card.tag in ('bowm', 'nether') and is_mirror_or_flash and total_counters >= 2:
        is_major_threat = True

    # High-power cheap creatures from tempo/aggro decks are major threats when
    # the defender lacks creature removal in hand. DRC (3/3 for 1) and Cutter
    # (3/1 haste for 2) are Legacy's premier cheap threats — if the defender
    # can't Fatal Push or Bolt them, they must counter or lose the tempo war.
    _TEMPO_THREAT_TAGS = {'drc', 'cutter', 'ragavan', 'delver'}
    if (spell_card.tag in _TEMPO_THREAT_TAGS and not is_major_threat):
        has_creature_removal = any(c.tag in ('push', 'bolt', 'heat', 'stp',
                                             'bowm', 'decay', 'solitude')
                                   for c in defender.hand)
        if not has_creature_removal and total_counters >= 2:
            is_major_threat = True

    # Infect pump spells: when caster has an infect creature on board, pump spells
    # are kill-enabling combo pieces and should always be countered. In real Legacy,
    # FoW on Invigorate or Berserk is critical — these are the infect kill spells.
    _INFECT_PUMP_TAGS = {'invigorate', 'mutagenic', 'berserk', 'vines', 'defense'}
    if spell_card.tag in _INFECT_PUMP_TAGS and not is_major_threat:
        infect_tags = {'glistener', 'blighted', 'inkmoth'}
        caster_has_infect = any(c.card.tag in infect_tags for c in caster.creatures)
        if caster_has_infect:
            is_major_threat = True

    # Control decks (runs STP) should NOT FoW cheap creatures — STP them later
    # But always counter Eidolon, lock pieces, and engines (can't STP those)
    if (spell_card.cmc <= 2 and has_removal and not spell_card.win_condition
            and spell_card.tag != 'eidolon'
            and not getattr(spell_card, 'lock_piece', False)
            and not getattr(spell_card, 'engine', False)):
        is_major_threat = False

    is_minor_threat = spell_card.tag in ('tamiyo', 'borrow')
    if is_minor_threat and total_counters <= 2:
        if gs.trace:
            log_list.append(f"    → {d_label} evaluates: minor threat + only {total_counters} counter(s) — PASSES")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False
    if not (is_major_threat or is_minor_threat):
        if gs.trace:
            avail = [c.name for t, c in counters_by_tag.items()]
            reason = "low-priority target"
            if spell_card.cmc <= 2 and has_removal:
                reason = f"CMC {spell_card.cmc} creature — better answered by removal later"
            log_list.append(f"    → {d_label} has [{', '.join(avail)}] but PASSES ({reason})")
            log_list.append(f"    → {spell_card.name} RESOLVES")
        return False

    # ── Determine defender label for log messages ──
    d_label = (getattr(gs, 'p1_deck', 'P1') if defender is gs.p1
               else getattr(gs, 'p2_deck', 'P2')).upper()

    ctr = []

    # ── FoN first (free on opponent's turn = caster's turn; needs blue pitch) ──
    if d_fon and 'U' in getattr(d_fon, 'colors', set()):
        blue_pitch = _select_fow_pitch(defender.hand, d_fon)
        if blue_pitch:
            defender.remove_from_hand(d_fon); defender.add_to_grave(d_fon)
            defender.remove_from_hand(blue_pitch); defender.exile.append(blue_pitch)
            gs._last_counter_used = 'fon'
            ctr.append(f"Force of Negation counters {spell_card.name} (exiles {blue_pitch.name})")

    # ── FoW (free if pitch blue card) ──
    if not ctr and d_fow:
        blue_pitch = _select_fow_pitch(defender.hand, d_fow)
        if blue_pitch:
            defender.remove_from_hand(d_fow); defender.add_to_grave(d_fow)
            defender.remove_from_hand(blue_pitch); defender.exile.append(blue_pitch)
            gs._last_counter_used = 'fow'
            ctr.append(f"Force of Will counters {spell_card.name} (exiles {blue_pitch.name})")

    # ── Counterspell (UU, requires mana + hand depth ≥ 4) ──
    if not ctr and d_cs and is_major_threat and len(defender.hand) >= 4:
        d_mana = defender.available_mana_count()
        d_has_uu = sum(1 for l in defender.lands if not l.tapped and 'U' in l.effective_produces()) >= 2
        if d_mana >= 2 and d_has_uu:
            defender.remove_from_hand(d_cs); defender.add_to_grave(d_cs)
            gs._last_counter_used = 'counter'
            ctr.append(f"Counterspell counters {spell_card.name}")

    # ── Flusterstorm (U, instant/sorcery only, requires mana + hand ≥ 3) ──
    if not ctr and d_fluster and is_major_threat and len(defender.hand) >= 3:
        if spell_card.card_type in (CardType.INSTANT, CardType.SORCERY):
            d_has_u = any(not l.tapped and 'U' in l.effective_produces() for l in defender.lands)
            if d_has_u:
                defender.remove_from_hand(d_fluster); defender.add_to_grave(d_fluster)
                gs._last_counter_used = 'fluster'
                ctr.append(f"Flusterstorm counters {spell_card.name}")

    # ── Pyroblast/REB (R, blue spells only) ──
    if not ctr and d_pyro:
        if 'U' in getattr(spell_card, 'colors', set()):
            d_has_r = any(not l.tapped and 'R' in l.effective_produces() for l in defender.lands)
            if d_has_r:
                defender.remove_from_hand(d_pyro); defender.add_to_grave(d_pyro)
                gs._last_counter_used = 'pyro'
                ctr.append(f"{d_pyro.name} counters {spell_card.name} (blue spell)")

    # ── Consign to Memory (3 mana, hard counter) ──
    if not ctr and d_consign:
        d_mana = defender.available_mana_count()
        if d_mana >= 3:
            defender.remove_from_hand(d_consign); defender.add_to_grave(d_consign)
            ctr.append(f"Consign to Memory counters {spell_card.name}")

    # ── Daze (return Island; caster may pay {1} to prevent) ──
    # Daze is strong T1-2 when opponents are mana-tight, but after T3 opponents
    # can usually pay {1}. Model pay-through rate scaling with turn + caster mana.
    if not ctr and d_daze and is_major_threat:
        blue_land = next((l for l in defender.lands if not l.tapped and 'U' in l.effective_produces()), None)
        if blue_land:
            is_combo = is_in_category(matchup, 'combo') or is_in_category(matchup, 'fast_combo')
            # Caster's available mana after casting the spell (can they afford +1?)
            caster_mana = caster.available_mana_count()
            caster_spare = max(0, caster_mana - spell_card.cmc)
            # Pay-through probability increases with turn and spare mana
            if is_combo:
                pay_threshold = CL.DAZE_PAY_PROB_COMBO  # combo decks often tap out
            elif gs.turn <= 2:
                pay_threshold = 0.15 if caster_spare >= 1 else 0.10  # was 0.0 — small chance even tapped out
            elif gs.turn == 3:
                pay_threshold = 0.50 if caster_spare >= 1 else 0.20
            else:
                # T4+: opponent almost always has spare mana to pay {1}
                pay_threshold = 0.85 if caster_spare >= 1 else 0.45
            can_pay = (spell_card.cmc >= 1 and
                       random.random() < pay_threshold)
            if can_pay:
                log_list.append(f"  Daze attempted on {spell_card.name} — caster pays {{1}}, spell resolves")
            else:
                defender.lands.remove(blue_land)
                defender.hand.append(blue_land.card)
                defender.remove_from_hand(d_daze); defender.add_to_grave(d_daze)
                gs._last_counter_used = 'daze'
                ctr.append(f"Daze counters {spell_card.name} — {blue_land.name} returned")

    if ctr:
        if gs.trace:
            threat_level = "MAJOR THREAT" if is_major_threat else "minor threat"
            log_list.append(f"    → {d_label} evaluates: {threat_level} — responds!")
        for m in ctr:
            log_list.append(f"  ★ {d_label} {m}")
        log_list.append(f"  {spell_card.name} COUNTERED — goes to graveyard")
        return True
    if gs.trace:
        log_list.append(f"    → {d_label} has counters but cannot use them (conditions not met)")
        log_list.append(f"    → {spell_card.name} RESOLVES")
    return False


def play_turn(gs: GameState, turn: int, who: str = 'p1'):
    """
    Unified turn entry point — dispatches to the appropriate turn function.
    who='p1': P1's turn (protagonist_turn — all decks via strategy dispatch)
    who='p2': P2's turn (opp_turn — all decks via registry)

    Both players get equal AI quality. The p1/p2 slots are neutral —
    the deck key determines which strategy runs, not the slot.

    Also enforces universal rules that apply regardless of strategy:
    - Narset lock (opponent's Narset prevents extra draws)
    """
    # ── Universal pre-turn rules ──
    player = gs.p1 if who == 'p1' else gs.p2
    opponent = gs.p2 if who == 'p1' else gs.p1
    # Narset: if opponent controls Narset, this player can't draw extra cards
    player._narset_lock = any(
        c.card.tag == 'narset' for c in
        (getattr(opponent, 'planeswalkers', []) + [c for c in opponent.creatures if c.card.tag == 'narset'])
    )
    # Leyline of the Void: if opponent has Leyline, this player's cards → exile
    opponent.leyline_exile = gs.leyline_active and any(
        p.card.tag == 'leyline' for p in opponent.enchantments
    )

    if who == 'p1':
        p1_deck = getattr(gs, 'p1_deck', '')
        # ── Wasteland sacrifice fix (CR 701.16) ──
        # protagonist_turn taps Wasteland but doesn't sacrifice it.
        # Real Wasteland: "{T}, Sacrifice ~: Destroy target nonbasic land."
        # Track which Wastelands were untapped before the turn. After the turn,
        # any that became tapped were activated and must be sacrificed.
        # Note: untap_all() runs inside protagonist_turn, so all Wastelands
        # start untapped. We detect newly-tapped ones after the turn.
        wl_ids_before = set(id(l) for l in player.lands
                            if l.card.tag in ('wl', 'wasteland'))
        opp_land_count_before = len(opponent.lands)
        from sim import protagonist_turn
        result = protagonist_turn(gs, turn, p1_deck)
        # If opponent lost a nonbasic land and a Wasteland was tapped,
        # it was an activation — sacrifice it
        opp_land_count_after = len(opponent.lands)
        if opp_land_count_after < opp_land_count_before:
            tapped_wl = [l for l in player.lands
                         if l.card.tag in ('wl', 'wasteland')
                         and l.tapped and id(l) in wl_ids_before]
            for wl in tapped_wl[:1]:  # at most 1 Wasteland activation per turn
                player.lands.remove(wl)
                player.add_to_grave(wl.card)
        return result
    else:
        matchup = getattr(gs, 'p2_deck', '') or getattr(gs, 'matchup', '')
        return opp_turn(gs, turn, matchup)



def _strategy_bug(player, opponent, gs, total_mana, log_fn, log_entries):
    """BUG Tempo strategy — extracted from bug_turn for symmetric dispatch.
    Handles: Bauble sac, Wasteland, discard, cantrips, removal, threats, sideboard cards."""
    budget = [total_mana]
    turn = gs.turn

    # Trinisphere CR 601.2f: all spells cost at least {3}
    trini_min = 3 if gs.trinisphere_active else 0
    thalia_tax = 1 if gs.thalia_on_board else 0
    def effective_cmc(card):
        base = max(card.cmc, trini_min)
        if not card.is_creature():
            base += thalia_tax
        return base

    def spend(card):
        """Deduct mana and fire Eidolon trigger."""
        _deduct(budget, effective_cmc(card), card)
        _eidolon_trigger(gs, card, log_fn)

    def _threat_castable(c):
        """True if we can cast this creature given current budget and GY state (handles delve)."""
        ecmc = effective_cmc(c)
        if budget[0] < ecmc: return False
        if ecmc < c.cmc:  # delve reduced cost — only check colored pips
            colored = {k:v for k,v in c.mana_cost.items() if k != 'generic'}
            return can_afford(player, colored)
        return can_afford(player, c.mana_cost)

    # ── Mishra's Bauble (BUG's own) — sac immediately, draws on next upkeep ──
    # CMC 0: tap and sacrifice; look at top of opp library; draw a card on next upkeep.
    # No mana cost. Always sac immediately — delayed draw + artifact in GY (Nethergoyf).
    for bauble in list(player.hand):
        if bauble.tag == 'bauble':
            player.remove_from_hand(bauble)
            player.add_to_grave(bauble)  # artifact type in BUG GY → helps own Nethergoyf
            gs.pending_bauble_draws = gs.pending_bauble_draws + 1
            log_fn(f"Mishra's Bauble (sac → draw on next upkeep, artifact in GY)")
            update_goyf(gs)

    # ═══════════════════════════════════════════════════════════
    # GAME STATE ASSESSMENT — informs all decisions this turn
    # ═══════════════════════════════════════════════════════════
    game_state, _m = assess_board(player, opponent)
    bug_board_power  = _m['board_power']
    opp_board_power  = _m['opp_power']
    bug_threat_count = _m['threat_count']
    opp_threat_count = _m['opp_threats']
    bug_has_threats  = _m['has_threats']
    opp_has_cantrips = any(c.is_cantrip for c in opponent.hand)

    # ── Wasteland (activated ability — uncounterable, no mana cost) ──
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        # Priority: cut the colour opp needs most for their spells this turn
        opp_spell_colours = set(col for card in opponent.hand if not card.is_land()
                                for col in card.colors)
        def _wl_priority(land):
            score = 0
            produces = land.effective_produces()
            # Combo lands (Dark Depths / Thespian's Stage) are highest priority
            if land.card.tag in ('depths', 'stage'): score += 50
            if produces & opp_spell_colours: score += 10  # cuts a colour opp needs NOW
            if land.card.mana_ritual: score += 5  # cuts mana-ritual lands (Tomb, City)
            if land.is_fetch:               score += 2   # denies future fixing
            return score
        eligible = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)
                    and (not l.card.is_basic and l.card.is_land())]
        target = max(eligible, key=_wl_priority, default=None)
        if target:
            player.lands.remove(wl)
            player.add_to_grave(wl.card)
            player.revolt_this_turn = True
            opponent.lands.remove(target)
            opponent.add_to_grave(target.card)
            stifle = opponent.find_tag('stifle') if getattr(gs, 'opp_has_stifle', False) else None
            if stifle and can_afford(opponent, stifle.mana_cost):
                opponent.remove_from_hand(stifle); opponent.add_to_grave(stifle)
                # Stifle counters the activated ability. Costs are already paid (Wasteland sac'd).
                # Per oracle: ability is countered but costs aren't reversed.
                # Practical effect: Wasteland is gone, but target land survives.
                try:
                    opponent.graveyard.remove(target.card)
                except ValueError:
                    pass
                opponent.lands.append(target)
                player.revolt_this_turn = False
                log_fn(f"  ★ OPP Stifle → counters Wasteland ability! {target.name} survives", True)
                update_goyf(gs)
            else:
                log_fn(f"Wasteland [ACTIVATED-uncounterable] → destroys {target.name}", key=True)
            budget[0] = player.available_mana_count()
            update_goyf(gs)

    # ── Thoughtseize — C1: needs 1B mana ──
    ts = player.find_tag('ts')
    ts_turn_cap = IP.TS_TURN_CAP_COMBO if MC.is_combo(gs) else IP.TS_TURN_CAP_FAIR
    if ts and turn <= ts_turn_cap and not gs.spell_blocked_by_chalice(ts.cmc):
        if budget[0] >= effective_cmc(ts) and can_afford(player, ts.mana_cost):
            # SEQ-09: only cast TS if opp has a non-land worth stripping.
            # Casting TS into an all-land hand wastes a card and 2 life for nothing.
            target = best_proactive_target(gs, opponent)
            if target:
                spend(ts)
                player.cast_spell(ts, log_fn=log_fn)
                opponent.remove_from_hand(target)
                log_fn(f"Thoughtseize -> strips {target.name}", key=True)

    # ── Flash Bowmasters — PRIORITY: before cantrips to tax opp's next draw ──
    # Bowmasters deploy timing.
    # vs non-mirror (Show, combo, aggro): deploy main phase ASAP — they have no removal.
    # vs mirror (dimir, dimir_flash): hold for EOT flash in response to their cantrip
    #   — 3 Brainstorm draws = 3 pings, and APNAP means our triggers resolve before
    #     their Tamiyo flip. Main-phase deployment telegraphs it and they won't cantrip.
    # Kirdie: "Bowmasters are often better later in Bowmasters mirrors."
    bowm = player.find_tag('bowm')
    if bowm and not gs.bowmasters_on_board and not gs.spell_blocked_by_chalice(bowm.cmc):
        if budget[0] >= effective_cmc(bowm) and can_afford(player, bowm.mana_cost):
            is_tempo_mirror = gs.matchup in MC.TEMPO_MIRROR
            opp_likely_has_cantrip = any(c.is_cantrip for c in opponent.hand)
            hold_for_mirror_eot = is_tempo_mirror and opp_likely_has_cantrip and game_state != 'behind'
            hold_for_interaction = (game_state == 'behind' and bug_has_threats and
                                    any(c.is_removal for c in player.hand))

            if not hold_for_mirror_eot and not hold_for_interaction:
                _deduct(budget, effective_cmc(bowm), bowm)
                player.remove_from_hand(bowm)
                if try_reactive_counter(gs, player, opponent, bowm, log_entries):
                    player.add_to_grave(bowm)
                else:
                    perm = player.put_creature_in_play(bowm)
                    gs.bowmasters_on_board = True
                    log_fn("Flash Bowmasters (1 trigger per card opp draws)", key=True)


    # ── AGGRO REMOVAL PRIORITY ──────────────────────────────────────────────
    # Against creature aggro (Burn, Eldrazi, UR Delver, etc), removal MUST fire
    # before cantrips. A T1 Push on Goblin Guide prevents 6+ damage over 3 turns;
    # a T1 Brainstorm just digs for cards we might not need if we're already dead.
    _did_early_push = False
    _did_early_snuff = False
    if MC.is_aggro(gs) and opponent.creatures:
        # Early Push
        push_early = player.find_tag('push')
        if push_early and not gs.spell_blocked_by_chalice(push_early.cmc):
            _push_mana_after = budget[0] - effective_cmc(push_early)  # mana left to pay ward
            push_targets_early = [c for c in opponent.creatures
                                  if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)
                                  and _can_target(c, _push_mana_after)]
            target_early = (
                next((c for c in push_targets_early if c.card.haste or c.card.draw_trigger), None) or
                next((c for c in push_targets_early if c.card.deathtouch or c.card.lifelink), None) or
                max(push_targets_early, key=lambda c: c.power, default=None)
            )
            if target_early and budget[0] >= effective_cmc(push_early) and can_afford(player, push_early.mana_cost):
                spend(push_early)
                player.remove_from_hand(push_early)
                player.add_to_grave(push_early)
                push_spell = cast_obj(push_early, 'b')
                ctr = []
                fow_worthwhile = target_early.card.cmc >= 3 or target_early.card.engine
                if fow_worthwhile and MTGRules.force_of_will_use(push_spell, opponent.hand, ctr):
                    pass
                elif opponent.available_mana_count() <= 1:
                    MTGRules.daze_use(push_spell, opponent.hand, opponent.lands, ctr)
                if not ctr:
                    opponent.remove_creature(target_early)
                    rev = " [revolt CMC≤4]" if player.revolt_this_turn else " [CMC≤2]"
                    log_fn(f"Fatal Push{rev} → kills {target_early.name} (CMC {target_early.cmc})")
                    _did_early_push = True
                else:
                    for m in ctr: log_fn(f"  {m}")
                update_goyf(gs)

        # Early Snuff Out (free removal — always correct against aggro creatures)
        if not _did_early_push and opponent.creatures:
            snuff_early = player.find_tag('snuffout')
            has_swamp = any('Swamp' in l.card.subtypes or
                            (l.card.is_basic and 'B' in l.effective_produces())
                            for l in player.lands)
            if snuff_early and has_swamp and not gs.spell_blocked_by_chalice(snuff_early.cmc):
                # Snuff Out is free (pay life) — all mana remains available for ward
                _snuff_mana_for_ward = budget[0]
                target_early = next((c for c in sorted(opponent.creatures, key=lambda x: -x.power)
                                     if 'B' not in c.card.colors
                                     and _can_target(c, _snuff_mana_for_ward)), None)
                if target_early and player.life > CT.SNUFF_LIFE_FLOOR_AGGRO:
                    player.cast_spell(snuff_early, log_fn=log_fn)
                    opponent.remove_creature(target_early)
                    log_fn(f"Snuff Out (free, −4 life → {player.life}) → kills {target_early.name}", key=True)
                    _did_early_snuff = True
                    update_goyf(gs)

    # ── Brainstorm — C1: needs 1U ──
    bs = player.find_tag('bs')
    if bs and not gs.spell_blocked_by_chalice(bs.cmc):
        threat_count = sum(1 for c in player.hand if c.is_creature())
        on_board = len(player.creatures)
        # Cast BS when: no threats deployed yet (need to find action regardless of hand),
        # OR fewer than 2 threats in hand. Prevents holding BS when threats are queued
        # but there's nothing on board applying pressure.
        # Cast Brainstorm with shuffle for full value (best).
        # Without shuffle, hold ONLY if we already have 2+ threats in hand
        # AND the game isn't urgent. Otherwise cast freely — BUG needs action.
        has_shuffle = (any(c.is_land() and c.is_fetch for c in player.hand) or
                       any(l.is_fetch and not l.tapped for l in player.lands))
        hand_is_rich = threat_count >= 2  # 2+ threats means we can afford to wait
        # Hold a "blind" BS only when: rich hand AND safe game state AND no urgency
        hold_blind_bs = (not has_shuffle and hand_is_rich and
                         game_state in ('ahead', 'parity') and on_board > 0)
        bs_worth_now = not hold_blind_bs
        # SEQ-05: when opp is fully tapped out, deploy an affordable threat first.
        # Cantripping into a tapped-out opp wastes the free window — cast Murktide/Nethergoyf now.
        opp_tapped_out = opponent.available_mana_count() == 0
        has_affordable_threat = any(c.is_creature() and _threat_castable(c) for c in player.hand)
        # Only yield cantrip to threat in FAIR matchups when opp is tapped out.
        # vs combo (Storm, Oops, Show, DD, Reanimator): always cantrip to find answers.
        is_fair_matchup = not MC.is_combo(gs)
        # Don't yield in mirrors -- Brainstorm before threats is correct in fair mirrors
        yield_to_threat = opp_tapped_out and has_affordable_threat and is_fair_matchup and not MC.is_mirror(gs)
        if bs_worth_now and not yield_to_threat and (on_board == 0 or threat_count < 2) and budget[0] >= effective_cmc(bs) and can_afford(player, bs.mana_cost):
            _deduct(budget, effective_cmc(bs), bs)
            player.remove_from_hand(bs)
            player.add_to_grave(bs)
            n = MTGRules.brainstorm_draws()
            drawn = player.draw(n)
            log_fn(f"Brainstorm ({n} draws = {n} separate draw events) → "
                f"[{', '.join(c.name for c in drawn)}]")
            put_back = sorted(player.hand, key=lambda c: (
                2 if c.is_land() else 1 if (c.is_cantrip) else 0
            ), reverse=True)[:MTGRules.brainstorm_puts_back()]
            for c in put_back:
                player.hand.remove(c)
                player.library.insert(0, c)
            log_fn(f"  Puts back: {[c.name for c in put_back]}")
            update_goyf(gs)

    # ── Ponder — C1: needs 1U ──
    pon = player.find_tag('ponder')
    if pon and not gs.spell_blocked_by_chalice(pon.cmc) and not player.find_tag('bs'):
        on_board_pon = len(player.creatures)
        threat_count_pon = sum(1 for c in player.hand if c.is_creature())
        opp_tapped_out_pon = opponent.available_mana_count() == 0
        has_affordable_threat_pon = any(c.is_creature() and _threat_castable(c) for c in player.hand)
        yield_to_threat_pon = opp_tapped_out_pon and has_affordable_threat_pon and not MC.is_combo(gs) and not MC.is_mirror(gs)
        if (on_board_pon == 0 or threat_count_pon < 2) and not yield_to_threat_pon and budget[0] >= effective_cmc(pon) and can_afford(player, pon.mana_cost):
            _deduct(budget, effective_cmc(pon), pon)
            player.remove_from_hand(pon)
            player.add_to_grave(pon)
            top3 = player.library[:3]
            player.library = player.library[3:]
            keep = (next((c for c in top3 if c.is_creature()), None) or
                    next((c for c in top3 if c.free_cast_if_blue), None) or
                    (top3[0] if top3 else None))
            if keep:
                player.hand.append(keep)
                top3.remove(keep)
            player.library = random.sample(top3, len(top3)) + player.library
            log_fn(f"Ponder ({MTGRules.ponder_draws()} draw) → keeps {keep.name if keep else '—'}")



    # ── Abrupt Decay — C1: needs BG. Uncounterable. ──
    ad = player.find_tag('ad')
    if ad and budget[0] >= effective_cmc(ad) and can_afford(player, ad.mana_cost):
        # Priority: lock pieces > planeswalkers (Narset) > combo enablers > deathtouch creatures
        ad_target = (
            next((p for p in opponent.artifacts + opponent.enchantments
                  if MTGRules.abrupt_decay_valid_target(p)
                  and p.card.lock_piece), None) or
            next((p for p in opponent.planeswalkers                                        # Narset CMC3
                  if MTGRules.abrupt_decay_valid_target(p)), None) or
            next((p for p in opponent.artifacts + opponent.enchantments
                  if MTGRules.abrupt_decay_valid_target(p)
                  and (p.card.is_combo_piece or p.card.engine)), None) or
            next((p for p in opponent.creatures
                  if MTGRules.abrupt_decay_valid_target(p)
                  and p.card.deathtouch), None) or
            next((p for p in opponent.creatures
                  if MTGRules.abrupt_decay_valid_target(p) and p.card.is_combo_piece), None)
        )
        if ad_target:
            spend(ad)
            player.remove_from_hand(ad)
            player.add_to_grave(ad)
            target_list = (opponent.artifacts if ad_target in opponent.artifacts else
                           opponent.enchantments if ad_target in opponent.enchantments else
                           opponent.planeswalkers if ad_target in opponent.planeswalkers else opponent.creatures)
            target_list.remove(ad_target)
            opponent.add_to_grave(ad_target.card)
            log_fn(f"Abrupt Decay [uncounterable] → {ad_target.name} (CMC {ad_target.cmc}≤3)",
                key=True)
            if ad_target.card.tag == 'chalice': gs.chalice_x = None
            elif ad_target.card.tag == 'bridge': gs.bridge_on_board = False
            elif ad_target.card.tag == 'moon':   gs.set_moon(False)
            elif ad_target.card.tag == 'b2b':    gs.set_b2b(False)
            update_goyf(gs)

    # ── Fatal Push — C1: needs 1B ──
    push = player.find_tag('push')
    if push and not _did_early_push and not gs.spell_blocked_by_chalice(push.cmc) and opponent.creatures:
        _push_mana_after = budget[0] - effective_cmc(push)  # mana remaining for ward after paying Push
        push_targets = [c for c in opponent.creatures
                        if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)
                        and _can_target(c, _push_mana_after)]
        target = (
            next((c for c in push_targets if (c.card.haste or c.card.draw_trigger)), None) or
            next((c for c in push_targets if c.card.deathtouch or c.card.lifelink), None) or
            next((c for c in push_targets if c.card.haste), None) or
            max(push_targets, key=lambda c: c.power, default=None)
        )
        if target and budget[0] >= effective_cmc(push) and can_afford(player, push.mana_cost):
            spend(push)
            player.remove_from_hand(push)
            player.add_to_grave(push)
            push_spell = cast_obj(push, 'b')
            ctr = []
            # Opp counters BUG's Push only if worth it:
            # FoW: only protecting a high-value creature
            # Daze: only if opp is tapped out after casting nothing (Push costs BUG 1B)
            # Since opp hasn't spent mana (it's BUG's Push), check opp has ≤1 untapped land
            opp_untapped = opponent.available_mana_count()
            fow_worthwhile_push = target.card.cmc >= 3 or (target.card.engine or target.card.cmc >= 3)
            if fow_worthwhile_push and MTGRules.force_of_will_use(push_spell, opponent.hand, ctr):
                pass
            elif opp_untapped <= 1:  # opp nearly tapped out → Daze correct
                MTGRules.daze_use(push_spell, opponent.hand, opponent.lands, ctr)
            if not ctr:
                opponent.remove_creature(target)  # destroy → opp GY
                rev = " [revolt CMC≤4]" if player.revolt_this_turn else " [CMC≤2]"
                log_fn(f"Fatal Push{rev} → kills {target.name} (CMC {target.cmc})")
            else:
                for m in ctr: log_fn(f"  {m}")
            update_goyf(gs)


    # ── Snuff Out — free (pay 4 life) if controlling a Swamp ──
    # Targets nonblack creatures only — covers Murktide, big Eldrazi, CMC3+ that Push misses.
    # Free to cast as long as BUG controls a Swamp or Underground Sea (Island+Swamp subtype).
    snuffout = player.find_tag('snuffout')
    if snuffout and not _did_early_snuff and not gs.spell_blocked_by_chalice(snuffout.cmc) and opponent.creatures:
        has_swamp = any('B' in l.effective_produces() for l in player.lands)
        # Snuff Out is free (pay life) — all budget mana remains available for ward
        _snuff_mana_for_ward = budget[0]
        snuff_targets = [c for c in opponent.creatures if c.card.tag not in ('bowm',) and
                         'B' not in getattr(c.card, 'colors', set())  # nonblack only
                         and _can_target(c, _snuff_mana_for_ward)]
        if has_swamp and snuff_targets and player.life > 4 + 4:  # keep 4 life buffer
            # Priority: highest CMC (targets Push can't reach) or biggest blocker
            target = max(snuff_targets, key=lambda c: (c.cmc, c.power))
            if target.cmc >= 3 or target.power >= 4 or target.toughness > 3:
                player.remove_from_hand(snuffout)
                player.add_to_grave(snuffout)
                player.life -= 4
                opponent.remove_creature(target)
                player.revolt_this_turn = True
                log_fn(f"Snuff Out (free, −4 life → {player.life}) → kills {target.name} (CMC {target.cmc})")
                update_goyf(gs)

    # ── Dismember — C1: needs 1 mana, L2/L3 ──
    dis = player.find_tag('dismember')
    if dis and not gs.spell_blocked_by_chalice(dis.cmc) and opponent.creatures:
        # Dismember costs 1 generic (+ 4 life); mana after = budget - 1 for ward check
        _dismember_mana_after = budget[0] - 1
        big = next((c for c in opponent.creatures
                    if c.power >= 4 and not player.creatures
                    and _can_target(c, _dismember_mana_after)), None)
        if big and budget[0] >= 1 and player.available_mana_count() >= 1:
            if MTGRules.dismember_kills(big):  # L3: only cast if it will kill
                _deduct(budget, 1, None)   # L2: pay the 1 generic
                player.remove_from_hand(dis)
                player.add_to_grave(dis)
                player.life -= 4
                opponent.remove_creature(big)
                log_fn(f"Dismember (1 mana + 4 life → {player.life}) kills {big.name} "
                    f"({big.toughness}-5={big.toughness-5}≤0)")
                update_goyf(gs)
                gs.state_based_actions()


    # ── Sideboard cards ──────────────────────────────────────────

    # Endurance (flash, ETB: exile all GYs) — vs Reanimator/Doomsday/Oops
    endurance_card = player.find_tag('endurance')
    if endurance_card and not gs.spell_blocked_by_chalice(endurance_card.cmc):
        opp_gy_size = len(opponent.graveyard)
        can_evoke = any('G' in c.colors for c in player.hand if c.tag != 'endurance')
        # Evoke (free): exile a green card from hand — ETB triggers, then creature sacrificed
        # Full cast (1GG): enters as a 3/4 reach creature
        if opp_gy_size >= 2:
            if can_evoke:
                # Evoke path — free, instant speed, creature sacrificed after ETB
                green_pitch = next(c for c in player.hand if 'G' in c.colors and c.tag != 'endurance')
                player.remove_from_hand(endurance_card)
                player.remove_from_hand(green_pitch)
                player.exile.append(green_pitch)
                # ETB: target OPP graveyard — put all cards on BOTTOM of their library (random order)
                # Oracle: "up to one target player puts all cards from their graveyard on
                # the bottom of their library in a random order"
                gy_count = len(opponent.graveyard)
                shuffled = list(opponent.graveyard)
                random.shuffle(shuffled)
                opponent.graveyard = []
                opponent.library.extend(shuffled)   # bottom of library
                # Endurance is sacrificed immediately (evoke) — does NOT enter creatures list
                log_fn(f"★ Endurance (EVOKE, exiles {green_pitch.name}) — {gy_count} opp GY cards"
                    f" put on bottom of library in random order", key=True)
                update_goyf(gs)
            elif budget[0] >= effective_cmc(endurance_card) and can_afford(player, endurance_card.mana_cost):
                _deduct(budget, effective_cmc(endurance_card), endurance_card)
                player.remove_from_hand(endurance_card)
                perm = player.put_creature_in_play(endurance_card)
                # Reach keyword — can block flyers
                perm.card.flying = False   # endurance doesn't fly, but has reach
                gy_count = len(opponent.graveyard)
                shuffled = list(opponent.graveyard)
                random.shuffle(shuffled)
                opponent.graveyard = []
                opponent.library.extend(shuffled)
                log_fn(f"★ Endurance 3/4 Reach (full cast) — {gy_count} opp GY cards"
                    f" put on bottom of library in random order", key=True)
                update_goyf(gs)

    # Force of Vigor — FREE only on opponent's turn (oracle: "if it's not your turn")
    # On BUG's OWN turn, FoV costs {1}{G}{G} = 3 mana. Worth paying if a lock piece is active.
    fov_paid = player.find_tag('fov')
    if fov_paid and budget[0] >= 3 and (gs.trinisphere_active or gs.chalice_x is not None or gs.bridge_on_board):
        has_green_src = any('G' in l.effective_produces() for l in player.lands if not l.tapped)
        if has_green_src:
            targets = [p for p in opponent.artifacts + opponent.enchantments
                       if p.card.lock_piece][:2]
            if targets:
                _deduct(budget, 3, fov_paid)
                player.remove_from_hand(fov_paid)
                player.add_to_grave(fov_paid)
                names = []
                for t in targets:
                    tlist = opponent.artifacts if t in opponent.artifacts else opponent.enchantments
                    if t in tlist:
                        tlist.remove(t)
                        opponent.add_to_grave(t.card)
                        names.append(t.name)
                        if t.card.tag == 'chalice': gs.chalice_x = None
                        elif t.card.tag == 'bridge': gs.bridge_on_board = False
                        elif t.card.tag == 'trini':  gs.trinisphere_active = False
                update_goyf(gs)
                log_fn(f"★ Force of Vigor (paid {'{1}{G}{G}'}) → destroys {' + '.join(names)}", key=True)

    # Pyroblast / Hydroblast
    # pyro = Pyroblast: destroys target blue permanent (correct vs Dimir mirrors)
    # hydro = Hydroblast: destroys target red permanent (correct vs UR Aggro, Painter)
    pyro_card = player.find_tag('pyro') or player.find_tag('hydro')
    if pyro_card and budget[0] >= 1 and can_afford(player, pyro_card.mana_cost):
        target_color = 'R' if pyro_card.tag == 'hydro' else 'U'
        color_name = 'red' if pyro_card.tag == 'hydro' else 'blue'
        # Pyro/Hydro costs 1; mana after paying = budget - 1 (for ward check)
        _pyro_mana_after = budget[0] - 1
        target_perm = next((c for c in opponent.creatures
                            if target_color in c.card.colors
                            and _can_target(c, _pyro_mana_after)), None)
        if target_perm:
            _deduct(budget, 1, pyro_card)
            player.remove_from_hand(pyro_card)
            player.add_to_grave(pyro_card)
            opponent.remove_creature(target_perm)
            opponent.revolt_this_turn = True
            log_fn(f"{pyro_card.name} → destroys {target_perm.name} ({color_name} permanent)")
            update_goyf(gs)

    # Toxic Deluge — vs wide aggro boards
    deluge_card = player.find_tag('deluge')
    if deluge_card and len(opponent.creatures) >= 2:
        if budget[0] >= effective_cmc(deluge_card) and can_afford(player, deluge_card.mana_cost):
            # Oracle: ALL creatures get -X/-X until EOT (including BUG's own)
            # Choose X = smallest value that wipes opp board without wiping BUG board
            # If BUG has no creatures, use max opp toughness
            # If BUG has creatures, use min X that kills opp board but not BUG's key creatures
            opp_max_t = max((c.toughness for c in opponent.creatures), default=1)
            bug_min_t = min((c.toughness for c in player.creatures), default=99) if player.creatures else 99
            x = opp_max_t
            # Check if Deluge would kill BUG's own board too
            bug_loses = [c for c in player.creatures if c.toughness <= x]
            life_cost = x
            if player.life - life_cost > 4:  # don't suicide
                spend(deluge_card)
                player.remove_from_hand(deluge_card)
                player.add_to_grave(deluge_card)
                player.life -= life_cost
                # Kill opp creatures
                killed_opp = [c for c in opponent.creatures if c.toughness <= x]
                for c in killed_opp:
                    opponent.remove_creature(c)
                    opponent.revolt_this_turn = True
                # Kill BUG's own creatures too (oracle: ALL creatures)
                killed_bug = [c for c in player.creatures if c.toughness <= x]
                for c in killed_bug:
                    player.remove_creature(c)
                log_fn(f"★ Toxic Deluge X={x} (−{life_cost} life → {player.life})"
                    f" — opp kills: {[c.name for c in killed_opp]}"
                    f", BUG kills: {[c.name for c in killed_bug]}", key=True)
                update_goyf(gs)

    # Surgical Extraction — exile target card + all copies from GYs
    surgical_card = player.find_tag('surgical')
    if surgical_card:
        # Oracle: target must already be IN a graveyard (not proactive)
        target_card = next((c for c in opponent.graveyard
                            if c.is_combo_piece), None)
        if target_card:
            player.cast_spell(surgical_card, log_fn=log_fn)  # pays life_cost=2, logs
            target_name = target_card.name
            removed = 0
            # Exile from OPP GY (the target itself and same-name copies)
            for c in [c for c in opponent.graveyard if c.name == target_name]:
                opponent.graveyard.remove(c); player.exile.append(c); removed += 1
            # Exile from OPP hand
            for c in [c for c in opponent.hand if c.name == target_name]:
                opponent.hand.remove(c); player.exile.append(c); removed += 1
            # Exile from OPP library
            for c in [c for c in opponent.library if c.name == target_name]:
                opponent.library.remove(c); player.exile.append(c); removed += 1
            # Oracle: ONLY the target card's owner shuffles their library
            random.shuffle(opponent.library)
            log_fn(f"★ Surgical Extraction → exiles {removed} copies of {target_name}"
                f" (opp shuffles library)", key=True)
            update_goyf(gs)

    # Mindbreak Trap — if opp cast 3+ spells this turn (free), exile all stack spells
    # Simplified: cast proactively as a pre-emptive hold against Storm
    # (Full implementation would require tracking spells cast per turn)
    # For now: treat as FoW variant that counters Storm/Oops win conditions
    # Actual handling done in Storm/Oops opponent strategy functions

    # ── Threat deployment — flood-risk gate + hold-mana logic ──
    # If opp has 3+ open mana and likely FoW, stop at 1 threat per turn.
    # At board-zero or racing, always deploy regardless.
    opp_open_mana = opponent.available_mana_count()
    opp_likely_fow = any(c.free_cast_if_blue for c in opponent.hand)
    flood_risk = (opp_open_mana >= IP.FLOOD_RISK_MANA and opp_likely_fow and
                  bug_threat_count >= IP.BOWM_HOLD_MIRROR and game_state != 'racing')
    threats_this_turn = [0]
    def ok_to_deploy(): return threats_this_turn[0] == 0 or not flood_risk

    # Hold-mana check: should BUG hold 1B open for Fatal Push / Flash Bowmasters
    # rather than tapping out for a sorcery-speed threat?
    # Conditions to hold mana:
    #   (a) opp has a creature on board that Push can kill, AND
    #   (b) BUG has Push or Bowmasters in hand, AND
    #   (c) game_state is 'behind' or 'parity' (ahead: deploy freely), AND
    #   (d) BUG already has a threat on board (so not desperate for a body)
    push_in_hand = player.find_tag('push') is not None
    bowm_in_hand = player.find_tag('bowm') is not None and not gs.bowmasters_on_board
    opp_has_killable = any(MTGRules.fatal_push_valid_target(c, True) for c in opponent.creatures)
    hold_for_push = (push_in_hand and opp_has_killable and
                     game_state in ('behind', 'parity') and bug_threat_count >= 1)
    hold_for_bowm = (bowm_in_hand and opp_has_cantrips and
                     game_state in ('parity',) and bug_threat_count >= 1)
    # If holding mana: don't deploy the SECOND sorcery-speed threat
    # (we still deploy the first — empty board is always worse than threat + held mana)
    hold_mana = hold_for_push or hold_for_bowm

    # ── Tamiyo — C1: needs 1U ──
    tam = player.find_tag('tamiyo')
    if tam and not gs.tamiyo_flipped and not gs.spell_blocked_by_chalice(tam.cmc) and ok_to_deploy():
        if not any(c.card.tag == 'tamiyo' for c in player.creatures):
            if budget[0] >= effective_cmc(tam) and can_afford(player, tam.mana_cost):
                spend(tam)
                player.remove_from_hand(tam)
                if try_reactive_counter(gs, player, opponent, tam, log_entries):
                    player.add_to_grave(tam)
                else:
                    perm = player.put_creature_in_play(tam)
                    threats_this_turn[0] += 1
                    log_fn(f"Cast Tamiyo (CMC 1, summoning sick)")

    # ── Tarmogoyf / Nethergoyf — C1 ──
    # Nethergoyf: P/T = types in YOUR GY (own graveyard only).
    # Tarmogoyf: P/T = types in ALL graveyards (both). update_goyf handles ongoing sizing.
    goyf = player.find_tag('goyf') or player.find_tag('nether')
    if goyf and not gs.spell_blocked_by_chalice(goyf.cmc) and ok_to_deploy() and not (hold_mana and threats_this_turn[0] >= 1):
        if budget[0] >= effective_cmc(goyf) and can_afford(player, goyf.mana_cost):
            spend(goyf)
            player.remove_from_hand(goyf)
            if try_reactive_counter(gs, player, opponent, goyf, log_entries):
                player.add_to_grave(goyf)
            else:
                perm = player.put_creature_in_play(goyf)
                if goyf.tag == 'nether':
                    pw, pt = MTGRules.tarmogoyf_pt(player.graveyard, [])
                else:
                    pw, pt = MTGRules.tarmogoyf_pt(player.graveyard, opponent.graveyard)
                perm.power_mod = pw - goyf.base_power
                perm.toughness_mod = pt - goyf.base_toughness
                threats_this_turn[0] += 1
                log_fn(f"Cast {goyf.name} (CMC 2, sick, P/T {perm.power}/{perm.toughness})")

    # ── Brazen Borrower — C1: 3/1 flying flash; deploy as threat if board needs it ──
    borrow_threat = player.find_tag('borrow')
    if borrow_threat and not gs.spell_blocked_by_chalice(borrow_threat.cmc):
        # Only deploy if we have no other threat on board (Borrower is a backup threat)
        no_threats_on_board = not any(c.card.tag not in ('borrow',) for c in player.creatures)
        if no_threats_on_board and budget[0] >= effective_cmc(borrow_threat) and can_afford(player, borrow_threat.mana_cost):
            spend(borrow_threat)
            player.remove_from_hand(borrow_threat)
            if try_reactive_counter(gs, player, opponent, borrow_threat, log_entries):
                player.add_to_grave(borrow_threat)
            else:
                player.put_creature_in_play(borrow_threat)
                log_fn(f"Cast Brazen Borrower (CMC 3, flash, 3/1 flying)")

    # ── Murktide via delve — C1: needs 1U + delve ──
    murk = player.find_tag('murk')
    spell_count = player.spell_count_in_graveyard()
    if murk and spell_count >= IP.MURKTIDE_DELVE_MIN and not gs.spell_blocked_by_chalice(0) and ok_to_deploy() and not (hold_mana and threats_this_turn[0] >= 1):
        delve_cost = {'U': 1, 'generic': max(0, 6 - spell_count)}
        if budget[0] >= effective_cmc(murk) and can_afford(player, murk.mana_cost):
            spend(murk)
            player.remove_from_hand(murk)
            if try_reactive_counter(gs, player, opponent, murk, log_entries):
                player.add_to_grave(murk)
            else:
                exiled = min(spell_count, 6)
                ex_cards = [c for c in player.graveyard
                        if c.card_type in (CardType.INSTANT, CardType.SORCERY)][:exiled]
                for c in ex_cards:
                    player.graveyard.remove(c)
                    player.exile.append(c)
                perm = player.put_creature_in_play(murk)
                perm.power_mod = exiled - murk.base_power
                perm.toughness_mod = exiled - murk.base_toughness
                log_fn(f"Murktide via delve ({exiled} exiled) → {perm.power}/{perm.toughness}",
                    key=True)

    # ── Kaito, Bane of Nightmares — Ninjutsu {1UB}: 3/4 hexproof, draw on damage ──
    # Deploy either: (a) cast at sorcery speed for {1UB}=3, or
    # (b) Ninjutsu via unblocked attacker (handled in resolve_combat if Kaito in hand).
    # Here: cast if we have 3 mana and a threat in play to set up Ninjutsu next turn.
    kaito = player.find_tag('kaito')
    kaito_in_play = any(c.card.tag == 'kaito' for c in player.creatures + player.planeswalkers)
    if kaito and not kaito_in_play and not gs.spell_blocked_by_chalice(kaito.cmc):
        # Prefer Ninjutsu window — don't hard-cast if a cheaper attacker is already active
        has_attacker = any(not c.summoning_sick and not c.tapped for c in player.creatures)
        can_ninjutsu = has_attacker and budget[0] >= 3  # {1UB}
        can_cast = budget[0] >= effective_cmc(kaito) and can_afford(player, kaito.mana_cost)
        if can_cast and ok_to_deploy() and not (hold_mana and threats_this_turn[0] >= 1):
            spend(kaito)
            player.remove_from_hand(kaito)
            if try_reactive_counter(gs, player, opponent, kaito, log_entries):
                player.add_to_grave(kaito)
            else:
                perm = player.put_creature_in_play(kaito)
                threats_this_turn[0] += 1
                drawn = player.draw(1)
                log_fn(f"Cast Kaito, Bane of Nightmares (3/4 hexproof) → Surveil 2, draw 1 [{drawn[0].name if drawn else 'empty'}]", key=True)
                update_goyf(gs)


    # ── EOT Bowmasters flash (mirror matchups) ──
    # If we held Bowmasters in main phase waiting for their cantrip, deploy it now
    # at instant speed on our end step. Opp will cantrip on THEIR turn and we fire then.
    bowm_eot = player.find_tag('bowm')
    if (bowm_eot and not gs.bowmasters_on_board and
            MC.is_mirror(gs) and
            not gs.spell_blocked_by_chalice(bowm_eot.cmc) and
            can_afford(player, bowm_eot.mana_cost) and
            player.available_mana_count() >= effective_cmc(bowm_eot)):
        _deduct(budget, effective_cmc(bowm_eot), bowm_eot)
        player.remove_from_hand(bowm_eot)
        player.put_creature_in_play(bowm_eot)
        gs.bowmasters_on_board = True
        log_fn("★ Bowmasters EOT flash (mirror — fires on their upkeep/cantrip)", True)


def _check_tamiyo_flip(gs, player, log):
    """Check if Tamiyo should flip (drew 3+ cards this turn)."""
    tam_perm = next((c for c in player.creatures if c.card.tag == 'tamiyo'), None)
    if tam_perm and not gs.tamiyo_flipped and not tam_perm.tapped:
        if player.draws_this_turn >= 3:
            gs.tamiyo_flipped = True
            tam_perm.power_mod = 3
            tam_perm.toughness_mod = 0
            log("★ Tamiyo flips → Tamiyo, Seasoned Scholar (drew 3rd card this turn)", key=True)


def _trace_board_state(player, opponent, log):
    """Emit trace-level board state summary at end of turn."""
    creatures = ', '.join(f"{c.card.name} ({c.power}/{c.toughness})" for c in player.creatures) or '(none)'
    lands = ', '.join(l.card.name for l in player.lands) or '(none)'
    arts = ', '.join(a.card.name for a in player.artifacts)
    log(f"  Board: Lands[{lands}]  Creatures[{creatures}]" +
        (f"  Artifacts[{arts}]" if arts else ""))
    log(f"  Hand ({len(player.hand)}): {', '.join(c.name for c in player.hand) or '(empty)'}")
    if player.graveyard:
        gy_names = ', '.join(c.name for c in player.graveyard[:15])
        suffix = f" +{len(player.graveyard)-15} more" if len(player.graveyard) > 15 else ""
        log(f"  GY ({len(player.graveyard)}): {gy_names}{suffix}")
    log(f"  Library: {len(player.library)} cards")


# ─────────────────────────────────────────────
# OPPONENT turn
# ─────────────────────────────────────────────

def opp_turn(gs: GameState, turn: int, matchup: str):
    """P2's turn — symmetric counterpart to protagonist_turn (P1)."""
    player = gs.p2             # active player this turn (P2)
    opponent = gs.p1           # opposing player (P1)
    o, b = player, opponent    # short aliases (legacy, used throughout)
    log_entries = []
    gs.p2_spells_cast_this_turn = 0
    gs.veil_active = False
    gs.teferi_active = False

    def log(msg, key=False):
        gs.log_event('p2', 'main', msg, key)
        log_entries.append(msg)

    # ── Cleanup from previous turn — CR 510.2 ──
    for player in [b, o]:
        for c in player.creatures:
            c.damage_marked = 0
            # Clear hexproof granted by until-EOT effects (Vines of Vastwood,
            # Blossoming Defense). Permanent hexproof is on the card, not the perm.
            if hasattr(c, 'hexproof'):
                del c.hexproof

    # ── Untap ──
    o.untap_all()
    o.revolt_this_turn = False
    o.clear_summoning_sickness()
    gs.combat_this_turn = False
    if gs.trace:
        log(f"── Untap ── ({len(o.lands)} lands)")

    # ── Draw (first player on play skips T1 draw) ──
    if gs.trace:
        if turn == 1 and not gs.p1_goes_first:
            log("── Draw ── (skipped — on the play, T1)")
        else:
            log("── Draw ──")
    if not (turn == 1 and not gs.p1_goes_first):
        drawn = o.draw(1, is_draw_step=True)  # first draw step card — Bowmasters exempt
        if drawn:
            log(f"Draw: {drawn[0].name}")
            # Bowmasters does NOT trigger on the first draw in a draw step (oracle)
            # It triggers on all other draws (cantrips, extra draws, etc.)

    # ── Land ──
    land = o.find_any(lambda c: c.is_land())
    if land:
        perm = o.play_land(land)
        if perm:
            # CR 613: apply all active continuous effects to newly entered land
            gs.apply_continuous_effects(perm)
            if perm.is_fetch:
                fetched = o.use_fetch(perm)
                if fetched:
                    gs.apply_continuous_effects(fetched)
                    log(f"Play+crack {land.name} (−1 life, {o.life}) → {fetched.name}")
            else:
                log(f"Land: {land.name} ({len(o.lands)} lands)")

    # ── Tap lands ──
    if gs.trace:
        log(f"── Main ──")
        log(f"  Hand ({len(o.hand)}): {', '.join(c.name for c in o.hand)}")
    # om = available mana from untapped lands (on-demand tapping)
    om = o.available_mana_count()
    # Lotus Petal: sac for any color mana (+1 each)
    om += sum(1 for c in o.hand if c.tag == 'petal')
    # Ragavan Treasure tokens from previous turn
    if getattr(gs, 'p2_treasure', 0) > 0:
        om += gs.p2_treasure
        if gs.p2_treasure > 0:
            log(f"Treasure ({gs.p2_treasure}) → +{gs.p2_treasure} mana")
        gs.p2_treasure = 0
    # Ancient Tomb: produces 2C but deals 2 damage when tapped (CR 702.9)
    tomb_count = sum(1 for l in o.lands if l.card.tag == 'tomb' and not l.tapped)
    if tomb_count > 0:
        om += tomb_count
        o.life -= tomb_count * 2
    # City of Traitors: produces 2C like Tomb but no life loss
    if gs.trace:
        log(f"  Mana available: {om}")

    # ── Rishadan Port: tap target BUG land during opponent's upkeep ──
    # Oracle: {T}: tap target land — fire ALL untapped Port copies, not just one.
    # With 4 Ports, turns 3+ lock 2-3 BUG lands before BUG even untaps.
    if matchup in MC.VIAL_DECKS:
        def land_value(lp):
            if lp.card.tag == 'dual': return 3
            if lp.card.is_fetch: return 2
            if lp.card.is_basic: return 1
            return 0
        for port in [l for l in o.lands if l.card.tag == 'port' and not l.tapped]:
            untapped_bug = [l for l in b.lands if not l.tapped]
            if not untapped_bug:
                break
            target = max(untapped_bug, key=land_value)
            target.tapped = True
            port.tapped = True
            log(f"Rishadan Port taps {target.name} (BUG loses 1 mana)", True)

    # ── Gameplan layer — compute board assessment + active goal ──
    # Exposes posture to individual strategy functions via gs.p2_goal
    plan = GAMEPLANS.get(matchup)
    if plan:
        ba = assess(gs, turn)
        gs.p2_goal = active_goal(plan, ba)
    else:
        gs.p2_goal = None

    # ── Lock piece enforcement (shared helpers — single source of truth) ──
    _adjustments = apply_lock_effects(gs, o, log)

    # ── Matchup dispatch (all decks via registry) ──
    from deck_registry import get_strategy
    strategy_fn = get_strategy(matchup)
    if strategy_fn:
        player, opponent = gs.p2, gs.p1
        def _plugin_log(msg, key=False):
            gs.log_event('o', 'main', msg, key)
            log_entries.append(msg)
        try:
            strategy_fn(player, opponent, gs, om, _plugin_log, log_entries)
        except Exception as e:
            log(f"⚠ Strategy error ({matchup}): {e} — forfeiting turn")

    # ── Post-strategy: restore lock adjustments ──
    restore_lock_effects(o, _adjustments)

    # ── Tamiyo flip check (P2's Tamiyo can flip if drew 3+ this turn) ──
    _check_tamiyo_flip(gs, o, log)

    # ── P1 instant-speed responses during P2's turn ──
    if not gs.game_over:
        _p1_respond_on_opp_turn(gs, log, log_entries)

    # ── Fallback combat: attack with eligible creatures if strategy didn't ──
    if not gs.combat_this_turn and not gs.game_over and o.creatures:
        attackers = _select_attackers(o, b)
        if attackers:
            if gs.trace:
                log(f"── Combat ── ({len(attackers)} attackers)")
            combat_declare(o, b, gs, log_entries, attackers)

    gs.state_based_actions()

    if gs.trace:
        log("── End ──")

    return log_entries


# ─────────────────────────────────────────────
# Shared opp utilities
# ─────────────────────────────────────────────

def opp_to_grave_or_exile(gs, card):
    """Route opp card to GY or exile depending on Leyline of the Void."""
    if gs.leyline_active:
        gs.p2.exile.append(card)
    else:
        gs.p2.add_to_grave(card)




def _p1_force_of_vigor(gs, target_tags, log_list):
    """
    Force of Vigor — free on opponent's turn: exile a green card, destroy up to 2 artifacts/enchantments.
    Oracle: "If it's not your turn, you may exile a green card from your hand rather than pay."
    Called from opp strategy functions (opponent's turn only).
    """
    b = gs.p1
    fov = b.find_tag('fov')
    if not fov: return False
    green_pitch = next((c for c in b.hand if 'G' in c.colors and c.tag not in ('fov','endurance')), None)
    if not green_pitch: return False
    targets = [p for p in gs.p2.artifacts + gs.p2.enchantments
               if p.card.tag in target_tags][:2]
    if not targets: return False
    b.remove_from_hand(fov)
    b.remove_from_hand(green_pitch)
    b.exile.append(green_pitch)
    names = []
    for t in targets:
        tlist = gs.p2.artifacts if t in gs.p2.artifacts else gs.p2.enchantments
        if t in tlist:
            tlist.remove(t)
            gs.p2.add_to_grave(t.card)
            names.append(t.name)
            if t.card.tag == 'chalice': gs.chalice_x = None
            elif t.card.tag == 'bridge': gs.bridge_on_board = False
            elif t.card.tag == 'moon':   gs.set_moon(False)
            elif t.card.tag == 'b2b':    gs.set_b2b(False)
    update_goyf(gs)
    log_list.append(f"★ BUG Force of Vigor (free on opp's turn, exiles {green_pitch.name})"
                    f" → destroys {' + '.join(names)}")
    return True


def _p1_respond_on_opp_turn(gs, log_fn, log_entries):
    """
    P1 instant-speed responses during P2's turn (after P2 strategy, before P2 combat).
    Handles: STP on P2 threats, flash Bowmasters, Force of Vigor, Wasteland.
    """
    b, o = gs.p1, gs.p2

    # ── STP: exile P2's biggest creature if power >= 3 (major threat) ──
    # STP costs 1W; after paying, remaining mana = available - 1
    stp = b.find_tag('stp')
    if stp and o.creatures and b.available_mana_count() >= 1:
        mana_after_stp = b.available_mana_count() - 1
        valid = [c for c in o.creatures if _can_target(c, mana_after_stp)]
        target = max(valid, key=lambda c: c.power) if valid else None
        # STP high-power threats: Marit Lage, Emrakul, Murktide, etc.
        if target and target.power >= 3:
            b.remove_from_hand(stp)
            b.add_to_grave(stp)
            life_gain = MTGRules.stp_life_gain(target)
            o.creatures.remove(target)
            o.life += life_gain
            log_fn(f"★ P1 STP (instant, P2's turn) → exiles {target.card.name} "
                   f"(P2 +{life_gain} life → {o.life})", True)
            update_goyf(gs)
            gs.check_life_totals()

    # ── Flash Bowmasters: deploy during P2's end step if P2 drew cards ──
    bowm = b.find_tag('bowm')
    bowm_on_board = any(c.card.tag == 'bowm' for c in b.creatures)
    if bowm and not bowm_on_board and b.available_mana_count() >= 2:
        # Deploy on P2's turn if P2 has cantrip-heavy deck (Dimir, UWx, etc.)
        p2_drew_extra = o.draws_this_turn > 1
        if p2_drew_extra or len(o.hand) >= 5:
            from game import can_afford
            if can_afford(b, bowm.mana_cost):
                b.remove_from_hand(bowm)
                if not _try_counter_any(b, o, gs, bowm, log_entries):
                    b.put_creature_in_play(bowm)
                    log_fn("★ P1 Flash Bowmasters (P2's turn — punishes next draw)", True)
                else:
                    b.add_to_grave(bowm)

    # ── Force of Vigor: free on opponent's turn, destroy lock pieces ──
    lock_targets = [p.card.tag for p in o.artifacts + o.enchantments if p.card.lock_piece]
    if lock_targets:
        _p1_force_of_vigor(gs, lock_targets, log_entries)

    # ── Wasteland: destroy P2's key nonbasic land ──
    wl = next((l for l in b.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        eligible = [l for l in o.lands if not l.card.is_basic
                    and MTGRules.wasteland_can_target(l)]
        if eligible:
            # Prioritise combo lands (Dark Depths / Thespian's Stage) above all else
            def _wl_p1_prio(land):
                if land.card.tag in ('depths', 'stage'): return 50
                if land.card.mana_ritual: return 5
                return 1
            target = max(eligible, key=_wl_p1_prio)
            b.lands.remove(wl)
            b.add_to_grave(wl.card)
            o.lands.remove(target)
            o.add_to_grave(target.card)
            log_fn(f"★ P1 Wasteland (P2's turn) → destroys {target.card.name}", True)
            update_goyf(gs)


def _p2_respond_on_pro_turn(gs, log_fn, log_entries):
    """
    P2 instant-speed responses during P1's turn (after P1 combat).
    Handles: STP, Fatal Push, Snuff Out, Lightning Bolt on P1 creatures.
    Hexproof creatures (e.g. protected by Vines of Vastwood) cannot be
    targeted by any of these spells (CR 702.11b).
    Ward creatures (CR 702.143) require the caster to pay extra mana or
    the targeting spell is countered on resolution.
    """
    b, o = gs.p1, gs.p2

    # ── STP: exile P1's biggest creature if power >= 3 ──
    # STP costs 1W; after paying, remaining mana = available - 1
    stp = o.find_tag('stp')
    if stp and b.creatures and o.available_mana_count() >= 1:
        mana_after_stp = o.available_mana_count() - 1
        valid = [c for c in b.creatures if _can_target(c, mana_after_stp)]
        if valid:
            target = max(valid, key=lambda c: c.power)
            if target.power >= 3:
                o.remove_from_hand(stp)
                o.add_to_grave(stp)
                life_gain = MTGRules.stp_life_gain(target)
                b.creatures.remove(target)
                b.life += life_gain
                log_fn(f"★ P2 STP (instant, P1's turn) → exiles {target.card.name} "
                       f"(P1 +{life_gain} life → {b.life})", True)
                update_goyf(gs)

    # ── Fatal Push on P1 creature (CMC ≤ 2, or ≤ 4 with revolt) ──
    # Fatal Push costs 1B; after paying, remaining mana = available - 1
    push = o.find_tag('push')
    if push and b.creatures and o.available_mana_count() >= 1:
        revolt = o.revolt_this_turn
        mana_after_push = o.available_mana_count() - 1
        targets = [c for c in b.creatures
                   if MTGRules.fatal_push_valid_target(c, revolt) and _can_target(c, mana_after_push)]
        if targets:
            target = max(targets, key=lambda c: c.power)
            if target.power >= 1:  # worth pushing any real threat
                o.remove_from_hand(push)
                o.add_to_grave(push)
                b.creatures.remove(target)
                b.add_to_grave(target.card)
                rev = " [revolt]" if revolt else ""
                log_fn(f"★ P2 Push{rev} (instant, P1's turn) → kills {target.card.name}", True)
                update_goyf(gs)

    # ── Snuff Out (free if controlling Swamp) ──
    # Snuff Out is free (pay 4 life); after paying, all mana remains available
    snuff = o.find_tag('snuffout')
    if snuff and b.creatures and o.life > CT.SNUFF_LIFE_FLOOR_AGGRO:
        has_swamp = any('B' in l.effective_produces() for l in o.lands)
        if has_swamp:
            mana_for_ward = o.available_mana_count()  # free spell — no mana spent
            targets = [c for c in b.creatures
                       if 'B' not in getattr(c.card, 'colors', set())
                       and _can_target(c, mana_for_ward)]
            if targets:
                target = max(targets, key=lambda c: c.power)
                if target.power >= 2:
                    o.remove_from_hand(snuff)
                    o.add_to_grave(snuff)
                    o.life -= 4
                    b.creatures.remove(target)
                    b.add_to_grave(target.card)
                    log_fn(f"★ P2 Snuff Out (free, −4 life → {o.life}, P1's turn) → kills {target.card.name}", True)
                    update_goyf(gs)

    # ── Lightning Bolt on P1 creature ──
    # Bolt costs 1R; after paying, remaining mana = available - 1
    bolt = o.find_tag('bolt') or o.find_tag('heat')
    if bolt and b.creatures and o.available_mana_count() >= 1:
        mana_after_bolt = o.available_mana_count() - 1
        targets = [c for c in b.creatures
                   if c.toughness <= 3 and c.power >= 2 and _can_target(c, mana_after_bolt)]
        if targets:
            target = max(targets, key=lambda c: c.power)
            o.remove_from_hand(bolt)
            o.add_to_grave(bolt)
            target.damage_marked += 3
            log_fn(f"★ P2 Bolt (instant, P1's turn) → {target.card.name} takes 3 damage", True)
            gs.state_based_actions()
            update_goyf(gs)


def _elves_strategy(player, opponent, gs: GameState, total_mana: int,
                    log_fn, log_entries: list):
    """
    Single source of truth for Elves strategic decisions.
    Called by both elves_turn (protagonist) and _opp_elves (antagonist).

    player   = Elves PlayerState (gs.p1 when protagonist, gs.p2 when antagonist)
    opponent = the other PlayerState
    total_mana = mana available this turn (caller computes Cradle + land mana)

    Bowmasters direction: when player draws, opponent's Bowmasters fires.
      bowm_ctrl = 'o' if player is gs.p1 (opp has Bowmasters, pings gs.p1)
                = 'b' if player is gs.p2 (bug has Bowmasters, pings gs.p2)
    """
    bowm_ctrl = 'o' if player is gs.p1 else 'b'
    # Elves mana includes untapped mana dorks (Heritage Druid, Llanowar, etc.)
    dork_mana = player.available_mana_count(include_dorks=True) - player.available_mana_count()
    mana_ref  = [total_mana + dork_mana]  # mutable so do_natural_order can deduct

    def elf_count():
        return len(player.creatures)

    def find_heritage():
        return next((c for c in player.creatures
                     if c.card.tag == 'heritage' and not c.tapped), None)

    def untapped_elves():
        elf_tags = {'llanowar','mystic','heritage','nettle','shepherd','visionary',
                    'symbiote','qranger','recsage','dryad_arbor','espirit','hoof'}
        return [c for c in player.creatures if not c.tapped and c.card.tag in elf_tags]

    shepherd_on_board = gs.shepherd_in_play

    def druid_refuel():
        """Tap Heritage Druid + 2 others for GGG. Returns True if activated."""
        ue = untapped_elves()
        hd = find_heritage()
        if len(ue) >= 3 and hd:
            others = [c for c in ue if c is not hd][:2]
            for c in [hd] + others:
                c.tapped = True
            mana_ref[0] += 3
            return True
        return False

    hoof_in_lib = any(c.tag == 'hoof' for c in player.library)

    def do_natural_order(natorder_card):
        """Execute Natural Order → Craterhoof. Sacrifice paid before counter (CR 601.2b)."""
        player.remove_from_hand(natorder_card)
        player.add_to_grave(natorder_card)
        # Additional cost: sacrifice smallest non-Heritage elf (paid on cast, before stack)
        sac_pool = [c for c in player.creatures if c.card.tag != 'heritage']
        if not sac_pool:
            sac_pool = list(player.creatures)
        if sac_pool:
            sac = min(sac_pool, key=lambda c: c.power)
            player.remove_creature(sac)
            player.add_to_grave(sac.card)
        # Try to counter (skip if Shepherd active — green spells uncounterable)
        if not shepherd_on_board:
            if _try_counter_any(player, opponent, gs, natorder_card, log_entries):
                log_fn("Natural Order countered (sac still paid)")
                return False
        hoof_card = next((c for c in player.library if c.tag == 'hoof'), None)
        if not hoof_card:
            return False
        player.library.remove(hoof_card)
        player.put_creature_in_play(hoof_card)
        n = elf_count()
        for c in player.creatures:
            c.power_mod       = getattr(c, 'power_mod', 0) + n
            c.toughness_mod   = getattr(c, 'toughness_mod', 0) + n
        log_fn(f"★ Natural Order → Craterhoof ETB: {n} creatures +{n}/+{n} trample", True)
        mana_ref[0] -= 4
        return True

    # ── Priority 1: Allosaurus Shepherd ──
    # Oracle: "Allosaurus Shepherd can't be countered." — always resolves.
    shepherd_card = player.find_tag('shepherd')
    if shepherd_card and not shepherd_on_board and mana_ref[0] >= 1:
        player.remove_from_hand(shepherd_card)
        player.put_creature_in_play(shepherd_card)
        shepherd_on_board = True
        mana_ref[0] -= 1
        log_fn("★ Allosaurus Shepherd — always resolves (can't be countered)", True)

    # ── Priority 2: Glimpse of Nature chain ──
    glimpse   = player.find_tag('glimpse')
    heritage  = find_heritage()
    natorder  = player.find_tag('natorder')

    if (glimpse and heritage and elf_count() >= 2 and mana_ref[0] >= 1
            and can_afford(player, glimpse.mana_cost)):
        player.remove_from_hand(glimpse)
        player.add_to_grave(glimpse)
        log_fn("★ Glimpse of Nature — chain begins", True)
        mana_ref[0] -= 1
        chain_spells = chain_draws = 0

        for _step in range(20):
            if mana_ref[0] < 1:
                if not druid_refuel():
                    break
            next_elf = next((c for c in player.hand
                             if c.is_creature() and c.cmc <= 1 and 'G' in c.colors), None)
            if not next_elf:
                break
            player.remove_from_hand(next_elf)
            player.put_creature_in_play(next_elf)
            mana_ref[0] -= max(1, next_elf.cmc)
            chain_spells += 1
            drawn = player.draw(1)
            chain_draws += 1
            bowmasters_triggers(1, gs, log_entries, controller=bowm_ctrl)
            for c in player.creatures:
                if c.card.tag == 'nettle' and c.tapped:
                    c.tapped = False
            if next_elf.tag == 'visionary':
                vis = player.draw(1)
                if vis:
                    chain_draws += 1
                    bowmasters_triggers(1, gs, log_entries, controller=bowm_ctrl)

        log_fn(f"  Glimpse chain: {chain_spells} elves, {chain_draws} draws, {elf_count()} in play")

        natorder = player.find_tag('natorder')
        if natorder and hoof_in_lib and elf_count() >= 3:
            druid_refuel()
            if mana_ref[0] >= 4 or shepherd_on_board:
                do_natural_order(natorder)

    # ── Priority 3: Natural Order direct ──
    natorder      = player.find_tag('natorder')
    glimpse_useful = (player.find_tag('glimpse') is not None
                      and find_heritage() is not None and elf_count() >= 2)
    if (natorder and not glimpse_useful and hoof_in_lib
            and mana_ref[0] >= 4 and elf_count() >= 3
            and can_afford(player, natorder.mana_cost)):
        do_natural_order(natorder)

    # ── Priority 4: Build phase — deploy all affordable elves each turn ──
    ramp_tags  = ['llanowar', 'mystic', 'heritage', 'shepherd']
    combo_tags = ['nettle', 'visionary', 'symbiote', 'qranger', 'recsage']
    deploy_tags = ramp_tags + combo_tags

    for tag in deploy_tags:
        elf_card = player.find_tag(tag)
        if not elf_card: continue
        if mana_ref[0] < max(1, elf_card.cmc): continue
        if not can_afford(player, elf_card.mana_cost): continue
        player.remove_from_hand(elf_card)
        if _try_counter_any(player, opponent, gs, elf_card, log_entries):
            player.add_to_grave(elf_card)
            continue
        player.put_creature_in_play(elf_card)
        mana_ref[0] -= max(1, elf_card.cmc)
        log_fn(f"{elf_card.name} ({elf_card.base_power}/{elf_card.base_toughness})")
        if tag == 'visionary':
            vis = player.draw(1)
            if vis:
                bowmasters_triggers(1, gs, log_entries, controller=bowm_ctrl)

    # ── Priority 5: GSZ ──
    gsz = player.find_tag('gsz')
    if gsz and mana_ref[0] >= 1 and can_afford(player, {'G': 1}):
        want = {'heritage': not any(c.card.tag == 'heritage' for c in player.creatures),
                'shepherd': not shepherd_on_board,
                'visionary': elf_count() < 3}
        target_tag = next((t for t, w in want.items()
                           if w and any(c.tag == t for c in player.library)), None)
        if target_tag:
            player.remove_from_hand(gsz)
            countered = (not shepherd_on_board
                         and _try_counter_any(player, opponent, gs, gsz, log_entries))
            player.library.append(gsz)
            import random; random.shuffle(player.library)
            if countered:
                log_fn("GSZ countered")
            else:
                tgt = next((c for c in player.library if c.tag == target_tag), None)
                if tgt:
                    player.library.remove(tgt)
                    player.put_creature_in_play(tgt)
                    log_fn(f"GSZ → {tgt.name}")

    # ── Combat ──
    attackers = [c for c in player.creatures if not c.summoning_sick and c.power > 0]
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)

    gs.state_based_actions()



def _try_counter_any(player, opponent, gs: GameState, spell_card, log_list: list) -> bool:
    """
    Unified counter attempt — works regardless of which role the deck plays.
    player is casting, opponent (defender) tries to counter.
    """
    defender = gs.p2 if player is gs.p1 else gs.p1
    return try_reactive_counter(gs, player, defender, spell_card, log_list)


def combat_declare(player, opponent, gs, log_entries, attackers):
    """
    Declare attackers and resolve combat.
    Only the supplied `attackers` list enters combat — all other creatures
    (held back for value, summoning sick, designated blockers) stay out.
    Enforces Ensnaring Bridge and Maze of Ith.
    """
    if not attackers:
        return

    gs.combat_this_turn = True

    # Ensnaring Bridge: creatures with power > controller's hand size can't attack (CR 702.9)
    if gs.bridge_on_board:
        bridge_controller = gs.p1 if any(
            getattr(a, 'card', None) and a.card.tag == 'bridge' for a in gs.p1.artifacts
        ) else gs.p2
        hand_size = len(bridge_controller.hand)
        blocked = [a for a in attackers if a.power > hand_size]
        attackers = [a for a in attackers if a.power <= hand_size]
        if blocked:
            names = ', '.join(a.card.name for a in blocked)
            log_entries.append(f"  Bridge blocks attack: {names} (power > {hand_size} cards in hand)")
        if not attackers:
            return

    # Maze of Ith: tap to remove attacker from combat (strongest attacker)
    defender = gs.p2 if player is gs.p1 else gs.p1
    maze = next((l for l in defender.lands if l.card.tag == 'maze' and not l.tapped), None)
    if maze and attackers:
        biggest = max(attackers, key=lambda a: a.power)
        if biggest.power >= 2:  # only worth Mazing a real threat
            maze.tapped = True
            attackers = [a for a in attackers if a is not biggest]
            log_entries.append(f"  Maze of Ith removes {biggest.card.name} from combat")
            if not attackers:
                return

    orig = player.creatures
    player.creatures = list(attackers)
    resolve_combat(gs, player, opponent, log_entries)
    player.creatures = orig


def _strategy_elves(player, opponent, gs, total_mana, log_fn, log_entries):
    """Elves strategy — delegates to _elves_strategy (the shared implementation)."""
    _elves_strategy(player, opponent, gs, total_mana, log_fn, log_entries)



def _strategy_dnt(player, opponent, gs, total_mana, log_fn, log_entries):
    """Death and Taxes: Aether Vial + tax creatures + land denial.

    Mother of Runes: if untapped on board, protects most valuable creature
    from targeted removal. Modeled as gs._mom_protected_tag — the tag of
    the creature MoR is protecting this turn. Removal targeting that
    creature fails (checked in opp_can_remove).

    Priority vs aggro (creatures on opponent's board):
      1. Swords to Plowshares (exile + life gain)
      2. Solitude (free evoke exile + life gain)
      3. Thalia (taxes noncreature spells)
      4. Aether Vial (free creature deployment)
      5. Other creatures via Vial or hard-cast

    Priority vs combo/control (no creatures):
      1. Aether Vial T1
      2. Thalia T2 (tax their cantrips/rituals)
      3. Stoneforge Mystic (tutor equipment)
      4. Wasteland + Port (deny mana)
    """

    # ── Mother of Runes: protect most valuable creature ──
    # MoR taps to give protection from a color → prevents targeted removal.
    # Model: flag the most important creature as protected for this turn cycle.
    mom_perm = next((c for c in player.creatures
                     if c.card.tag == 'mom' and not c.summoning_sick), None)
    gs._mom_protected_tag = None
    if mom_perm and len(player.creatures) >= 2:
        # Protect the most valuable non-MoR creature
        protect_priority = {'thalia': 10, 'sfm': 8, 'skyclave': 7, 'phelia': 6,
                            'flickerwisp': 5, 'solitude': 5, 'recruiter': 3}
        best = max((c for c in player.creatures if c.card.tag != 'mom'),
                   key=lambda c: protect_priority.get(c.card.tag, 1), default=None)
        if best:
            gs._mom_protected_tag = best.card.tag
            log_fn(f"Mother of Runes protects {best.card.name}")

    # ── 0. Swords to Plowshares — FIRST PRIORITY vs any creature ──
    # Real DnT always fires STP before deploying own threats.
    # Exile their best threat and GAIN LIFE (critical vs Burn).
    while True:
        stp = player.find_tag('stp')
        if not stp or not opponent.creatures:
            break
        if not opp_can_cast(stp, total_mana, gs, caster=player):
            break
        # STP costs 1W; mana remaining after casting = total_mana - 1 (for ward check)
        mana_after_stp = total_mana - 1
        valid_stp = [c for c in opponent.creatures if _can_target(c, mana_after_stp)]
        target = max(valid_stp, key=lambda c: c.power + c.toughness) if valid_stp else None
        if not target or target.power < 1:
            break  # don't waste STP on 0-power creatures or ward-protected targets
        player.remove_from_hand(stp); player.add_to_grave(stp)
        total_mana -= 1
        life_gain = MTGRules.stp_life_gain(target)
        opponent.remove_creature(target, to_exile=True)
        opponent.life += life_gain
        log_fn(f"Swords to Plowshares exiles {target.card.name} (+{life_gain} life)")
        update_goyf(gs)
        if not opponent.creatures:
            break

    # ── 1. Solitude — free evoke (exile white card) vs any creature ──
    # Evoke = free, exile opponent's creature, player gains life = toughness.
    # Critical vs Burn: removes Eidolon/Guide/Swiftspear AND gains life.
    # NEVER pitch Thalia (too valuable as tax piece).
    solitude = player.find_tag('solitude')
    if solitude and opponent.creatures:
        # Prefer pitching low-value white cards (not Thalia, not STP)
        _pitch_priority = {'recruiter': 1, 'orchid': 1, 'flickerwisp': 2,
                           'phelia': 2, 'mom': 2, 'sfm': 3, 'equipment': 3,
                           'kaldra': 3, 'skyclave': 3, 'solitude': 5}
        white_candidates = [c for c in player.hand
                            if 'W' in getattr(c, 'colors', set())
                            and c is not solitude and c.tag != 'thalia' and c.tag != 'stp']
        white_pitch = min(white_candidates, key=lambda c: _pitch_priority.get(c.tag, 4),
                          default=None) if white_candidates else None
        if white_pitch:
            # Solitude evoke is free (pitch + 0 mana); full mana available for ward
            valid_sol = [c for c in opponent.creatures if _can_target(c, total_mana)]
            target = max(valid_sol, key=lambda c: c.power + c.toughness) if valid_sol else None
            if target and target.power >= 1:
                player.remove_from_hand(solitude); player.add_to_grave(solitude)
                player.remove_from_hand(white_pitch); player.exile.append(white_pitch)
                life_gain = target.toughness
                opponent.remove_creature(target, to_exile=True)
                player.life += life_gain
                log_fn(f"★ Solitude (evoke, pitch {white_pitch.name}) exiles {target.card.name} (+{life_gain} life)", True)
                update_goyf(gs)

    # ── 2. Aether Vial — highest priority T1-T3 ──
    vial = player.find_tag('vial')
    vial_on_board = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial and not vial_on_board and total_mana >= 1 and gs.turn <= 3:
        player.remove_from_hand(vial)
        if not _try_counter_any(player, opponent, gs, vial, log_entries):
            player.put_artifact_in_play(vial)
            gs.vial_counters = 0
            gs._vial_entered_last_turn = True
            total_mana -= 1
            log_fn("Aether Vial enters play")
        else:
            player.add_to_grave(vial)

    # Vial upkeep tick
    vial_tags = ('thalia', 'mom', 'phelia', 'skyclave', 'recruiter', 'flickerwisp',
                 'solitude', 'sfm', 'orchid', 'eidolon', 'bowm')
    vial_perm = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial_perm:
        if gs._vial_entered_last_turn:
            gs._vial_entered_last_turn = False
        elif gs.vial_counters < 3:
            gs.vial_counters += 1
            log_fn(f"Aether Vial — {gs.vial_counters} counter(s)")

    # ── 3. Deploy creatures — priority order matters ──
    # Thalia FIRST (taxes opponent's spells), then SFM (tutors equipment),
    # then other threats. Recruiter last (value, not tempo).
    deploy_priority = ['thalia', 'sfm', 'skyclave', 'phelia', 'flickerwisp',
                       'orchid', 'mom', 'recruiter']

    # Hard cast creatures — always deploy when mana available.
    # Vial handles EXTRA deployments at instant speed (EOT/combat),
    # but main phase should still hard-cast with available mana.
    deployed_this_turn = 0
    max_deploys = 2 if total_mana >= 4 else 1
    if True:
        for tag in deploy_priority:
            crea = player.find_tag(tag)
            if not crea or not opp_can_cast(crea, total_mana, gs, caster=player):
                continue
            gs.strat_log.log_decision(
                gs.turn, 'dnt',
                candidates=deploy_priority,
                chosen=tag,
                reason=f"mana={total_mana}, hand={[c.tag for c in player.hand]}")
            player.remove_from_hand(crea)
            if not _try_counter_any(player, opponent, gs, crea, log_entries):
                player.put_creature_in_play(crea)
                total_mana -= crea.cmc
                log_fn(f"{crea.name} ({crea.base_power}/{crea.base_toughness})")
                # ETB triggers
                if tag == 'skyclave' and opponent.creatures:
                    # Priority: Eidolon (punishes all our spells) > biggest threat
                    target = next((c for c in opponent.creatures if c.card.tag == 'eidolon'), None)
                    if not target:
                        target = next((c for c in opponent.creatures if c.card.cmc <= 4), None)
                    if target:
                        opponent.remove_creature(target)
                        if target.card.tag == 'eidolon':
                            gs.eidolon_active = False
                        log_fn(f"  Skyclave Apparition exiles {target.card.name}")
                if tag == 'recruiter':
                    found = next((c for c in player.library
                                  if c.is_creature() and c.base_power <= 2), None)
                    if found:
                        player.library.remove(found); player.hand.append(found)
                        log_fn(f"  Recruiter tutors {found.name}")
                if tag == 'sfm':
                    equip = next((c for c in player.library if c.tag in CR.EQUIPMENT_SET), None)
                    if equip:
                        player.library.remove(equip); player.hand.append(equip)
                        log_fn(f"  Stoneforge Mystic tutors {equip.name}")
                if tag == 'flickerwisp':
                    tgt = max(opponent.creatures, key=lambda c: c.power, default=None)
                    if tgt:
                        opponent.remove_creature(tgt)
                        new_p = opponent.put_creature_in_play(tgt.card)
                        new_p.summoning_sick = True
                        log_fn(f"  Flickerwisp blinks {tgt.card.name}")
                        update_goyf(gs)
            else:
                player.add_to_grave(crea)
            deployed_this_turn += 1
            if deployed_this_turn >= max_deploys:
                break

    # SFM activated: put equipment into play
    sfm_perm = next((p for p in player.creatures if p.card.tag == 'sfm'), None)
    equip_card = player.find_tag('equipment') or player.find_tag('kaldra')
    if sfm_perm and equip_card and total_mana >= 1:
        player.remove_from_hand(equip_card)
        player.put_artifact_in_play(equip_card)
        if player.creatures:
            biggest = max((c for c in player.creatures if c.card.tag != 'sfm'),
                         key=lambda c: c.power, default=None)
            if biggest:
                biggest.power_mod += 3; biggest.toughness_mod += 3
                log_fn(f"  {equip_card.name} equipped to {biggest.card.name} (+3/+3)", True)

    # ── 4. Wasteland — destroy opponent's nonbasic lands ──
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        targets = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if targets:
            target = max(targets, key=lambda l: 3 if l.card.tag == 'dual' else 2 if l.is_fetch else 1)
            player.lands.remove(wl); player.add_to_grave(wl.card)
            player.revolt_this_turn = True
            opponent.lands.remove(target); opponent.add_to_grave(target.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland → destroys {target.card.name}")
            update_goyf(gs)

    # Karakas — bounce legendary creatures
    for karakas in [l for l in player.lands if l.card.tag == 'karakas' and not l.tapped]:
        murktide = next((c for c in opponent.creatures if c.card.tag == 'murk'), None)
        if murktide:
            karakas.tapped = True
            opponent.creatures.remove(murktide)
            opponent.hand.append(murktide.card)
            log_fn(f"★ Karakas → returns {murktide.card.name}", True)
            break

    # ── 4b. Rishadan Port — tap opponent's lands to deny mana ──
    # Port is devastating vs low-land decks like Burn: each Port tap = 1 fewer spell.
    for port in [l for l in player.lands if l.card.tag == 'port' and not l.tapped]:
        opp_untapped = [l for l in opponent.lands if not l.tapped]
        if opp_untapped:
            def _land_val(l):
                if l.card.tag == 'dual': return 3
                if l.card.is_basic: return 2
                return 1
            target = max(opp_untapped, key=_land_val)
            target.tapped = True
            port.tapped = True
            log_fn(f"Rishadan Port taps {target.card.name} (opponent loses 1 mana)")

    # ── 5. Combat — attack strategically ──
    # Thalia attacks only when DnT has 3+ creatures (board superiority).
    # SFM stays back if it hasn't activated equipment yet.
    # Recruiter (1/1) only attacks in alpha strikes.
    board_size = len([c for c in player.creatures if not c.summoning_sick])
    opp_blockers = len(opponent.creatures)
    total_power = sum(c.power for c in player.creatures if not c.summoning_sick)
    alpha_strike = total_power >= opponent.life or (board_size >= 3 and opp_blockers == 0)

    attackers = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'thalia' and board_size < 3 and not alpha_strike:
            continue  # keep Thalia back as tax piece when we need her
        if c.card.tag == 'sfm' and equip_card:
            continue  # keep SFM for activation
        if c.card.tag == 'recruiter' and not alpha_strike:
            continue  # 1/1 not worth risking
        if c.power > 0:
            attackers.append(c)
    combat_declare(player, opponent, gs, log_entries, attackers)



def _strategy_mono_black(player, opponent, gs, total_mana, log_fn, log_entries):
    """Mono Black Aggro: fast creatures + discard + Snuff Out."""
    # Thoughtseize T1
    ts = player.find_tag('ts')
    if ts and opp_can_cast(ts, total_mana, gs, caster=player) and gs.turn <= 2:
        player.cast_spell(ts, log_fn=log_fn)  # pays life_cost=2
        if opponent.hand:
            nonlands = [c for c in opponent.hand if not c.is_land()]
            target = next((c for c in nonlands if c.free_cast_if_blue), None)
            if not target and nonlands: target = max(nonlands, key=lambda c: c.cmc)
            if target:
                opponent.remove_from_hand(target); opponent.add_to_grave(target)
                log_fn(f"★ Thoughtseize strips {target.name}")
    # Hymn to Tourach T2
    hymn = player.find_tag('hymn')
    if hymn and opp_can_cast(hymn, total_mana, gs, caster=player) and gs.turn >= 2 and len(opponent.hand) >= 2:
        player.remove_from_hand(hymn); player.add_to_grave(hymn)
        if not _try_counter_any(player, opponent, gs, hymn, log_entries):
            import random
            discards = random.sample(list(opponent.hand), min(2, len(opponent.hand)))
            for c in discards:
                opponent.remove_from_hand(c); opponent.add_to_grave(c)
            log_fn(f"Hymn to Tourach — BUG discards {len(discards)} cards")
    # Grief evoke T1 (exile black card from hand)
    grief = player.find_tag('grief')
    blacks = [c for c in player.hand if 'B' in c.colors and c.tag != 'grief']
    if grief and blacks and gs.turn == 1:
        player.remove_from_hand(grief); player.remove_from_hand(blacks[0]); player.add_to_grave(blacks[0])
        if not _try_counter_any(player, opponent, gs, grief, log_entries):
            if opponent.hand:
                nonlands = [c for c in opponent.hand if not c.is_land()]
                target = (next((c for c in nonlands if c.free_cast_if_blue), None)
                          or (nonlands[0] if nonlands else None))
                if target:
                    opponent.remove_from_hand(target); opponent.add_to_grave(target)
                    log_fn(f"★ Grief (evoke) strips {target.name}")
    # Creatures
    # Mono Black creatures: find any creature opp can cast
    crea = next((c for c in player.hand
                 if c.is_creature() and opp_can_cast(c, total_mana, gs, caster=player)), None)
    if crea:
        player.remove_from_hand(crea)
        if not _try_counter_any(player, opponent, gs, crea, log_entries):
            player.put_creature_in_play(crea)
            log_fn(f"{crea.name} ({crea.base_power}/{crea.base_toughness})")
        else:
            player.add_to_grave(crea)

    # Wasteland — only when 4+ lands (need mana for Braids CMC4 / Grief CMC5)
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl and len(player.lands) >= 4:
        targets = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if targets:
            target = max(targets, key=lambda l: 3 if l.card.tag == 'dual' else 2 if l.is_fetch else 1)
            player.lands.remove(wl); player.add_to_grave(wl.card)
            player.revolt_this_turn = True
            opponent.lands.remove(target); opponent.add_to_grave(target.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland → destroys {target.card.name}")
            update_goyf(gs)

    # Combat
    attackers_this_turn = _select_attackers(player, opponent, hold_tags=('bowm',))
    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)



def _strategy_boros(player, opponent, gs, total_mana, log_fn, log_entries):
    """Boros Aggro/Initiative: fast white/red creatures, Vial, Thalia."""

    # Aether Vial — highest priority, cast T1-T3
    vial = player.find_tag('vial')
    vial_on_board_b = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial and not vial_on_board_b and total_mana >= 1 and gs.turn <= 3:
        player.remove_from_hand(vial)
        if not _try_counter_any(player, opponent, gs, vial, log_entries):
            player.put_artifact_in_play(vial)
            gs.vial_counters = 0
            gs._vial_entered_last_turn = True  # no tick until next upkeep (CR 702.12)
            log_fn("Aether Vial enters play")
        else:
            player.add_to_grave(vial)

    # Eidolon of the Great Revel — CMC2 creature; deploy early to tax BUG's spells
    eidolon = player.find_tag('eidolon')
    eidolon_on_board = any(c.card.tag == 'eidolon' for c in player.creatures)
    if eidolon and not eidolon_on_board and total_mana >= 2:
        player.remove_from_hand(eidolon)
        if not _try_counter_any(player, opponent, gs, eidolon, log_entries):
            player.put_creature_in_play(eidolon)
            gs.eidolon_active = True
            log_fn("★ Eidolon of the Great Revel — BUG pays 2 life per CMC≥2 spell", True)
        else:
            player.add_to_grave(eidolon)
    # Keep eidolon_active in sync with board state
    gs.eidolon_active = any(c.card.tag == 'eidolon' for c in player.creatures)

    # Vial upkeep tick — smart counter management, cap at 2 for Boros CMC distribution
    boros_tags = ('thalia', 'orchid', 'dungeoneer', 'adventurer', 'recruiter', 'minsc',
                  'eidolon', 'bowm')
    vial_perm_b = next((p for p in player.artifacts if p.card.tag == 'vial'), None)
    if vial_perm_b:
        if gs._vial_entered_last_turn:
            gs._vial_entered_last_turn = False
        elif gs.vial_counters < 2:
            gs.vial_counters += 1
            log_fn(f"Aether Vial — {gs.vial_counters} counter(s)")

    # Hard cast ALL affordable creatures — Boros wants maximum board pressure.
    # Deploy up to 3 per turn (aggro floods the board to overwhelm BUG's removal).
    cast_count = 0
    for tag in boros_tags:
        if cast_count >= 3 or total_mana < 1: break
        crea = player.find_tag(tag)
        if crea and opp_can_cast(crea, total_mana, gs, caster=player):
            player.remove_from_hand(crea)
            if not _try_counter_any(player, opponent, gs, crea, log_entries):
                player.put_creature_in_play(crea)
                total_mana -= crea.cmc
                log_fn(f"{crea.name}")
                cast_count += 1
            else:
                player.add_to_grave(crea)

    # STP removal — exile BUG threats aggressively, grant life (CR 106)
    for _ in range(4):
        stp = player.find_tag('stp')
        if not (stp and opponent.creatures and opp_can_cast(stp, total_mana, gs, caster=player)):
            break
        # STP costs 1W; mana after casting = total_mana - 1 (for ward check)
        mana_after_stp = total_mana - 1
        valid_stp = [c for c in opponent.creatures if _can_target(c, mana_after_stp)]
        target = max(valid_stp, key=lambda c: c.power) if valid_stp else None
        if not target or target.power < 1: break
        player.remove_from_hand(stp); player.add_to_grave(stp)
        total_mana -= 1
        life_gain = MTGRules.stp_life_gain(target)
        opponent.remove_creature(target, to_exile=True)
        opponent.life += life_gain
        log_fn(f"Swords to Plowshares exiles {target.card.name} (+{life_gain} life)")
        update_goyf(gs)

    # Chalice of the Void — Boros sometimes runs it to shut off BUG's CMC1 package
    ch = player.find_tag('chalice')
    if ch and gs.chalice_x is None and total_mana >= 1:
        player.remove_from_hand(ch)
        if not _try_counter_any(player, opponent, gs, ch, log_entries):
            player.put_artifact_in_play(ch)
            gs.chalice_x = 1
            log_fn("★ Chalice on 1 — counters Brainstorm/Ponder/Push/Tamiyo/Daze", True)
        else:
            player.add_to_grave(ch)

    # Lightning Bolt — aggressive burn plan: face when near-lethal, otherwise kill blocker
    # Fire all available bolts when BUG life ≤ 9 (burn them out)
    bolts = [c for c in player.hand if c.is_removal and c.cmc == 1 and not c.is_creature()]
    for bolt in bolts:
        if not opp_can_cast(bolt, total_mana, gs, caster=player):
            break
        total_mana -= 1  # cost 1R each
        player.remove_from_hand(bolt); player.add_to_grave(bolt)
        # Burn face if: BUG life ≤ 12 (3-bolt kill range), or no threatening blocker
        go_face = opponent.life <= 12 or not any(c.toughness <= 3 for c in opponent.creatures)
        # Bolt costs 1R; after paying, mana remaining = total_mana (already decremented above)
        small = next((c for c in sorted(opponent.creatures, key=lambda x: x.toughness)
                      if c.toughness <= 3 and _can_target(c, total_mana)), None)
        if go_face or not small:
            opponent.life -= 3
            log_fn(f"Lightning Bolt — BUG face ({opponent.life})", True)
            gs.check_life_totals()
            if gs.game_over: break
        else:
            opponent.remove_creature(small)
            log_fn(f"Lightning Bolt → {small.name}")
            update_goyf(gs)

    # Hold Eidolon back only if BUG has blockers that would kill it (2/2)
    eidolon_safe = not any(c.power >= 2 for c in opponent.creatures)
    hold = ('bowm',) if eidolon_safe else ('bowm', 'eidolon')
    attackers_this_turn = _select_attackers(player, opponent, hold_tags=hold)
    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)

    # Initiative — Seasoned Dungeoneer takes Initiative on ETB/attack.
    # Each turn with Initiative: venture into Undercity dungeon room.
    # Simplified: deal escalating damage (1 first trigger, then 2 per subsequent).
    has_initiative = any(c.card.tag == 'dungeoneer' for c in player.creatures)
    if has_initiative:
        init_count = getattr(gs, '_initiative_count', 0) + 1
        gs._initiative_count = init_count
        init_damage = min(init_count, 3)  # cap at 3 per turn (Undercity rooms)
        opponent.life -= init_damage
        log_fn(f"Initiative (Undercity room {init_count}) — {init_damage} damage to BUG ({opponent.life})", True)
        gs.check_life_totals()

    # Wasteland — destroy BUG's nonbasic lands (Underground Sea)
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        targets = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if targets:
            target = max(targets, key=lambda l: 3 if l.card.tag == 'dual' else 2 if l.is_fetch else 1)
            player.lands.remove(wl); player.add_to_grave(wl.card)
            player.revolt_this_turn = True
            opponent.lands.remove(target); opponent.add_to_grave(target.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland → destroys {target.card.name}")
            update_goyf(gs)

    # Karakas — bounce BUG's legendary creatures
    legendary_targets = ('murk', 'tamiyo', 'wst')
    for karakas in [l for l in player.lands if l.card.tag == 'karakas' and not l.tapped]:
        bug_legend = next((c for c in sorted(opponent.creatures,
                           key=lambda x: x.card.cmc, reverse=True)
                           if c.card.tag in legendary_targets), None)
        if bug_legend:
            karakas.tapped = True
            opponent.creatures.remove(bug_legend)
            opponent.hand.append(bug_legend.card)
            opponent.revolt_this_turn = True
            log_fn(f"★ Karakas → returns {bug_legend.card.name} to BUG's hand", True)
            update_goyf(gs)
            break  # one Karakas activation per gs.turn is typical



def _resolve_lock(gs, card, log_fn):
    """Apply the game state effect of a resolved lock piece."""
    if card.tag == 'chalice':
        gs.chalice_x = 1
        log_fn("★ Chalice on 1 — counters all CMC 1 spells", True)
    elif card.tag == 'bridge':
        gs.bridge_on_board = True
        log_fn("★ Ensnaring Bridge — creatures with power > hand size can't attack", True)
    elif card.tag == 'moon':
        gs.set_moon(True)
        log_fn("★ Blood Moon — nonbasic lands become Mountains", True)
    elif card.tag == 'b2b':
        gs.set_b2b(True)
        log_fn("★ Back to Basics — nonbasic lands don't untap", True)
    elif card.tag == 'trini':
        gs.trinisphere_active = True
        log_fn("★ Trinisphere — all spells cost at least {3}", True)


def _strategy_prison(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Artifacts Prison strategy. Priority order:
    1. Chalice on 1 T1 (Ancient Tomb → shuts off Brainstorm/Ponder/Daze)
    2. Trinisphere — locks all cheap spells to 3 mana
    3. Painter's Servant + Grindstone combo (instant mill kill)
    4. Karn (tutors any artifact lock/combo piece from sideboard)
    5. Ensnaring Bridge (stops attacks once hand is depleted)
    6. TKS (strips best card, 4/4 body)
    7. Null Rod (shuts off fetch lands)
    """

    # ── 0. Fast mana: Lotus Petal and Grim Monolith ──
    petal = player.find_tag('petal')
    if petal and petal.cmc <= total_mana:
        player.remove_from_hand(petal); player.add_to_grave(petal)
        total_mana += 1
        log_fn("Lotus Petal → +1 mana")
    mono = player.find_tag('monolith')
    if mono and total_mana >= 2:
        player.remove_from_hand(mono); player.put_artifact_in_play(mono)
        total_mana += 1  # Grim Monolith: costs 2, taps for 3 (net +1 same turn)
        log_fn("Grim Monolith → +3 mana")

    # ── 1. Chalice of the Void on 1 — T1 priority with Ancient Tomb ──
    ch = player.find_tag('chalice')
    if ch and gs.chalice_x is None and total_mana >= 2:
        player.remove_from_hand(ch)
        if not _try_counter_any(player, opponent, gs, ch, log_entries):
            player.put_artifact_in_play(ch)
            total_mana -= 2
            _resolve_lock(gs, ch, log_fn)
        else:
            player.add_to_grave(ch)

    # ── 2. Trinisphere — second lock piece ──
    tri = player.find_tag('trini')
    if tri and not gs.trinisphere_active and total_mana >= 3:
        player.remove_from_hand(tri)
        if not _try_counter_any(player, opponent, gs, tri, log_entries):
            player.put_artifact_in_play(tri)
            total_mana -= 3
            gs.trinisphere_active = True
            log_fn("Trinisphere — all spells cost minimum 3", True)
        else:
            player.add_to_grave(tri)

    # (FoV is handled by _p1_respond_on_opp_turn, not here — removed
    #  self-destructive call that destroyed Prison's own lock pieces as P2)

    # ── 3. Painter's Servant + Grindstone combo — instant mill kill ──
    painter_in_play = any(p.card.tag == 'painter' for p in player.artifacts + player.creatures)
    grind_in_play = any(p.card.tag == 'grind' for p in player.artifacts)

    # If both pieces in play → win
    if painter_in_play and grind_in_play:
        # Grindstone activation: tap + 3 mana to mill. With Painter naming a color,
        # the two cards always share a color → repeat until library is empty.
        if total_mana >= 3:
            log_fn("★ Painter + Grindstone — mills entire library!", True)
            gs.game_over = True
            gs.kill_turn = gs.turn
            gs.winner = 'p1' if player is gs.p1 else 'p2'
            gs.win_reason = "Painter + Grindstone combo"
            return

    # Deploy Painter's Servant (CMC 2)
    painter = player.find_tag('painter')
    if painter and not painter_in_play and total_mana >= 2:
        player.remove_from_hand(painter)
        if not _try_counter_any(player, opponent, gs, painter, log_entries):
            player.put_artifact_in_play(painter)
            total_mana -= 2
            log_fn("Painter's Servant (naming blue)", True)
        else:
            player.add_to_grave(painter)

    # Deploy Grindstone (CMC 1)
    grind = player.find_tag('grind')
    if grind and not grind_in_play and total_mana >= 1:
        player.remove_from_hand(grind)
        if not _try_counter_any(player, opponent, gs, grind, log_entries):
            player.put_artifact_in_play(grind)
            total_mana -= 1
            log_fn("Grindstone", True)
        else:
            player.add_to_grave(grind)

    # Check combo again after deploying pieces
    painter_in_play = any(p.card.tag == 'painter' for p in player.artifacts + player.creatures)
    grind_in_play = any(p.card.tag == 'grind' for p in player.artifacts)
    if painter_in_play and grind_in_play and total_mana >= 3:
        log_fn("★ Painter + Grindstone — mills entire library!", True)
        gs.game_over = True
        gs.kill_turn = gs.turn
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = "Painter + Grindstone combo"
        return

    # ── 4. Karn, the Great Creator — recurring +1 each turn ──
    karn_on_board = any(p.card.tag == 'karn' for p in player.artifacts)
    def _karn_wish():
        """Karn +1: wish for the most impactful missing piece."""
        # Priority: combo piece > lock piece
        if not grind_in_play and painter_in_play:
            log_fn("  Karn +1: wishes for Grindstone", True)
            # Create a grindstone in play
            from rules import Card
            gs_card = artifact('Grindstone', 1, {'generic':1}, tag='grind', win_condition=True)
            player.put_artifact_in_play(gs_card)
        elif not painter_in_play and grind_in_play:
            log_fn("  Karn +1: wishes for Painter's Servant", True)
            ps_card = artifact("Painter's Servant", 2, {'generic':2}, tag='painter', is_combo_piece=True)
            player.put_artifact_in_play(ps_card)
        elif not gs.bridge_on_board and opponent.creatures:
            log_fn("  Karn +1: wishes for Ensnaring Bridge", True)
            gs.bridge_on_board = True
        elif not gs.trinisphere_active:
            log_fn("  Karn +1: wishes for Trinisphere", True)
            gs.trinisphere_active = True
        elif gs.chalice_x is None:
            log_fn("  Karn +1: wishes for Chalice (on 1)", True)
            gs.chalice_x = 1

    # Karn already on board — tick +1 and wish each turn
    if karn_on_board:
        _karn_wish()

    # Deploy Karn from hand if not yet on board
    karn = player.find_tag('karn')
    if karn and total_mana >= 4 and not karn_on_board:
        player.remove_from_hand(karn)
        if not _try_counter_any(player, opponent, gs, karn, log_entries):
            player.put_artifact_in_play(karn)
            total_mana -= 4
            log_fn("Karn, the Great Creator (static: opp artifacts lose abilities)", True)
            _karn_wish()
        else:
            player.add_to_grave(karn)

    # ── 5. Ensnaring Bridge ──
    br = player.find_tag('bridge')
    if br and not gs.bridge_on_board and total_mana >= 3:
        player.remove_from_hand(br)
        ad = opponent.find_tag('ad')
        if ad and opponent.available_mana_count() >= ad.cmc:
            opponent.remove_from_hand(ad); opponent.add_to_grave(ad)
            log_fn("Abrupt Decay destroys Bridge in response", True)
        elif not _try_counter_any(player, opponent, gs, br, log_entries):
            player.put_artifact_in_play(br)
            _resolve_lock(gs, br, log_fn)
        else:
            player.add_to_grave(br)

    # ── 6. TKS ──
    tks = player.find_tag('tks')
    if tks and total_mana >= 4:
        player.remove_from_hand(tks)
        if not _try_counter_any(player, opponent, gs, tks, log_entries):
            player.put_creature_in_play(tks)
            if opponent.hand:
                nonlands = [c for c in opponent.hand if not c.is_land()]
                if nonlands:
                    ex = random.choice(nonlands); opponent.hand.remove(ex); opponent.exile.append(ex)
                    log_fn(f"TKS exiles {ex.name}", True)
        else:
            player.add_to_grave(tks)

    # ── 7. Null Rod (if no Karn already providing similar effect) ──
    nr = player.find_tag('nullrod')
    if nr and total_mana >= 2 and not any(p.card.tag == 'karn' for p in player.artifacts):
        player.remove_from_hand(nr)
        if not _try_counter_any(player, opponent, gs, nr, log_entries):
            player.put_artifact_in_play(nr)
            log_fn("Null Rod — activated abilities of artifacts don't work", True)
        else:
            player.add_to_grave(nr)

    # Bridge hand-dump: reduce hand to 0-1 to block most creatures.
    if gs.bridge_on_board and len(player.hand) > 1:
        useful_tags = {'chalice', 'trini', 'bridge', 'karn', 'tks', 'nullrod', 'painter', 'grind'}
        while len(player.hand) > 1:
            non_useful = next((c for c in player.hand if c.tag not in useful_tags), None)
            if non_useful:
                player.hand.remove(non_useful)
                player.add_to_grave(non_useful)
            else:
                break
        log_fn(f"Hand dump for Bridge — hand now {len(player.hand)}")

    # Combat — Prison attacks with TKS and creatures if available
    attackers_this_turn = _select_attackers(player, opponent, hold_tags=())
    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)



def _strategy_eldrazi(player, opponent, gs, total_mana, log_fn, log_entries):

    # FoV reactive: destroy opp's Chalice if BUG has Force of Vigor
    if gs.chalice_x is not None:
        _p1_force_of_vigor(gs, ['chalice'], log_entries)

    # ── Chalice of the Void ──
    # Oracle: costs {X}{X} = generic/colorless mana only
    # VALID sources: Ancient Tomb (2C), City of Traitors (2C), Lotus Petal (any)
    # INVALID: Eldrazi Temple {CC} is restricted to Eldrazi spells, not Chalice
    ch = player.find_tag('chalice')
    if ch and gs.chalice_x is None:
        tomb_ok  = any(l.card.tag == 'tomb' and not l.tapped for l in player.lands)
        city_ok  = any(l.card.tag == 'city' and not l.tapped for l in player.lands)
        petals   = [c for c in player.hand if c.tag == 'petal']
        has_2c_generic = tomb_ok or city_ok or len(petals) >= 2

        if has_2c_generic or total_mana >= 2:
            player.remove_from_hand(ch)
            # Spend Lotus Petals if no other 2-mana generic source
            if not tomb_ok and not city_ok and len(petals) >= 2:
                for p in petals[:2]: player.remove_from_hand(p); player.add_to_grave(p)
            if not _try_counter_any(player, opponent, gs, ch, log_entries):
                player.put_artifact_in_play(ch); gs.chalice_x = 1
                log_fn("Chalice on 1", True)
            else: player.add_to_grave(ch)
    if ch and gs.chalice_x is None:
        player.remove_from_hand(ch)
        if not _try_counter_any(player, opponent, gs, ch, log_entries):
            player.put_artifact_in_play(ch); gs.chalice_x = 1
            log_fn("Chalice on 1", True)
        else: player.add_to_grave(ch)
    # ── Threats ──
    # ── Threats — deploy all affordable creatures each turn (biggest first) ──
    # TKS first (hand disruption is high-value)
    tks = player.find_tag('tks')
    if tks and opp_can_cast(tks, total_mana, gs, caster=player):
        player.remove_from_hand(tks)
        if not _try_counter_any(player, opponent, gs, tks, log_entries):
            player.put_creature_in_play(tks)
            total_mana -= tks.cmc
            if opponent.hand:
                nonlands = [c for c in opponent.hand if not c.is_land()]
                if nonlands:
                    ex = random.choice(nonlands); opponent.hand.remove(ex); opponent.exile.append(ex)
                    log_fn(f"TKS exiles {ex.name}", True)
        else: player.add_to_grave(tks)

    # Deploy remaining creatures, biggest-first
    while True:
        affordable = [c for c in player.hand
                      if c.is_creature() and opp_can_cast(c, total_mana, gs, caster=player)]
        if not affordable:
            break
        thr = max(affordable, key=lambda c: c.cmc)
        player.remove_from_hand(thr)
        if not _try_counter_any(player, opponent, gs, thr, log_entries):
            player.put_creature_in_play(thr)
            log_fn(f"{thr.name} ({thr.base_power}/{thr.base_toughness})")
        else:
            player.add_to_grave(thr)
        total_mana -= thr.cmc

    # Wasteland — only when 3+ lands (Eldrazi needs mana for CMC 3-4 threats)
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl and len(player.lands) >= 3:
        targets = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if targets:
            target = max(targets, key=lambda l: 3 if l.card.tag == 'dual' else 2 if l.is_fetch else 1)
            player.lands.remove(wl); player.add_to_grave(wl.card)
            player.revolt_this_turn = True
            opponent.lands.remove(target); opponent.add_to_grave(target.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland → destroys {target.card.name}")
            update_goyf(gs)

    # Combat — Eldrazi attacks aggressively
    attackers_this_turn = _select_attackers(player, opponent, hold_tags=())
    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)



def _strategy_show(player, opponent, gs, total_mana, log_fn, log_entries):

    # ── Mana: Ancient Tomb gives {CC} generic; City of Traitors gives {CC} ──
    # Lotus Petal sacs for any mana
    tomb_untapped = sum(1 for l in player.lands if l.card.tag == 'tomb' and not l.tapped)
    city_untapped = sum(1 for l in player.lands if l.card.tag == 'city' and not l.tapped)
    petals        = [c for c in player.hand if c.tag == 'petal']
    # (Ancient Tomb life loss already deducted in protagonist_turn/opp_turn
    #  — removed redundant deduction that was double-charging Show 4 life/Tomb)
    # Effective mana: each untapped Tomb/City adds +1 (base already counts 1 from land)
    om_eff = total_mana + tomb_untapped + city_untapped + len(petals)

    # ── Cantrips ──
    can = next((c for c in player.hand if c.is_cantrip and om_eff>=1), None)
    if can:
        player.remove_from_hand(can); player.add_to_grave(can)
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)

    # ── Show and Tell (costs 3 generic: UU1) ──
    sat = player.find_tag('sat')
    win_card = (player.find_tag('emrakul') or player.find_tag('omni') or
                player.find_tag('sneak')   or player.find_tag('gris'))
    if sat and win_card and om_eff >= 3:
        # Spend Lotus Petals if needed
        mana_needed = max(0, 3 - total_mana)
        for p in petals[:mana_needed]:
            player.remove_from_hand(p); player.add_to_grave(p)

        vos = player.find_tag('vos')
        if vos and can_afford(player, vos.mana_cost):
            # Cast Veil first — but opponent gets a counter window
            if not _try_counter_any(player, opponent, gs, vos, log_entries):
                player.remove_from_hand(vos); player.add_to_grave(vos); gs.veil_active = True
                log_fn("Veil of Summer — BUG blue/black counters blanked this gs.turn")
            else:
                player.remove_from_hand(vos); player.add_to_grave(vos)
                log_fn("Veil of Summer countered")
            player.remove_from_hand(sat); player.add_to_grave(sat)
            player.remove_from_hand(win_card)
            # BUG gets to put its best permanent in play too
            bug_put = opponent.find_any(lambda c: c.is_creature() and not c.is_land())
            if bug_put:
                opponent.remove_from_hand(bug_put); opponent.put_creature_in_play(bug_put)
                log_fn(f"  BUG puts {bug_put.name} in play")
            log_fn(f"★ {win_card.name} enters through Veil (haste)" if getattr(win_card,'haste',False) else f"★ {win_card.name} enters through Veil", True)
            if win_card.is_creature():
                player.put_creature_in_play(win_card)
            gs.game_over = True; gs.winner = ('p1' if player is gs.p1 else 'p2')
            gs.kill_turn = gs.turn
            gs.win_reason = f"Show+Veil: {win_card.name}"
        else:
            player.remove_from_hand(sat)
            if not _try_counter_any(player, opponent, gs, sat, log_entries):
                player.add_to_grave(sat)
                player.remove_from_hand(win_card)
                bug_put = opponent.find_any(lambda c: c.is_creature() and not c.is_land())
                if bug_put:
                    opponent.remove_from_hand(bug_put); opponent.put_creature_in_play(bug_put)
                    log_fn(f"  BUG puts {bug_put.name} in play")
                log_fn(f"★ Show+Tell resolves: {win_card.name} enters play", True)
                # Emrakul/Omniscience wins via combat — put creature in play and let combat happen
                if win_card.is_creature():
                    player.put_creature_in_play(win_card)
                    # Emrakul has haste — attack immediately for lethal
                    if win_card.tag in ('emrakul', 'gris', 'archon') and getattr(win_card, 'haste', False):
                        # Emrakul annihilator 6 + extra turn / Griselbrand draw-7 → treat as instant win
                        # Annihilator strips opponent's board, 15 damage lethal from any real life total
                        opponent.life -= win_card.base_power
                        player.life   += getattr(win_card, 'lifelink', False) and win_card.base_power or 0
                        log_fn(f"★ {win_card.name} attacks — {win_card.base_power} damage, opp at {opponent.life}", True)
                        # Win if lethal, or if Emrakul (annihilator 6 strips 30+ points of permanents)
                        if opponent.life <= 0 or win_card.tag == 'emrakul':
                            gs.game_over = True; gs.winner = ('p1' if player is gs.p1 else 'p2')
                            gs.kill_turn = gs.turn
                            gs.win_reason = f"Show+Tell: {win_card.name} (annihilator+attack)"
                    else:
                        # No haste — mark for next turn
                        gs.show_creature_in_play = win_card.name
                        log_fn(f"  {win_card.name} in play — attacks next turn for lethal")
                else:
                    # Omniscience — permanent enchantment, ALL spells free from now on
                    gs.omniscience_active = True
                    log_fn(f"★ Omniscience enters play — all spells cost {0} permanently", True)
                    # Immediately cast Emrakul/Griselbrand from hand for free
                    chain_target = (player.find_tag('emrakul') or player.find_tag('gris') or
                                    player.find_tag('archon'))
                    if chain_target:
                        player.remove_from_hand(chain_target)
                        player.put_creature_in_play(chain_target)
                        log_fn(f"★ Omniscience → casts {chain_target.name} for free", True)
                        if getattr(chain_target, 'haste', False):
                            opponent.life -= chain_target.base_power
                            player.life   += getattr(chain_target,'lifelink',False) and chain_target.base_power or 0
                            log_fn(f"★ {chain_target.name} attacks for {chain_target.base_power}", True)
                            if opponent.life <= 0 or chain_target.tag == 'emrakul':
                                gs.game_over = True
                                gs.kill_turn = gs.turn
                                gs.winner = 'p1' if player is gs.p1 else 'p2'
                                gs.win_reason = f"Omniscience+{chain_target.name}"
                        else:
                            gs.show_creature_in_play = chain_target.name
            else:
                player.add_to_grave(sat)

    # ── Sneak Attack activation (if Sneak on board and has Emrakul in hand) ──
    sneak_perm = next((p for p in player.artifacts if p.card.tag == 'sneak'), None)
    if sneak_perm and not gs.game_over:
        emy = player.find_tag('emrakul') or player.find_tag('gris')
        if emy and om_eff >= 4:  # Sneak costs {R} + creature CMC colourless
            player.remove_from_hand(emy)
            log_fn(f"★ Sneak Attack → {emy.name} attacks for lethal — game over", True)
            gs.game_over = True; gs.winner = ('p1' if player is gs.p1 else 'p2')
            gs.kill_turn = gs.turn
            gs.win_reason = f"Sneak Attack: {emy.name}"

    # ── Put Sneak Attack into play if SaT already resolved ──
    sneak_card = player.find_tag('sneak')
    if sneak_card and om_eff >= 4 and not gs.game_over:
        sat2 = player.find_tag('sat')
        if sat2 and win_card:
            pass  # Will handle via Show next gs.turn
        elif not sneak_perm:
            player.remove_from_hand(sneak_card)
            if not _try_counter_any(player, opponent, gs, sneak_card, log_entries):
                player.put_artifact_in_play(sneak_card)
                log_fn("Sneak Attack enters play")
            else:
                player.add_to_grave(sneak_card)



def _strategy_lands(player, opponent, gs, total_mana, log_fn, log_entries):
    crop = player.find_tag('crop')
    if crop and opp_can_cast(crop, total_mana, gs, caster=player):
        player.remove_from_hand(crop)
        if not _try_counter_any(player, opponent, gs, crop, log_entries):
            player.add_to_grave(crop)
            want = 'depths' if not any(l.card.tag == 'depths' for l in player.lands) else 'stage'
            found = next((c for c in player.library if c.tag == want), None)
            if found:
                player.library.remove(found)
                player.lands.append(LandPermanent(card=found, controller=('b' if player is gs.p1 else 'o')))
                log_fn(f"Crop Rotation → {found.name}")
        else: player.add_to_grave(crop)
    has_depths = any(l.card.tag == 'depths' for l in player.lands)
    has_stage  = any(l.card.tag == 'stage' for l in player.lands)
    if has_depths and has_stage and not gs.game_over:
        from rules import Card as RCard
        trigger = StackObject(name="Marit Lage token",
                              stack_type=MTGRules.marit_lage_stack_type(), controller=('b' if player is gs.p1 else 'o'),
                              trigger_source='Dark Depths')
        log_fn(f"Dark Depths combo → triggered ability (StackType: {trigger.stack_type.name})", True)
        log_fn("★ RULES: Triggered ability — FoW/Daze/Counterspell CANNOT counter CR 113.9", True)
        ml_card = RCard(name='Marit Lage', card_type=CardType.CREATURE, cmc=0, mana_cost={},
                        colors={'B'}, base_power=20, base_toughness=20,
                        flying=True, indestructible=True, tag='marit', gy_type='creature')
        ml = Permanent(card=ml_card, controller=('b' if player is gs.p1 else 'o'), summoning_sick=True)
        player.creatures.append(ml)
        player.lands = [l for l in player.lands if l.card.tag not in ('depths','stage')]
        borrow = opponent.find_tag('borrow')
        if borrow and opponent.available_mana_count() >= borrow.cmc:
            # (mana spent reactively)
            opponent.remove_from_hand(borrow); opponent.add_to_grave(borrow)
            player.remove_creature(ml)
            log_fn("★ Brazen Borrower bounces Marit Lage (valid target — now a permanent)", True)
        else:
            log_fn("No Borrower — Marit Lage 20/20 flying indestructible in play", True)
    if any(l.card.tag == 'tab' for l in player.lands) and opponent.creatures:
        cost = len(opponent.creatures)
        if opponent.available_mana_count() < cost:
            sac = opponent.creatures[:cost - opponent.available_mana_count()]
            for s in sac:
                opponent.remove_creature(s)  # revolt + GY via remove_creature
            log_fn(f"Tabernacle — BUG sacrifices {[s.name for s in sac]}", True)
    # Snuff Out — free (pay 4 life) if controlling a Swamp; destroy nonblack creature
    snuff = player.find_tag('snuffout')
    # Snuff Out: 'if you control a Swamp' = any land with Swamp subtype (incl. duals)
    has_swamp = any('Swamp' in l.card.subtypes or (l.card.is_basic and 'B' in l.effective_produces()) for l in player.lands)
    if snuff and has_swamp and opponent.creatures:
        # Snuff Out is free (pay life); all total_mana available for ward
        target = next((c for c in sorted(opponent.creatures, key=lambda x: -x.power)
                       if 'B' not in c.card.colors and _can_target(c, total_mana)), None)
        if target:
            player.cast_spell(snuff)  # pays life_cost=4
            opponent.remove_creature(target)
            log_fn(f"Snuff Out (free, −4 life → {player.life}) → kills {target.name} (nonblack)", True)
            update_goyf(gs)

    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        # Target priority: cut the colour BUG needs most for their hand
        bug_spell_colours = set(col for card in opponent.hand if not card.is_land()
                                for col in card.colors)
        def _wl_pri(land):
            score = 0
            p = land.effective_produces()
            if p & bug_spell_colours: score += 10  # cuts colour BUG needs now
            if land.card.tag in ('dual',): score += 3  # duals are hardest to replace
            if land.is_fetch: score += 2
            return score
        eligible = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        wt = max(eligible, key=_wl_pri, default=None)
        if wt:
            player.lands.remove(wl); player.add_to_grave(wl.card)
            opponent.lands.remove(wt); opponent.add_to_grave(wt.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland [ACTIVATED-uncounterable] → {wt.name}")
            update_goyf(gs)
    # UWx selective combat: only attack with creatures that can deal unblocked damage
    # or that trade favourably. Hold Riddler back until it's larger than BUG blockers.
    bug_max_blocker_toughness = max((c.toughness for c in opponent.creatures), default=0)
    bug_max_blocker_power     = max((c.power     for c in opponent.creatures), default=0)

    # Combat: decide which Mardu creatures attack
    # Bowmasters: VALUE engine — pings opponent every draw step.
    # Never trade it in combat unless the board is desperate.
    # Only attack with Bowmasters if opponent has no blockers (unblocked damage)
    # or if Mardu is so far behind it must race.
    opp_has_blockers = len(opponent.creatures) > 0
    mardu_desperate  = player.life < CT.DESPERATE_LIFE   # racing, need every point
    attackers_this_turn = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'bowm':
            # Hold Bowmasters back unless unblocked or desperate
            if not opp_has_blockers or mardu_desperate:
                attackers_this_turn.append(c)
            # else: keep pinging, don't trade in combat
        elif c.card.tag == 'tamiyo':
            pass   # 0/3 blocks, doesn't attack
        else:
            attackers_this_turn.append(c)

    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)



def _strategy_oops(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Oops All Spells: 0-land combo deck.
    Win: cast Balustrade Spy (4 mana) or Undercity Informer (3+1), mill entire
    deck (no lands to stop), Narcomoebas enter, flashback Dread Return on
    Thassa's Oracle for the win.

    Mana sources: Lotus Petal (0), Chrome Mox (0), Elvish/Simian Spirit Guide
    (exile from hand for 1 mana), Dark Ritual (+2 net), Cabal Ritual (+2 net),
    MDFC "lands" (Agadeem's Awakening / Turntimber Symbiosis played as tapped lands).
    """
    # ── 0. Play MDFC as land if no lands in play ──
    if not player.lands:
        mdfc = next((c for c in player.hand if getattr(c, 'is_mdfc_land', False)), None)
        if mdfc:
            player.remove_from_hand(mdfc)
            # MDFC back face enters tapped, produces B (Agadeem) or G (Turntimber)
            color = 'B' if mdfc.tag == 'agadeem' else 'G'
            # Temporarily set produces on the card so LandPermanent can use it
            mdfc.produces = {color}
            from rules import LandPermanent
            lp = LandPermanent(card=mdfc, controller='b' if player is gs.p1 else 'o',
                               tapped=True)
            player.lands.append(lp)
            log_fn(f"{mdfc.name} → enters tapped as land ({color})")

    # ── 1. Free mana: crack Petals, exile Spirit Guides ──
    for _ in range(10):  # loop for multiple petals/guides
        petal = player.find_tag('petal') or player.find_tag('cmox')
        if petal:
            player.remove_from_hand(petal); player.add_to_grave(petal)
            total_mana += 1
            log_fn(f"{petal.name} → +1 mana")
            continue
        esg = player.find_tag('esg') or player.find_tag('ssg')
        if esg:
            player.remove_from_hand(esg); player.exile.append(esg)
            total_mana += 1
            log_fn(f"Exile {esg.name} → +1 mana")
            continue
        break

    # ── 2. Rituals ──
    for _ in range(10):
        rit = next((c for c in player.hand if c.tag in ('darkrit', 'cabalrit')
                     and c.cmc <= total_mana), None)
        if rit:
            player.remove_from_hand(rit); player.add_to_grave(rit)
            total_mana -= rit.cmc
            total_mana += 3  # Dark Ritual/Cabal Ritual produce BBB/BBBBB
            log_fn(f"{rit.name} → mana now {total_mana}")
        else:
            break

    # ── 2b. Summoner's Pact: free tutor for green creature (Spy) ──
    # Pact costs 0 now, pay {2}{G}{G} next upkeep (or lose the game).
    # In Oops, you win before next upkeep, so it's always free.
    spact = player.find_tag('spact')
    if spact and not player.find_tag('spy'):
        # Tutor Balustrade Spy from library
        spy_from_lib = next((c for c in player.library if c.tag == 'spy'), None)
        if spy_from_lib:
            player.remove_from_hand(spact); player.exile.append(spact)
            player.library.remove(spy_from_lib)
            player.hand.append(spy_from_lib)
            log_fn(f"Summoner's Pact → tutors Balustrade Spy (free)", True)

    # ── 3. Grief (free evoke: exile black card from hand) ──
    # Don't pitch combo pieces (Spy, Informer, Oracle) or rituals
    grief = player.find_tag('grief')
    _grief_protected = {'spy', 'informer', 'oracle', 'dread', 'darkrit', 'cabalrit'}
    if grief and sum(1 for c in player.hand if 'B' in getattr(c, 'colors', set()) and c is not grief and c.tag not in _grief_protected) >= 1:
        pitch = next(c for c in player.hand if 'B' in getattr(c, 'colors', set()) and c is not grief and c.tag not in _grief_protected)
        player.remove_from_hand(grief); player.add_to_grave(grief)
        player.remove_from_hand(pitch); player.exile.append(pitch)
        if opponent.hand:
            nonlands = [c for c in opponent.hand if not c.is_land()]
            if nonlands:
                best = next((c for c in nonlands if c.tag in ('fow', 'fon', 'fluster', 'endurance')),
                            nonlands[0])
                opponent.hand.remove(best); opponent.add_to_grave(best)
                log_fn(f"Grief (evoke, pitch {pitch.name}) — strips {best.name}", True)

    # ── 4. Combo: Balustrade Spy (4) or Undercity Informer (3+1) ──
    # Leyline of the Void exiles all cards that would go to GY — combo fizzles
    if gs.leyline_active:
        return

    spy = player.find_tag('spy')
    informer = player.find_tag('informer')
    combo_card = None
    combo_cost = 0
    if spy and total_mana >= 4:
        combo_card = spy; combo_cost = 4
    elif informer and total_mana >= 4:  # 3 to cast + 1 to activate
        combo_card = informer; combo_cost = 4

    gs.strat_log.log_decision(
        gs.turn, 'oops',
        candidates=['cast_spy', 'cast_informer', 'pass'],
        chosen=('cast_' + combo_card.tag) if combo_card else 'pass',
        reason=(f"mana={total_mana}, spy={spy is not None}, "
                f"informer={informer is not None}, leyline={gs.leyline_active}"))

    if combo_card:
        # Try Veil protection first
        vos = player.find_tag('vos')
        if vos and total_mana >= combo_cost + 1:
            if not _try_counter_any(player, opponent, gs, vos, log_entries):
                player.remove_from_hand(vos); player.add_to_grave(vos)
                gs.veil_active = True
                total_mana -= 1
                log_fn("Veil of Summer — blue interaction blanked")
            else:
                player.remove_from_hand(vos); player.add_to_grave(vos)
                total_mana -= 1
                log_fn("Veil of Summer countered")

        # Mindbreak Trap check
        mindbreak_o = opponent.find_tag('mindbreak')
        spells_this_turn = getattr(player, 'spells_cast_this_turn', 0)
        if mindbreak_o and spells_this_turn >= 3:
            opponent.remove_from_hand(mindbreak_o); opponent.add_to_grave(mindbreak_o)
            player.add_to_grave(combo_card)
            log_fn(f"★ Mindbreak Trap — {combo_card.name} exiled, combo fizzles", True)
            return

        player.remove_from_hand(combo_card)
        if not _try_counter_any(player, opponent, gs, combo_card, log_entries):
            player.add_to_grave(combo_card)
            # Mill entire library (no lands to stop it)
            milled = list(player.library)
            player.graveyard.extend(milled)
            player.library.clear()
            log_fn(f"★ {combo_card.name} → mill entire deck ({len(milled)} cards)", True)

            # Narcomoebas enter battlefield from graveyard (triggered ability)
            narcos = [c for c in player.graveyard if c.tag == 'narco']
            for n in narcos:
                player.graveyard.remove(n)
                player.put_creature_in_play(n)
            log_fn(f"  {len(narcos)} Narcomoeba(s) enter from graveyard", True)

            # Flashback Dread Return: sac 3 creatures, reanimate Oracle
            oracle_in_gy = next((c for c in player.graveyard if c.tag == 'oracle'), None)
            dread_in_gy = next((c for c in player.graveyard if c.tag == 'dread'), None)
            if dread_in_gy and oracle_in_gy and len(player.creatures) >= 3:
                for _ in range(3):
                    if player.creatures:
                        sac = player.creatures.pop()
                        player.add_to_grave(sac.card)
                player.graveyard.remove(dread_in_gy)
                player.exile.append(dread_in_gy)
                log_fn("  Flashback Dread Return (sac 3) → Thassa's Oracle", True)

                if not _try_counter_any(player, opponent, gs, dread_in_gy, log_entries):
                    player.graveyard.remove(oracle_in_gy)
                    player.put_creature_in_play(oracle_in_gy)
                    log_fn("  ★ Thassa's Oracle ETB — library empty → WIN", True)
                    gs.game_over = True
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = f"Oops combo ({combo_card.name} → Oracle)"
                    gs.kill_turn = gs.turn
                else:
                    log_fn("  Dread Return countered — combo fizzles")
            else:
                log_fn(f"  Missing pieces for Oracle win (oracle={oracle_in_gy is not None}, dread={dread_in_gy is not None}, creatures={len(player.creatures)})")
        else:
            player.add_to_grave(combo_card)



def _strategy_doomsday(player, opponent, gs, total_mana, log_fn, log_entries):
    """Doomsday combo: cast Doomsday (BBB, pay half life, build 5-card pile),
    then cycle Street Wraith (pay 2 life) to draw into pile, cast Thassa's Oracle
    (UU) to win when devotion to blue >= cards left in library.
    Handles both same-turn win and next-turn win after DD resolved previously."""

    dd_already_resolved = getattr(gs, '_doomsday_pile_built', False)
    mana = total_mana  # track remaining mana

    # ── Helper: cycle cards from hand (activated abilities — uncounterable) ──
    # Repeatedly cycle: each Wraith/Edge drawn from the pile can itself be cycled,
    # chaining through the pile to thin the library for Oracle.
    def _cycle_draw_cards():
        for _ in range(10):  # generous limit for chain-cycling through pile
            wraith = player.find_tag('wraith')
            edge = player.find_tag('edge')
            if wraith and player.life > 2:
                player.remove_from_hand(wraith); player.add_to_grave(wraith)
                player.life -= 2
                gs.check_life_totals()
                if gs.game_over: break
                drawn = player.draw(1)
                drawn_name = drawn[0].name if drawn else 'nothing'
                log_fn(f"  Street Wraith cycles (−2 life → {player.life}) — draws {drawn_name}")
            elif edge and player.lands:
                player.remove_from_hand(edge); player.add_to_grave(edge)
                sac = player.lands.pop(); player.add_to_grave(sac.card)
                drawn = player.draw(1)
                drawn_name = drawn[0].name if drawn else 'nothing'
                log_fn(f"  Edge of Autumn cycles (sac land) — draws {drawn_name}")
            else:
                break
            if gs.bowmasters_on_board:
                ctr = []; bowmasters_triggers(1, gs, ctr)
                for m in ctr: log_entries.append(m)

    # ── Helper: cast Thassa's Oracle and check ETB win ──
    def _try_cast_oracle(avail_mana):
        oracle = player.find_tag('oracle')
        if not oracle or avail_mana < 2:
            return False
        # Pre-check: only cast Oracle when devotion will be high enough to win.
        # Oracle gives 2 blue devotion (UU); count other blue permanents too.
        expected_devotion = 2  # Oracle's own UU
        for c in player.creatures:
            expected_devotion += c.card.mana_cost.get('U', 0)
        if expected_devotion < len(player.library):
            return False  # don't waste Oracle if it won't win yet

        player.remove_from_hand(oracle)
        countered = False
        if not gs.veil_active:
            countered = _try_counter_any(player, opponent, gs, oracle, log_entries)
        if not countered:
            player.put_creature_in_play(oracle)
            lib_size = len(player.library)
            log_fn(f"  ★ Thassa's Oracle ETB — devotion {expected_devotion}, "
                   f"library {lib_size}", True)
            gs.game_over = True
            gs.kill_turn = gs.turn
            gs.winner = 'p1' if player is gs.p1 else 'p2'
            gs.win_reason = (f"Doomsday → Oracle (devotion {expected_devotion} "
                             f"≥ library {lib_size})")
            gs.kill_turn = gs.turn
            return True
        else:
            player.add_to_grave(oracle)
            log_fn("  Oracle countered — Doomsday pile stranded")
            return True  # spell was attempted

    # ── Post-DD turns: pile already built, just draw + cast Oracle ──
    if dd_already_resolved:
        _cycle_draw_cards()
        if not gs.game_over:
            _try_cast_oracle(mana)
        return

    # ── Pre-DD: rituals for mana acceleration ──
    rits = [c for c in player.hand if c.tag == 'darkrit' and opp_can_cast(c, mana, gs, caster=player)]
    extra = 0
    for r in rits:
        player.remove_from_hand(r); player.add_to_grave(r); extra += 2
    if extra: log_fn(f"Dark Ritual ×{len(rits)} → +{extra} mana")
    mana += extra

    # ── Cantrips (pre-DD: dig for combo pieces) ──
    # If we have DD + enough mana, skip mana cantrips to preserve mana for DD.
    # Free cycling (Wraith, Edge) is always fine. Only skip paid cantrips if DD ready.
    dd = player.find_tag('dd')
    dd_ready = dd and mana >= 3  # DD costs BBB = 3 mana

    # Cast free cantrips (cycling) to dig — these don't cost mana
    for _ in range(4):
        # Prefer non-Wraith cantrips pre-DD: save Wraiths for post-DD pile cycling.
        can = None
        if not dd_ready:
            can = next((c for c in player.hand if c.is_cantrip and c.tag not in ('wraith', 'edge')
                        and mana >= 1), None)
        if not can:
            can = next((c for c in player.hand if c.is_cantrip and c.tag == 'edge'
                        and player.lands), None)
        if not can and not dd_ready:
            can = next((c for c in player.hand if c.is_cantrip and c.tag == 'wraith'
                        and player.life > 2), None)
        if not can:
            break
        player.remove_from_hand(can); player.add_to_grave(can)
        if can.tag == 'wraith':
            player.life -= 2
            gs.check_life_totals()
            if gs.game_over: break
            log_fn(f"Street Wraith cycles (−2 life → {player.life}) — draws 1")
            player.draw(1)
        elif can.tag == 'edge':
            if player.lands: sac = player.lands.pop(); player.add_to_grave(sac.card)
            log_fn(f"Edge of Autumn cycles (sac a land) — draws 1")
            player.draw(1)
        else:
            draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
            log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
            player.draw(draws)
            mana -= 1
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(1, gs, ctr)
            for m in ctr: log_entries.append(m)
        # Re-check DD readiness after each cantrip (may have drawn DD or ritual)
        dd = player.find_tag('dd')
        # Also check for new rituals drawn by cantrips
        new_rits = [c for c in player.hand if c.tag == 'darkrit' and opp_can_cast(c, mana, gs, caster=player)]
        for r in new_rits:
            player.remove_from_hand(r); player.add_to_grave(r); mana += 2
            log_fn(f"Dark Ritual → +2 mana")
        dd_ready = dd and mana >= 3  # DD costs BBB = 3 mana

    # ── Cast Doomsday if we have 5+ mana ──
    dd = player.find_tag('dd')
    if dd and mana >= 3:  # DD costs BBB = 3 mana
        dd_resolved = False
        vos = player.find_tag('vos')
        if vos:
            veil_resolved = not _try_counter_any(player, opponent, gs, vos, log_entries)
            player.remove_from_hand(vos); player.add_to_grave(vos)
            if veil_resolved:
                gs.veil_active = True
                log_fn("Veil of Summer — blue interaction blanked")
            else:
                log_fn("Veil of Summer countered")
            # DD must still pass counter check if Veil was countered
            player.remove_from_hand(dd)
            if veil_resolved or not _try_counter_any(player, opponent, gs, dd, log_entries):
                player.add_to_grave(dd)
                log_fn("★ Doomsday resolves" + (" through Veil" if veil_resolved else ""), True)
                dd_resolved = True
            else:
                player.add_to_grave(dd)
                log_fn("Doomsday countered")
        else:
            player.remove_from_hand(dd)
            if not _try_counter_any(player, opponent, gs, dd, log_entries):
                player.add_to_grave(dd)
                log_fn("★ Doomsday resolves", True)
                dd_resolved = True
            else:
                player.add_to_grave(dd)

        if dd_resolved:
            # Doomsday: pay half your life (rounded up)
            half_life = (player.life + 1) // 2
            player.life -= half_life
            log_fn(f"  Doomsday life payment: −{half_life} → {player.life}")
            if player.life <= 0:
                gs.game_over = True
                gs.kill_turn = gs.turn
                gs.winner = 'p2' if player is gs.p1 else 'p1'
                gs.win_reason = f"Doomsday self-kill (life={player.life})"
                return

            # Build a 5-card pile optimized for Oracle win.
            # Pile is filled with Street Wraiths so cycling chains through it,
            # thinning the library to 0-1 cards for Oracle's ETB.
            # Oracle in hand  → [Wraith, Wraith, Wraith, Wraith, X]
            # Oracle NOT in hand → [Oracle, Wraith, Wraith, Wraith, Wraith]
            oracle_in_hand = player.find_tag('oracle')
            from cards import sorcery
            padding = sorcery('Pile Card', 0, {}, set(), tag='pile_padding')
            def _make_wraith():
                return creature('Street Wraith', 5, {'B':2,'generic':3}, {'B'},
                                3, 4, tag='wraith', is_cantrip=True)
            if oracle_in_hand:
                player.library = [_make_wraith() for _ in range(4)] + [padding]
            else:
                oracle_card = creature("Thassa's Oracle", 2, {'U':2}, {'U'}, 1, 3,
                                       tag='oracle', win_condition=True)
                player.library = [oracle_card] + [_make_wraith() for _ in range(4)]
            gs._doomsday_pile_built = True
            log_fn(f"  Pile built: {len(player.library)} cards in library")

            mana -= 3  # DD costs BBB = 3 mana

            # Same-turn win attempt: cycle Wraiths from hand to thin pile + draw Oracle
            _cycle_draw_cards()

            if not gs.game_over:
                _try_cast_oracle(mana)



def _strategy_dimir(player, opponent, gs, total_mana, log_fn, log_entries):
    rem = total_mana  # remaining mana this gs.turn — deduct after each spell cast

    # ── 0a. Thoughtseize — proactive disruption (early turns) ──
    from config import MatchupCategory as MC
    from interaction import best_proactive_target
    ts = player.find_tag('ts')
    ts_turn_cap = 3 if MC.is_combo(gs) else 2  # aligned with config (was 6/3 — too oppressive vs combo)
    if ts and gs.turn <= ts_turn_cap and rem >= 1:
        target = best_proactive_target(gs, opponent) if hasattr(gs, 'p2') else None
        if target:
            player.remove_from_hand(ts)
            player.add_to_grave(ts)
            rem -= 1
            opponent.hand.remove(target)
            opponent.add_to_grave(target)
            player.life -= 2
            log_fn(f"Thoughtseize → takes {target.name} (−2 life, {player.life})", True)

    # ── 0b. Deploy T1 threats (Tamiyo is the best T1 play) ──
    # Real Dimir plays T1 Tamiyo (starts flip clock, 0/3 blocks) or T1 Thoughtseize.
    # Against aggro, prioritize Bowmasters over Tamiyo
    opp_is_aggro = MC.is_aggro(gs)
    # Priority: Tamiyo > Nethergoyf > other cheap creatures
    if opp_is_aggro:
        _deploy_priority = {'bowm': 0, 'tamiyo': 3, 'nether': 1, 'barrow': 1, 'borrow': 4}
    else:
        _deploy_priority = {'tamiyo': 0, 'nether': 1, 'barrow': 1, 'borrow': 3}
    cheap_threats = [(c, _deploy_priority.get(c.tag, 2))
                     for c in player.hand
                     if c.is_creature() and c.cmc <= rem
                     and c.tag not in ('snuffout', 'murk')]
    cheap_threats.sort(key=lambda x: x[1])

    for thr, _ in cheap_threats[:1]:  # deploy one creature
        player.remove_from_hand(thr)
        if not _try_counter_any(player, opponent, gs, thr, log_entries):
            player.put_creature_in_play(thr)
            log_fn(f"{thr.name} ({thr.base_power}/{thr.base_toughness})")
            rem -= thr.cmc
            if getattr(thr, 'engine', False) and thr.cmc == 2:
                drawn = player.draw(1)
                if drawn: log_fn(f"  Strix ETB → draws {drawn[0].name}")
                if gs.bowmasters_on_board:
                    ctr = []; bowmasters_triggers(1, gs, ctr)
                    for m in ctr: log_entries.append(m)
            elif thr.tag == 'barrow':
                update_goyf(gs)
                log_fn(f"  Barrowgoyf P/T: {player.creatures[-1].power}/{player.creatures[-1].toughness}")
        else:
            player.add_to_grave(thr)
        break

    # ── 1. Cantrips — cast with remaining mana ──
    can = next((c for c in player.hand if c.is_cantrip and rem >= 1), None)
    if can:
        player.remove_from_hand(can); player.add_to_grave(can)
        rem -= 1  # spent 1 mana on cantrip
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)
    # Mishra's Bauble: CMC 0, tap+sac → artifact in own GY, draw at next upkeep
    # Sacrifice every copy immediately: grow Nethergoyf T, queue delayed draws
    for bauble in list(player.hand):
        if bauble.tag == 'bauble':
            player.remove_from_hand(bauble)
            player.add_to_grave(bauble)          # artifact type now in opp GY → Nethergoyf T+1
            gs.pending_bauble_draws = getattr(gs, 'pending_bauble_draws', 0) + 1
            update_goyf(gs)
            log_fn(f"Mishra\'s Bauble (sac, artifact in GY, +1 draw next upkeep)")
    # Deploy second creature if mana permits (moved primary deploy to top)
    thr2 = player.find_any(lambda c: c.is_creature() and c.cmc <= rem and c.tag not in ('bowm','snuffout','murk'))
    if thr2 and rem >= thr2.cmc:
        player.remove_from_hand(thr2)
        if not _try_counter_any(player, opponent, gs, thr2, log_entries):
            player.put_creature_in_play(thr2)
            log_fn(f"{thr2.name} ({thr2.base_power}/{thr2.base_toughness})")
            rem -= thr2.cmc
            if thr2.tag == 'barrow':
                update_goyf(gs)
        else: player.add_to_grave(thr2)

    # Deploy Bowmasters: flash creature that provides a blocker and pings on draws.
    # In real Legacy, Bowmasters is cast on opponent's turn (flash), but since
    # the sim doesn't model between-turn flash timing, deploy it on our turn
    # when we have spare mana and need a body for blocking or board presence.
    bowm_in_play = any(c.card.tag == 'bowm' for c in player.creatures)
    bowm = player.find_tag('bowm')
    if bowm and rem >= 2 and not bowm_in_play:
        player.remove_from_hand(bowm)
        if not _try_counter_any(player, opponent, gs, bowm, log_entries):
            perm = player.put_creature_in_play(bowm)
            rem -= 2
            log_fn(f"Orcish Bowmasters (1/1, flash)")
            gs.bowmasters_on_board = True
            # Bowmasters ETB: deal 1 damage to any target, create 1/1 Orc Army
            if opponent.creatures:
                # Target smallest enemy creature (ping to kill 1/1s like infect creatures)
                target = min(opponent.creatures, key=lambda c: c.toughness)
                if target.toughness <= 1:
                    opponent.remove_creature(target)
                    log_fn(f"  Bowmasters ETB: pings {target.card.name} (dies)")
                    update_goyf(gs)
            from rules import Permanent
            army_card = creature("Orc Army", 1, {}, set(), 1, 1, tag='army')
            army_perm = Permanent(card=army_card, controller=perm.controller)
            player.creatures.append(army_perm)
        else:
            player.add_to_grave(bowm)
    push = player.find_tag('push')
    if push and opponent.creatures:
        # Fatal Push costs 1B; mana after paying = rem - 1 (for ward check)
        _push_mana_after = rem - 1
        target = next((c for c in opponent.creatures
                       if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)
                       and _can_target(c, _push_mana_after)), None)
        if target:
            player.remove_from_hand(push); player.add_to_grave(push)
            opponent.remove_creature(target)
            rev = "[revolt CMC≤4]" if player.revolt_this_turn else "[CMC≤2]"
            log_fn(f"Fatal Push {rev} → kills {target.name}")
            update_goyf(gs)
    # Snuff Out — free (pay 4 life) if controlling a Swamp; destroy nonblack creature
    snuff = player.find_tag('snuffout')
    # Snuff Out: 'if you control a Swamp' = any land with Swamp subtype (incl. duals)
    has_swamp = any('Swamp' in l.card.subtypes or (l.card.is_basic and 'B' in l.effective_produces()) for l in player.lands)
    if snuff and has_swamp and opponent.creatures:
        # Snuff Out is free (pay life); all rem mana available for ward
        target = next((c for c in sorted(opponent.creatures, key=lambda x: -x.power)
                       if 'B' not in c.card.colors and _can_target(c, rem)), None)
        if target:
            player.cast_spell(snuff)  # pays life_cost=4
            opponent.remove_creature(target)
            log_fn(f"Snuff Out (free, −4 life → {player.life}) → kills {target.name} (nonblack)", True)
            update_goyf(gs)

    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        eligible_wt = [l for l in opponent.lands if MTGRules.wasteland_can_target(l)]
        if eligible_wt:
            # Prioritize combo lands (Depths, Stage, Cradle) over duals/utility
            _COMBO_LAND_TAGS = {'depths', 'stage', 'cradle', 'tomb', 'city'}
            def _wl_prio(land):
                if land.card.tag in _COMBO_LAND_TAGS: return 10
                if land.card.tag == 'dual': return 3
                return 1
            wt = max(eligible_wt, key=_wl_prio)
            player.lands.remove(wl); player.add_to_grave(wl.card)
            opponent.lands.remove(wt); opponent.add_to_grave(wt.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland [ACTIVATED-uncounterable] → {wt.name}")
            update_goyf(gs)
    # UWx selective combat: only attack with creatures that can deal unblocked damage
    # or that trade favourably. Hold Riddler back until it's larger than BUG blockers.
    bug_max_blocker_toughness = max((c.toughness for c in opponent.creatures), default=0)
    bug_max_blocker_power     = max((c.power     for c in opponent.creatures), default=0)

    # Combat: decide which Mardu creatures attack
    # Bowmasters: VALUE engine — pings opponent every draw step.
    # Never trade it in combat unless the board is desperate.
    # Only attack with Bowmasters if opponent has no blockers (unblocked damage)
    # or if Mardu is so far behind it must race.
    opp_has_blockers = len(opponent.creatures) > 0
    mardu_desperate  = player.life < CT.DESPERATE_LIFE   # racing, need every point
    attackers_this_turn = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'bowm':
            # Hold Bowmasters back unless unblocked or desperate
            if not opp_has_blockers or mardu_desperate:
                attackers_this_turn.append(c)
            # else: keep pinging, don't trade in combat
        elif c.card.tag == 'tamiyo':
            pass   # 0/3 blocks, doesn't attack
        else:
            attackers_this_turn.append(c)

    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)



def _strategy_dimir_flash(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Dimir Flash strategy — same as Dimir Tempo but with Wan Shi Tong as the key threat.
    WST held at instant speed until BUG taps out or end of BUG's gs.turn.
    Key rules:
    - WST enters with X +1/+1 counters, draws X/2 cards (rounded down)
    - WST triggers +1/+1 + draw whenever BUG searches their library (fetches)
    - WST has flash+flying+vigilance — can block AND attack same gs.turn if cast on BUG's EOT
    Strategy: cantrip, hold up WST at X=2-3 (3-4 mana), cast on BUG's EOT for maximum value
    """

    # ── Cantrips ──
    # Cantrips: find any CMC1 noncreature spell opp can cast
    can = next((c for c in player.hand
                if c.is_cantrip and opp_can_cast(c, total_mana, gs, caster=player)), None)
    if can:
        player.remove_from_hand(can); player.add_to_grave(can)
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)

    # ── Wan Shi Tong — cast with maximum X affordable ──
    # X=0 ({U}{U}) = 2 mana: just a 1/1 flier with vigilance, still triggers fetches
    # X=1 ({1}{U}{U}) = 3 mana: 2/2 flier, draws 0 extra on ETB but grows from fetches
    # X=2 ({2}{U}{U}) = 4 mana: 3/3, draws 1 card — minimum for real value
    # Real players hold for X=2+, but will deploy X=0-1 if empty-handed or way behind
    wst_card = player.find_tag('wst')
    wst_on_board = next((p for p in player.creatures if p.card.tag == 'wst'), None)
    if wst_card and not wst_on_board and opp_can_cast(wst_card, total_mana, gs, caster=player):
        x = max(0, min(total_mana - 2, 4))  # pay UU + X generic
        # Deploy at X≥1 (2/2 flier w/ vigilance is strong) or X=0 with no board
        # Earlier WST = more fetch triggers = more cards + bigger body
        has_board = len(player.creatures) > 0
        deploy = (x >= 1) or (x >= 0 and not has_board and total_mana >= 2)
        if deploy:
            player.remove_from_hand(wst_card)
            if not _try_counter_any(player, opponent, gs, wst_card, log_entries):
                perm = player.put_creature_in_play(wst_card)
                perm.power_mod = x
                perm.toughness_mod = x
                cards_drawn = x // 2
                log_fn(f"Wan Shi Tong, Librarian (X={x}) enters as {perm.power}/{perm.toughness}")
                if cards_drawn > 0:
                    drawn = player.draw(cards_drawn)
                    if drawn:
                        log_fn(f"  WST ETB: draws {cards_drawn} card(s)")
                    if gs.bowmasters_on_board:
                        ctr = []; bowmasters_triggers(cards_drawn, gs, ctr)
                        for m in ctr: log_entries.append(m)
            else:
                player.add_to_grave(wst_card)

    # ── Other threats (Bowmasters, Murktide, Tamiyo) ──
    thr = player.find_any(lambda c: c.is_creature() and c.cmc <= total_mana and c.tag not in ('bowm','wst','snuffout'))
    if thr:
        player.remove_from_hand(thr)
        if not _try_counter_any(player, opponent, gs, thr, log_entries):
            player.put_creature_in_play(thr)
            log_fn(f"{thr.name} ({thr.base_power}/{thr.base_toughness})")
        else:
            player.add_to_grave(thr)

    # ── Bowmasters at flash speed ──
    bowm = player.find_tag('bowm')
    if bowm and opp_can_cast(bowm, total_mana, gs, caster=player):
        player.remove_from_hand(bowm)
        if not _try_counter_any(player, opponent, gs, bowm, log_entries):
            player.put_creature_in_play(bowm)
            log_fn(f"Flash Bowmasters")
        else:
            player.add_to_grave(bowm)

    # ── Removal ──
    push = player.find_tag('push')
    if push and opponent.creatures:
        # Fatal Push costs 1B; mana after paying = total_mana - 1 (for ward check)
        _push_mana_after = total_mana - 1
        target = next((c for c in opponent.creatures
                       if MTGRules.fatal_push_valid_target(c, player.revolt_this_turn)
                       and _can_target(c, _push_mana_after)), None)
        if target:
            player.remove_from_hand(push); player.add_to_grave(push)
            opponent.remove_creature(target)
            rev = "[revolt CMC≤4]" if player.revolt_this_turn else "[CMC≤2]"
            log_fn(f"Fatal Push {rev} → kills {target.name}")
            update_goyf(gs)

    # ── Wasteland ──
    wl = next((l for l in player.lands if l.card.tag == 'wl' and not l.tapped), None)
    if wl:
        wt = next((l for l in opponent.lands if MTGRules.wasteland_can_target(l)), None)
        if wt:
            player.lands.remove(wl); player.add_to_grave(wl.card)
            opponent.lands.remove(wt); opponent.add_to_grave(wt.card)
            opponent.revolt_this_turn = True
            log_fn(f"Wasteland [ACTIVATED-uncounterable] → {wt.name}")
            update_goyf(gs)

    # UWx selective combat: only attack with creatures that can deal unblocked damage
    # or that trade favourably. Hold Riddler back until it's larger than BUG blockers.
    bug_max_blocker_toughness = max((c.toughness for c in opponent.creatures), default=0)
    bug_max_blocker_power     = max((c.power     for c in opponent.creatures), default=0)

    # Combat: decide which Mardu creatures attack
    # Bowmasters: VALUE engine — pings opponent every draw step.
    # Never trade it in combat unless the board is desperate.
    # Only attack with Bowmasters if opponent has no blockers (unblocked damage)
    # or if Mardu is so far behind it must race.
    opp_has_blockers = len(opponent.creatures) > 0
    mardu_desperate  = player.life < CT.DESPERATE_LIFE   # racing, need every point
    attackers_this_turn = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'bowm':
            # Hold Bowmasters back unless unblocked or desperate
            if not opp_has_blockers or mardu_desperate:
                attackers_this_turn.append(c)
            # else: keep pinging, don't trade in combat
        elif c.card.tag == 'tamiyo':
            pass   # 0/3 blocks, doesn't attack
        else:
            attackers_this_turn.append(c)

    combat_declare(player, opponent, gs, log_entries, attackers_this_turn)




def _strategy_uwx(player, opponent, gs, total_mana, log_fn, log_entries):
    """UWx Control — protagonist-aware strategy.
    Priority: removal → Mentor (win condition) → lock pieces → cantrips → combat.
    Mana tracked via mana_ref to avoid phantom multi-casting.
    Reactive hook: FoW/Daze/STP used against opponent threats.
    """
    mana_ref = [total_mana]

    def can_cast(card):
        return opp_can_cast(card, mana_ref[0], gs, caster=player)

    def spend(card):
        mana_ref[0] -= card.cmc

    def mentor_trigger():
        if any(c.card.tag == 'mentor' for c in player.creatures):
            player.put_creature_in_play(_MONK_TOKEN)
            log_fn("  Mentor trigger → 1/1 Monk token")

    # ── STP — instant removal, fire 1 proactively (save rest for BUG's turn) ──
    stp = player.find_tag('stp')
    if stp and opponent.creatures and mana_ref[0] >= 1:
        target = max(opponent.creatures, key=lambda c: c.power)
        if target.power >= 2:   # only exile real threats (2+ power)
            player.remove_from_hand(stp); player.add_to_grave(stp)
            life_gain = MTGRules.stp_life_gain(target)
            opponent.remove_creature(target, to_exile=True)
            opponent.life += life_gain
            spend(stp)
            log_fn(f"Swords to Plowshares → exiles {target.card.name}, opp gains {life_gain} life")
            update_goyf(gs)
            mentor_trigger()

    # ── Terminus — wrath when opp has 2+ creatures AND we don't have Mentor on board ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    opp_threat = sum(c.power for c in opponent.creatures)
    # Only Terminus if: opp has 2+ creatures, AND (no Mentor on board OR opp is lethal)
    if len(opponent.creatures) >= 2 and (not mentor_on_board or opp_threat >= player.life):
        term = player.find_tag('terminus')
        if term:
            player.remove_from_hand(term); player.add_to_grave(term)
            for c in list(opponent.creatures):
                opponent.exile.append(c.card); opponent.revolt_this_turn = True
            opponent.creatures.clear()
            for c in list(player.creatures): player.library.append(c.card)
            player.creatures.clear()
            log_fn("★ Terminus (Miracle {W}) — all creatures on bottom of library", True)
            update_goyf(gs)

    # ── Monastery Mentor — primary win condition, deploy aggressively ──
    mentor_on_board = any(c.card.tag == 'mentor' for c in player.creatures)
    mentor = player.find_tag('mentor')
    if mentor and not mentor_on_board and can_cast(mentor):
        player.remove_from_hand(mentor)
        if not _try_counter_any(player, opponent, gs, mentor, log_entries):
            player.put_creature_in_play(mentor)
            spend(mentor)
            log_fn("★ Monastery Mentor (2/2 prowess — tokens on noncreature spells)", True)
        else:
            player.add_to_grave(mentor)

    # ── Snapcaster Mage — flashback value ──
    snap = player.find_tag('snap')
    if snap and can_cast(snap):
        stp_fb  = next((c for c in player.graveyard
                        if c.is_removal and not c.is_mass_removal and c.cmc == 1
                        and opponent.creatures and max(c2.power for c2 in opponent.creatures) >= 2), None)
        term_fb = next((c for c in player.graveyard if c.tag == 'terminus'), None) if len(opponent.creatures) >= 2 else None
        bs_fb   = next((c for c in player.graveyard if c.is_cantrip), None)
        fb = stp_fb or term_fb or bs_fb
        if fb:
            player.remove_from_hand(snap)
            if not _try_counter_any(player, opponent, gs, snap, log_entries):
                player.put_creature_in_play(snap); spend(snap)
                log_fn(f"Snapcaster Mage (2/1) — flashback {fb.name}")
                if fb == stp_fb and opponent.creatures:
                    t = max(opponent.creatures, key=lambda c: c.power)
                    lg = MTGRules.stp_life_gain(t)
                    opponent.remove_creature(t, to_exile=True); opponent.life += lg
                    player.graveyard.remove(fb); player.exile.append(fb)
                    log_fn(f"  Snapcaster flashback STP → exiles {t.card.name}", True)
                    update_goyf(gs)
                elif fb == term_fb and opponent.creatures:
                    for c in list(opponent.creatures): opponent.exile.append(c.card); opponent.revolt_this_turn = True
                    opponent.creatures.clear()
                    for c in list(player.creatures): player.library.append(c.card)
                    player.creatures.clear()
                    player.graveyard.remove(fb); player.exile.append(fb)
                    log_fn("  Snapcaster flashback Terminus", True); update_goyf(gs)
                elif fb == bs_fb:
                    player.graveyard.remove(fb); player.exile.append(fb)
                    drawn = player.draw(MTGRules.brainstorm_draws())
                    log_fn(f"  Snapcaster flashback Brainstorm ({len(drawn)} draw)")
                    bowmasters_triggers(len(drawn), gs, log_entries, controller='o' if player is gs.p1 else 'b')
            else:
                player.add_to_grave(snap)

    # ── Back to Basics — deploy BEFORE cantrips (lock BUG out of mana early) ──
    b2b = player.find_tag('b2b')
    if b2b and not gs.b2b_on_board and can_cast(b2b):
        player.remove_from_hand(b2b)
        if not _try_counter_any(player, opponent, gs, b2b, log_entries):
            player.put_enchantment_in_play(b2b); spend(b2b)
            gs.set_b2b(True)
            log_fn("★ Back to Basics — nonbasic lands don't untap", True)
            mentor_trigger()
        else:
            player.add_to_grave(b2b)

    # ── Narset — lock piece, deploy before cantrips to restrict BUG draws ──
    narset = player.find_tag('narset')
    narset_on_board = any(p.card.tag == 'narset' for p in player.planeswalkers)
    if narset and not narset_on_board and can_cast(narset):
        player.remove_from_hand(narset)
        if not _try_counter_any(player, opponent, gs, narset, log_entries):
            player.put_planeswalker_in_play(narset); spend(narset)
            log_fn("★ Narset, Parter of Veils — opponent can only draw one card per turn", True)
            mentor_trigger()
        else:
            player.add_to_grave(narset)

    # ── Cantrips — cast up to 2 per turn (hold mana for reactive counters) ──
    for _ in range(2):
        if mana_ref[0] < 1: break
        can_c = next((c for c in player.hand if c.is_cantrip and can_cast(c)), None)
        if not can_c: break
        player.remove_from_hand(can_c); player.add_to_grave(can_c); spend(can_c)
        draws = MTGRules.brainstorm_draws() if can_c.tag == 'bs' else 1
        log_fn(f"{can_c.name} ({draws} draw{'s' if draws>1 else ''})")
        player.draw(draws)
        bowmasters_triggers(draws, gs, log_entries, controller='o' if player is gs.p1 else 'b')
        mentor_trigger()

    # ── Combat ──
    bug_max_t = max((c.toughness for c in opponent.creatures), default=0)
    attackers = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'riddler':
            if c.power > bug_max_t: attackers.append(c)
        elif c.card.tag in ('tamiyo',): pass   # 0/3 doesn't attack productively
        else:
            attackers.append(c)
    if attackers:
        combat_declare(player, opponent, gs, log_entries, attackers)


def _strategy_painter(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Painter (Tron/Karn shell) — based on XanaZero 1st Legacy Challenge 2026-04-04.
    Win: Painter's Servant + Grindstone (mill entire library).
    Plan: fast mana → Karn wishes for combo pieces → assemble and win.
    The One Ring provides card draw + protection. Tezzeret recurs artifacts.
    """

    # ── 0. Fast mana: Lotus Petal, Mox Opal, Grim Monolith ──
    for _ in range(6):
        petal = player.find_tag('petal') or player.find_tag('opal')
        if petal:
            player.remove_from_hand(petal); player.add_to_grave(petal)
            total_mana += 1
            log_fn(f"{petal.name} → +1 mana")
            continue
        mono = player.find_tag('monolith')
        if mono and total_mana >= 2:
            player.remove_from_hand(mono); player.put_artifact_in_play(mono)
            total_mana += 1  # costs 2, taps for 3 (net +1 same turn)
            log_fn("Grim Monolith → +3 mana")
            continue
        break

    # ── 1. Check if combo is already assembled ──
    painter_in_play = any(p.card.tag == 'painter' for p in player.artifacts + player.creatures)
    grind_in_play = any(p.card.tag == 'grind' for p in player.artifacts)

    if painter_in_play and grind_in_play and total_mana >= 3:
        log_fn("★ Painter + Grindstone — mills entire library!", True)
        gs.game_over = True
        gs.kill_turn = gs.turn
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = "Painter + Grindstone combo"
        return

    # ── 2. Deploy combo pieces from hand ──
    p_card = player.find_tag('painter')
    if p_card and not painter_in_play and total_mana >= 2:
        player.remove_from_hand(p_card)
        if not _try_counter_any(player, opponent, gs, p_card, log_entries):
            player.put_artifact_in_play(p_card)
            total_mana -= 2
            painter_in_play = True
            log_fn("Painter's Servant (naming blue)", True)
        else:
            player.add_to_grave(p_card)

    grind_card = player.find_tag('grind')
    if grind_card and not grind_in_play and total_mana >= 1:
        player.remove_from_hand(grind_card)
        if not _try_counter_any(player, opponent, gs, grind_card, log_entries):
            player.put_artifact_in_play(grind_card)
            total_mana -= 1
            grind_in_play = True
            log_fn("Grindstone", True)
        else:
            player.add_to_grave(grind_card)

    # Check combo again after deploying
    if painter_in_play and grind_in_play and total_mana >= 3:
        log_fn("★ Painter + Grindstone — mills entire library!", True)
        gs.game_over = True
        gs.kill_turn = gs.turn
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = "Painter + Grindstone combo"
        return

    # ── 3. The One Ring — card draw + protection ──
    ring = player.find_tag('ring')
    if ring and total_mana >= 4:
        player.remove_from_hand(ring)
        if not _try_counter_any(player, opponent, gs, ring, log_entries):
            player.put_artifact_in_play(ring)
            total_mana -= 4
            player.draw(2)  # approximate: Ring draws cards over time
            log_fn("The One Ring — protection + draw 2", True)
        else:
            player.add_to_grave(ring)

    # ── 4. Karn, the Great Creator — wish for combo/lock pieces ──
    karn_on_board = any(p.card.tag == 'karn' for p in player.artifacts)

    def _karn_wish():
        nonlocal painter_in_play, grind_in_play
        if not grind_in_play and painter_in_play:
            gs_card = artifact('Grindstone', 1, {'generic':1}, tag='grind', win_condition=True)
            player.put_artifact_in_play(gs_card)
            grind_in_play = True
            log_fn("  Karn +1: wishes for Grindstone", True)
        elif not painter_in_play:
            ps_card = creature("Painter's Servant", 2, {'generic':2}, set(), 1, 3,
                               tag='painter', is_combo_piece=True)
            player.put_artifact_in_play(ps_card)
            painter_in_play = True
            log_fn("  Karn +1: wishes for Painter's Servant", True)
        elif not gs.bridge_on_board and opponent.creatures:
            gs.bridge_on_board = True
            log_fn("  Karn +1: wishes for Ensnaring Bridge", True)

    if karn_on_board:
        _karn_wish()

    karn = player.find_tag('karn')
    if karn and total_mana >= 4 and not karn_on_board:
        player.remove_from_hand(karn)
        if not _try_counter_any(player, opponent, gs, karn, log_entries):
            player.put_artifact_in_play(karn)
            total_mana -= 4
            log_fn("Karn, the Great Creator", True)
            _karn_wish()
        else:
            player.add_to_grave(karn)

    # Check combo once more after Karn wish
    if painter_in_play and grind_in_play and total_mana >= 3:
        log_fn("★ Painter + Grindstone — mills entire library!", True)
        gs.game_over = True
        gs.kill_turn = gs.turn
        gs.winner = 'p1' if player is gs.p1 else 'p2'
        gs.win_reason = "Painter + Grindstone combo"
        return

    # ── 5. Disruptor Flute (name a key card) ──
    flute = player.find_tag('flute')
    if flute and total_mana >= 3:
        player.remove_from_hand(flute); player.put_artifact_in_play(flute)
        total_mana -= 3
        log_fn("Disruptor Flute — names opponent's key card", True)



def _strategy_storm(player, opponent, gs, total_mana, log_fn, log_entries):

    # Cantrips: find any CMC1 noncreature spell opp can cast
    can = next((c for c in player.hand
                if c.is_cantrip and opp_can_cast(c, total_mana, gs, caster=player)), None)
    if can:
        player.remove_from_hand(can); player.add_to_grave(can)
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)
    # Rituals: affordable from total_mana + ritual chaining.
    # IMPORTANT: rituals generate mana — so cascade:
    # with 1 land (1 mana): cast Dark Ritual (costs 1) → +2 net → now have 3 mana
    # → can cast Cabal Ritual (costs 3) → +2 more net → etc.
    # Model: ritual chain is feasible if we have any starting mana + 1 ritual.
    def _ritual_cost(c): return max(sum(c.mana_cost.values()), c.cmc)  # respects Trinisphere via raised cmc
    # Chalice check: rituals blocked by Chalice can't be cast
    def _chalice_blocks(c): return gs.spell_blocked_by_chalice(c.cmc)
    # Simulate mana available after casting affordable rituals
    # LED can be cracked in response to any spell for 3 mana of any color
    # Under Trinisphere, LED costs 3 to cast (artifact spell, CMC 0 → taxed to 3)
    led = player.find_tag('led')
    led_castable = led and total_mana >= led.cmc  # cmc already raised to 3 by Trini
    led_mana = 3 if led_castable else 0
    led_cost = led.cmc if led_castable else 0
    sim_mana = total_mana - led_cost + led_mana  # pay to cast LED, then crack for 3
    # First pass: rituals affordable from land mana (exclude Chalice-blocked)
    def _is_ritual(c): return c.mana_ritual or c.tag in ('darkrit','cabalrit')
    rituals = [c for c in player.hand if _is_ritual(c) and _ritual_cost(c) <= sim_mana
               and not _chalice_blocks(c)]
    # Second pass: rituals affordable after netting mana from first rituals
    for r in rituals:
        net = sum(r.mana_produced.values()) - _ritual_cost(r) if hasattr(r,'mana_produced') else 2
        sim_mana += net
    rituals2 = [c for c in player.hand if _is_ritual(c) and c not in rituals
                and _ritual_cost(c) <= sim_mana and not _chalice_blocks(c)]
    rituals = rituals + rituals2
    # Infernal Tutor acts as a ritual proxy: if in hand and mana available,
    # it can fetch a ritual or kill spell. Use card.cmc (which respects Thalia's
    # +1 tax applied in apply_lock_effects) — not a hardcoded 2.
    _itutor_card = player.find_tag('itutor')
    itutor_proxy = _itutor_card and sim_mana >= _itutor_card.cmc
    tendrils = player.find_tag('tendrils')
    # Storm should only go off when safe: Veil active, opp has no FoW, or desperate
    veil_protecting = getattr(gs, 'veil_active', False)
    opp_clock = sum(c.power for c in opponent.creatures if not c.summoning_sick)
    storm_desperate = opp_clock > 0 and player.life <= opp_clock * 2  # dead in ~2 attacks
    # Also desperate if life is dropping fast (burn spells, not just creatures)
    # If we've lost 5+ life and opponent has no counters, just go for it
    life_lost = 20 - player.life
    opp_has_counters = any(c.tag in ('fow', 'fon', 'daze', 'counter', 'fluster')
                           for c in opponent.hand)
    if life_lost >= 5 and not opp_has_counters:
        storm_desperate = True
    # Also desperate at ≤10 life regardless (getting close to lethal range)
    if player.life <= 10:
        storm_desperate = True
    # Thalia-desperate: if Thalia is out, rituals net less mana and waiting
    # only makes things worse (D&T will add Phyrexian Revoker / SFM pressure
    # next turn). Take any kill line we have.
    thalia_on_table = any(getattr(c.card, 'tag', None) == 'thalia'
                          for c in opponent.creatures)
    if thalia_on_table and (len(rituals) >= 2 or (led_castable and len(rituals) >= 1)):
        storm_desperate = True
    # Check if opponent likely has free counter (FoW/FoN + blue pitch card)
    opp_fow = any(c.tag in ('fow', 'fon') for c in opponent.hand)
    opp_blue_pitch = any(c for c in opponent.hand
                         if 'U' in getattr(c, 'colors', set()) and c.tag not in ('fow', 'fon'))
    opp_has_free_counter = opp_fow and opp_blue_pitch
    # Need enough mana sources to support a ritual chain (land mana, not just LED)
    has_mana_base = total_mana >= 1 or len(rituals) >= 1
    safe_to_combo = (veil_protecting or storm_desperate or
                     (has_mana_base and not opp_has_free_counter))
    itutor   = player.find_tag('itutor')
    led      = player.find_tag('led')
    adnaus   = player.find_tag('adnauseam')
    pif      = player.find_tag('pif')

    # ── Kill-hand heuristics (any one = enough to assemble lethal storm) ────
    # Each criterion represents a known ANT goldfish line that reaches storm ≥9.
    # Storm count estimate: each ritual/LED/tutor = +1 spell cast before Tendrils.
    # Lethal Tendrils needs storm ≥ 9 (10 copies × 2 damage = 20).
    # Chalice blocks spells with matching CMC — check each kill component.
    tendrils_blocked = tendrils and _chalice_blocks(tendrils)
    itutor_blocked = itutor and _chalice_blocks(itutor)
    adnaus_blocked = adnaus and _chalice_blocks(adnaus)
    pif_blocked = pif and _chalice_blocks(pif)
    win_available = ((tendrils and not tendrils_blocked) or (itutor and not itutor_blocked))

    # Estimate storm count from castable spells before Tendrils resolves.
    # Count ALL spells that would be cast: rituals, LED, tutor, cantrips, Veil, PiF.
    # Tendrils = 2 damage per copy (1 original + N storm copies).
    # Lethal needs storm >= ceil(opponent.life / 2) - 1, typically 9 for 20 life.
    cantrips_in_hand = sum(1 for c in player.hand if c.is_cantrip)
    vos_in_hand = player.find_tag('vos')
    est_storm = (len(rituals) + (1 if led else 0) + (1 if itutor_proxy else 0)
                 + cantrips_in_hand + (1 if vos_in_hand else 0) + (1 if pif else 0))
    lethal_storm = max(1, (opponent.life + 1) // 2 - 1)  # storm copies needed for lethal
    # Under Thalia, rituals net less mana — Storm can't afford to wait for a
    # "clean" kill hand. Accept one-short storm counts: if we can storm for
    # lethal_storm - 1, the final itutor/tendrils cast pushes us over.
    if thalia_on_table:
        lethal_storm = max(1, lethal_storm - 1)
    # Ad Nauseam / Past in Flames self-generate storm during resolution (draw 15+ / replay GY)
    self_assembles = False

    kill_A = bool(led_castable and len(rituals) >= 2 and win_available and est_storm >= lethal_storm)
    kill_B = bool(len(rituals) >= 3 and led_castable and win_available and est_storm >= lethal_storm)
    kill_C = bool(adnaus and not adnaus_blocked and sim_mana >= adnaus.cmc and
                  (len(rituals) >= 1 or sim_mana >= adnaus.cmc + 2))  # Ad Nauseam self-assembles
    kill_D = bool(pif and not pif_blocked and len(player.graveyard) >= 4 and sim_mana >= 4)  # PiF replays GY
    kill_E = bool(len(rituals) >= 3 and win_available and est_storm >= lethal_storm)
    kill_F = bool(itutor_proxy and len(rituals) >= 2 and sim_mana >= 3 and est_storm >= lethal_storm)
    self_assembles = kill_C or kill_D  # these generate their own storm count
    can_kill = kill_A or kill_B or kill_C or kill_D or kill_E or kill_F

    # Strategic trace (no-op unless --trace)
    _fired_kill = next((n for n, k in (('A', kill_A), ('B', kill_B), ('C', kill_C),
                                       ('D', kill_D), ('E', kill_E), ('F', kill_F)) if k), 'pass')
    gs.strat_log.log_decision(
        gs.turn, 'storm',
        candidates=['kill_A', 'kill_B', 'kill_C', 'kill_D', 'kill_E', 'kill_F', 'pass'],
        chosen=('kill_' + _fired_kill) if can_kill else 'pass',
        reason=(f"storm={est_storm}/{lethal_storm}, rituals={len(rituals)}, "
                f"safe={safe_to_combo}, thalia={thalia_on_table}, life={player.life}"))

    if can_kill and safe_to_combo:
        # ── Try to protect with Veil of Summer first ────────────────────────
        vos = player.find_tag('vos')
        veil_up = False
        opp_has_blue = any('U' in str(l.effective_produces()) for l in opponent.lands)
        if vos and opp_has_blue and sim_mana >= 1:
            if not _try_counter_any(player, opponent, gs, vos, log_entries):
                player.remove_from_hand(vos); player.add_to_grave(vos)
                gs.veil_active = True
                log_fn("Veil of Summer — opponent's blue interaction blanked this turn", True)
                veil_up = True
            else:
                player.add_to_grave(vos)

        # ── Mindbreak Trap check (colorless — goes through Veil) ────────────
        mindbreak = opponent.find_tag('mindbreak')
        spells_this_turn = getattr(player, 'spells_cast_this_turn', 0)
        if mindbreak and spells_this_turn >= 3:
            opponent.remove_from_hand(mindbreak); opponent.add_to_grave(mindbreak)
            for r in list(rituals): player.remove_from_hand(r); player.add_to_grave(r)
            log_fn(f"★ Mindbreak Trap (free) — Storm fizzles despite Veil", True)
            return

        # ── Execute the kill ────────────────────────────────────────────────
        # Simplified: cast the win condition (Tendrils or Infernal Tutor → Tendrils)
        kill_spell = tendrils or itutor
        if kill_spell:
            player.remove_from_hand(kill_spell)
            countered = _try_counter_any(player, opponent, gs, kill_spell, log_entries)
            if countered:
                # Storm pitches Flusterstorm vs FoW/FoN (65% success; fails vs backup counter)
                import random as _rr
                fluster = player.find_tag('fluster')
                last_ctr = getattr(gs, '_last_counter_used', None)
                opp_has_backup = sum(1 for c in opponent.hand
                                     if c.tag in ('fow','fon','fluster','daze')) >= 2
                can_fluster = (fluster and last_ctr in ('fow','fon','daze')
                               and not opp_has_backup and _rr.random() < 0.65)
                if can_fluster:
                    player.remove_from_hand(fluster); player.add_to_grave(fluster)
                    log_fn(f"  Flusterstorm beats {last_ctr} — {kill_spell.name} resolves!", True)
                    countered = False
            if not countered:
                player.add_to_grave(kill_spell)
                for r in list(rituals): player.remove_from_hand(r); player.add_to_grave(r)
                kill_type = 'Ad Nauseam' if kill_C else 'Past in Flames' if kill_D else 'Tendrils chain'
                # Storm success — non-GY combo, no post-resolution fizzle (was double-jeopardy)
                # Fizzle gate is only for GY combos (Oops, Reanimator) where hate can whiff the combo
                import random as _rr2
                if True:  # Storm always wins if Tendrils resolves through counters
                    log_fn(f"★ Storm {kill_type} — wins (est. storm ~{est_storm + len(rituals)})", True)
                    gs.game_over = True
                    gs.kill_turn = gs.turn
                    gs.winner = 'p1' if player is gs.p1 else 'p2'
                    gs.win_reason = f"ANT combo ({kill_type})"
                else:
                    log_fn(f"Storm {kill_type} fizzles (BUG had backup interaction)")
            else:
                player.add_to_grave(kill_spell)



def _strategy_reanimator(player, opponent, gs, total_mana, log_fn, log_entries):
    """
    Reanimator strategy — correct sequencing:
    1. Lotus Petal (0 mana — always play first, adds free mana)
    2. Unmask (free) — strip opponent's FoW BEFORE building mana (they can't FoW the Unmask)
    3. Dark Ritual — spend {B}, add {B}{B}{B} (net +2). Requires a black source.
    4. Entomb → put Griselbrand/Archon into GY
    5. Reanimate/Exhume/Animate Dead → bring it back

    T1 kill line: Swamp → Petal (free) → Unmask (strips FoW) → Ritual (3B) → Entomb (2B) → Reanimate (1B)
    Reanimate oracle: pay life equal to creature's CMC. Griselbrand=8 → lose 8 life.
    """
    mana = total_mana  # start with land mana (Swamp or fetchable dual = {B})

    # ── Step 1: Lotus Petal — free mana, always first ────────────────────────
    petals = [c for c in player.hand if c.tag == 'petal']
    for p in petals:
        player.remove_from_hand(p)
        player.exile.append(p)
        mana += 1
        log_fn(f"Lotus Petal — mana {mana}")

    # ── Step 2: Unmask (free) — strip FoW BEFORE committing mana ────────────
    # Unmask is free if you reveal your hand and opponent chooses a nonland card you discard.
    # In Reanimator: you CHOOSE to discard the fatties (self-mill + strip their counter).
    unmask = player.find_tag('unmask')
    gris_for_unmask = player.find_tag('gris') or player.find_tag('archon')
    if unmask and gris_for_unmask and gs.turn <= 2:
        player.remove_from_hand(unmask); player.add_to_grave(unmask)
        player.remove_from_hand(gris_for_unmask)
        player.add_to_grave(gris_for_unmask)
        # Strip opponent's best counter
        if opponent.hand:
            target = (next((c for c in opponent.hand if c.tag == 'fow'), None) or
                      next((c for c in opponent.hand if c.tag == 'fon'), None) or
                      next((c for c in opponent.hand if c.free_cast_if_blue), None) or
                      next((c for c in opponent.hand if not c.is_land()), None))
            if target:
                opponent.hand.remove(target)
                log_fn(f"Unmask (free) — discards {gris_for_unmask.name} to GY, strips {target.name}", True)
            else:
                log_fn(f"Unmask (free) — discards {gris_for_unmask.name} to GY")

    # ── Step 3: Dark Ritual — spend {B}, add {B}{B}{B} (net +2) ────────────
    # Requires at least 1 black source (land or prior ritual output).
    # Fire all rituals to maximise mana pool.
    has_black_source = (mana >= 1)  # any mana at this point should be black (Swamp/dual/petal)
    if has_black_source:
        rituals = [c for c in player.hand if c.tag == 'darkrit']
        for r in rituals:
            if mana >= 1:  # spend 1B, get 3B
                player.remove_from_hand(r)
                player.add_to_grave(r)
                mana += 2  # net +2
                log_fn(f"Dark Ritual ({mana-2}B→{mana}B)")

    # ── Careful Study / Brainstorm — fill GY with reanimation targets ────────
    study = player.find_tag('study')
    if study and mana >= 1:
        player.remove_from_hand(study); player.add_to_grave(study)
        mana -= 1
        drawn = player.draw(2)
        # Discard 2 — prefer discarding the fatties into GY
        discard_pref = sorted(player.hand,
            key=lambda c: -(c.cmc if c.win_condition or c.is_combo_piece else 0))
        for c in discard_pref[:2]:
            player.hand.remove(c); player.add_to_grave(c)
            log_fn(f"  Study discards {c.name} to GY")

    # ── Entomb — put target into GY ─────────────────────────────────────────
    entomb = player.find_tag('entomb')
    gy_target = next((c for c in player.graveyard
                      if c.win_condition or c.is_combo_piece and c.is_creature()), None)
    
    if entomb and not gy_target and mana >= 1:
        player.remove_from_hand(entomb)
        if not _try_counter_any(player, opponent, gs, entomb, log_entries):
            player.add_to_grave(entomb)
            mana -= 1
            # Tutor Griselbrand into GY
            target = (next((c for c in player.library if c.tag == 'gris'), None) or
                      next((c for c in player.library if c.win_condition), None))
            if target:
                player.library.remove(target)
                player.add_to_grave(target)
                log_fn(f"Entomb → {target.name} in GY", True)
                gy_target = target
        else:
            player.add_to_grave(entomb)
            log_fn("Entomb countered")

    # ── Reanimate / Exhume / Animate Dead — bring back the target ───────────
    gy_target = next((c for c in player.graveyard
                      if (c.win_condition or c.is_combo_piece) and c.is_creature()), None)
    
    if gy_target and not gs.leyline_active:
        # Try Reanimate (cheapest)
        rean = player.find_tag('reanimate')
        exhume = player.find_tag('exhume')
        animate = player.find_tag('animatedead')
        
        spell = None
        cost = 99
        if rean and mana >= 1:   spell, cost = rean, 1
        elif exhume and mana >= 2: spell, cost = exhume, 2
        elif animate and mana >= 2: spell, cost = animate, 2
        
        if spell:
            player.remove_from_hand(spell)
            if not _try_counter_any(player, opponent, gs, spell, log_entries):
                player.add_to_grave(spell)
                mana -= cost
                # Reanimate oracle: pay life equal to reanimated creature's CMC
                if spell.tag == 'reanimate':
                    life_paid = gy_target.cmc
                    player.life -= life_paid
                    log_fn(f"  Reanimate: pay {life_paid} life ({player.life} remaining)")
                    gs.check_life_totals()
                player.graveyard.remove(gy_target)
                perm = player.put_creature_in_play(gy_target)
                log_fn(f"★ {spell.name} → {gy_target.name} enters play", True)
                # Griselbrand/Archon: extremely powerful but NOT instant-win.
                # Real Legacy gives the opponent a turn to answer (Karakas, Borrower,
                # STP, Fatal Push revolt, etc.). Model the creature correctly:
                # - Griselbrand: 7/7 flying lifelink, draw 7 on ETB (simplified)
                # - Archon: 6/6, ETB drain 3 + draw 1 + discard 1
                # - Atraxa: 7/7 flying lifelink deathtouch, ETB draw 4
                if gy_target.tag == 'gris':
                    # Set flying/lifelink on BOTH perm and card (combat reads card attrs)
                    perm.flying = True
                    perm.lifelink = True
                    gy_target.flying = True
                    gy_target.lifelink = True
                    # Griselbrand: activated ability "Pay 7 life: Draw 7 cards"
                    # Check if Bowmasters would kill us: 7 draws = 7 pings = 7 damage
                    opp_has_bowm = any(c.card.tag == 'bowm' for c in opponent.creatures)
                    bowm_damage = 7 if (opp_has_bowm or gs.bowmasters_on_board) else 0
                    # Need life > 7 (Griselbrand cost) + bowmasters pings + buffer
                    life_after = player.life - 7 - bowm_damage
                    if life_after >= 1:
                        player.life -= 7
                        drawn = player.draw(7)
                        log_fn(f"  Griselbrand: pay 7 life, draw 7 ({player.life} remaining)")
                        # Bowmasters triggers on each of the 7 draws
                        if gs.bowmasters_on_board or opp_has_bowm:
                            bowmasters_triggers(7, gs, log_entries,
                                controller='o' if player is gs.p1 else 'b')
                        gs.check_life_totals()
                elif gy_target.tag == 'archon':
                    # Archon ETB: target opponent sacrifices creature/planeswalker,
                    # discards a card, loses 3 life; you draw, gain 3 life
                    if opponent.creatures:
                        worst = min(opponent.creatures, key=lambda c: c.power)
                        opponent.remove_creature(worst)
                        log_fn(f"  Archon ETB: opponent sacrifices {worst.card.name}")
                    if opponent.hand:
                        worst = min(opponent.hand, key=lambda c: c.cmc)
                        opponent.hand.remove(worst)
                        opponent.graveyard.append(worst)
                    player.draw(1)
                    opponent.life -= 3
                    player.life += 3
                    log_fn(f"  Archon ETB: drain 3, draw 1, opp discards (opp at {opponent.life})")
                    gs.check_life_totals()
                elif gy_target.tag == 'atraxa':
                    # Set flying/lifelink/deathtouch on BOTH perm and card
                    perm.flying = True
                    perm.lifelink = True
                    perm.deathtouch = True
                    gy_target.flying = True
                    gy_target.lifelink = True
                    gy_target.deathtouch = True
                    # Atraxa ETB: reveal top 10, put one of each type into hand
                    drawn = player.draw(4)
                    log_fn(f"  Atraxa ETB: draw 4")
                    gs.check_life_totals()
            else:
                player.add_to_grave(spell)
                log_fn(f"{spell.name} countered")
    elif gy_target and gs.leyline_active:
        log_fn("Leyline active — no GY target available")

    # ── Combat: attack with any non-summoning-sick creatures ─────────────
    if not gs.game_over:
        attackers = [c for c in player.creatures if not c.summoning_sick]
        if attackers:
            combat_declare(player, opponent, gs, log_entries, attackers)
    gs.state_based_actions()


def _strategy_ur_aggro(player, opponent, gs, total_mana, log_fn, log_entries):
    """UR Delver/Aggro: Delver of Secrets, Ragavan, Dragon's Rage Channeler, Murktide.
    Strategy: deploy cheap threats T1-2, protect with Daze/FoW, Bolt face to close."""

    # Cantrips — dig for threats early
    can = next((c for c in player.hand if c.is_cantrip and total_mana >= 1), None)
    if can and len(player.creatures) < 2:
        player.remove_from_hand(can); player.add_to_grave(can)
        draws = MTGRules.brainstorm_draws() if can.tag == 'bs' else 1
        log_fn(f"{can.name} ({draws} draw{'s' if draws > 1 else ''})")
        player.draw(draws)
        total_mana -= 1
        if gs.bowmasters_on_board:
            ctr = []; bowmasters_triggers(draws, gs, ctr)
            for m in ctr: log_entries.append(m)

    # Ragavan — haste, highest priority T1
    rag = player.find_tag('ragavan')
    if rag and not any(c.card.tag == 'ragavan' for c in player.creatures):
        player.remove_from_hand(rag)
        if not _try_counter_any(player, opponent, gs, rag, log_entries):
            player.put_creature_in_play(rag)
            total_mana -= 1
            log_fn("Ragavan, Nimble Pilferer (haste)")
        else:
            player.add_to_grave(rag)

    # Deploy ALL affordable threats (no break — deploy as many as mana allows)
    for tag in ('drc', 'delver', 'murk'):
        threat = player.find_tag(tag)
        if threat and opp_can_cast(threat, total_mana, gs, caster=player):
            player.remove_from_hand(threat)
            if not _try_counter_any(player, opponent, gs, threat, log_entries):
                player.put_creature_in_play(threat)
                total_mana -= threat.cmc
                log_fn(f"{threat.name}")
            else:
                player.add_to_grave(threat)

    # Lightning Bolt — kill key blockers (Bowmasters, Goyf) or go face
    bolt = player.find_tag('bolt')
    if bolt:
        def bolt_priority(c):
            if c.card.tag == 'tamiyo':  return 0
            if c.card.tag == 'bowm':    return 1
            if c.card.tag == 'goyf':    return 2
            if c.toughness <= 2:        return 3
            if c.toughness == 3:        return 4
            return 99
        # Bolt costs 1R; mana after paying = total_mana - 1 (for ward check)
        _bolt_mana_after = total_mana - 1
        candidates = [c for c in opponent.creatures
                      if bolt_priority(c) < 99 and _can_target(c, _bolt_mana_after)]
        target = min(candidates, key=bolt_priority) if candidates else None
        go_face = (target is None and opponent.life <= 15 and len(player.creatures) > 0)
        if target or go_face:
            player.remove_from_hand(bolt); player.add_to_grave(bolt)
            if target:
                opponent.remove_creature(target)
                log_fn(f"Lightning Bolt → {target.card.name}", True); update_goyf(gs)
            else:
                opponent.life -= 3
                log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
                gs.check_life_totals()

    # Daze — hold up on key turns
    # (handled reactively by _try_counter_any)

    # Combat — attack with everything
    attackers = [c for c in player.creatures if not c.summoning_sick]
    combat_declare(player, opponent, gs, log_entries, attackers)

    # Ragavan combat damage trigger — oracle: "deals combat damage to a player"
    if 'ragavan' in getattr(gs, '_combat_unblocked_tags', set()) and opponent.library:
        stolen = opponent.library.pop(0)
        if player is gs.p1:
            gs.p1_treasure = getattr(gs, 'p1_treasure', 0) + 1
        else:
            gs.p2_treasure = getattr(gs, 'p2_treasure', 0) + 1
        log_fn(f"★ Ragavan exiles {stolen.name} from library + creates Treasure", True)
        update_goyf(gs)


def _strategy_mardu(player, opponent, gs, total_mana, log_fn, log_entries):
    """Mardu Initiative/Grief: Grief+Ephemerate T1 strip engine, Ragavan, Bowmasters, Fury."""

    grief = player.find_tag('grief')
    ephemerate = player.find_tag('ephemerate')

    # T1 Grief+Ephemerate: strip 2 cards
    if grief and ephemerate and gs.turn == 1:
        player.remove_from_hand(grief); player.remove_from_hand(ephemerate)
        player.add_to_grave(ephemerate)
        for _ in range(2):
            if opponent.hand:
                t = (opponent.find_any(lambda c: c.free_cast_if_blue) or
                     opponent.find_any(lambda c: c.is_creature()) or
                     (next((c for c in opponent.hand if not c.is_land()), None)))
                if t:
                    opponent.hand.remove(t)
                    log_fn(f"★ Grief ETB — strips {t.name}", True)
        player.put_creature_in_play(grief)

    # Evoke Grief T1-2 (no Ephemerate)
    elif grief and gs.turn <= 2:
        blacks = [c for c in player.hand if 'B' in getattr(c,'colors',set()) and c.tag != 'grief']
        if blacks:
            player.remove_from_hand(grief); player.remove_from_hand(blacks[0])
            player.exile.append(blacks[0])
            if opponent.hand:
                nonlands = [c for c in opponent.hand if not c.is_land()]
                t = next((c for c in nonlands if c.free_cast_if_blue), None) or (nonlands[0] if nonlands else None)
                if t:
                    opponent.hand.remove(t); opponent.add_to_grave(t)
                    log_fn(f"Grief (evoke) strips {t.name}")
            player.add_to_grave(grief)

    # Fury — ETB 4 damage divided, Ephemerate for second wave
    fury = player.find_tag('fury')
    eph2 = player.find_tag('ephemerate')
    if fury and opponent.creatures:
        player.remove_from_hand(fury)
        red_pitch = next((c for c in player.hand if 'R' in getattr(c,'colors',set())), None)
        if red_pitch: player.remove_from_hand(red_pitch); player.exile.append(red_pitch)
        n_waves = 2 if (eph2 and not (grief and ephemerate)) else 1
        if n_waves == 2: player.remove_from_hand(eph2); player.add_to_grave(eph2)
        for wave in range(n_waves):
            targets = sorted(opponent.creatures, key=lambda c: c.toughness)
            rem = 4
            killed, wounded = [], []
            for t in targets:
                if rem <= 0: break
                deal = min(rem, t.toughness); t.damage_marked += deal; rem -= deal
                if t.is_destroyed(): killed.append(t)
                else: wounded.append(t)
            for c in killed: opponent.remove_creature(c)
            label = f"ETB#{wave+1}" + (" (Ephemerate blink)" if wave else "")
            log_fn(f"★ Fury {label} (4 divided) — kills: {[c.name for c in killed]}", True)
        update_goyf(gs); gs.state_based_actions()

    # Thoughtseize — cast early (T1-T3) unless Grief+Ephemerate already stripped
    ts = player.find_tag('ts')
    if ts and opp_can_cast(ts, total_mana, gs, caster=player) and not (grief and ephemerate) and gs.turn <= 3:
        veil_b = opponent.find_tag('vos')
        if veil_b and can_afford(opponent, veil_b.mana_cost):
            opponent.remove_from_hand(veil_b); opponent.add_to_grave(veil_b)
            opponent.draw(1)
            log_fn("Veil of Summer — TS fizzles")
        else:
            player.cast_spell(ts, log_fn=log_fn)
            t = (opponent.find_any(lambda c: c.free_cast_if_blue) or
                 opponent.find_any(lambda c: c.is_creature()))
            if t: opponent.hand.remove(t); log_fn(f"Thoughtseize — strips {t.name}")

    # ── Creature deployment loop — deploy aggressively on curve ──
    # Mardu floods the board: Ragavan T1, Bowmasters T2, second creature T3+
    # Priority: Ragavan (haste, Treasure) > Bowmasters (draw punishment) > Grief (body)
    deploy_tags = ['ragavan', 'bowm', 'grief']
    for tag in deploy_tags:
        card = player.find_tag(tag)
        if not card or not opp_can_cast(card, total_mana, gs, caster=player):
            continue
        # Grief: only deploy as body if Evoke already happened (it's a 3/2 menace)
        if tag == 'grief' and gs.turn <= 2:
            continue  # T1-T2 Grief is handled by Evoke above
        player.remove_from_hand(card)
        if not _try_counter_any(player, opponent, gs, card, log_entries):
            player.put_creature_in_play(card)
            total_mana -= card.cmc
            if tag == 'ragavan':
                log_fn("Ragavan (haste)")
            elif tag == 'bowm':
                log_fn("Orcish Bowmasters (flash)")
            else:
                log_fn(f"{card.name} ({card.base_power}/{card.base_toughness})")
        else:
            player.add_to_grave(card)

    # STP — exile big BUG threats only (Murktide, Kaito — hard to re-deploy)
    stp = player.find_tag('stp')
    if stp and opponent.creatures and opp_can_cast(stp, total_mana, gs, caster=player):
        # STP costs 1W; mana after casting = total_mana - 1 (for ward check)
        mana_after_stp = total_mana - 1
        valid_stp = [c for c in opponent.creatures if _can_target(c, mana_after_stp)]
        target = max(valid_stp, key=lambda c: c.power) if valid_stp else None
        if target and target.power >= 1:  # exile any creature — Mardu is aggressive with removal
            player.remove_from_hand(stp); player.add_to_grave(stp)
            total_mana -= 1
            opponent.remove_creature(target)
            log_fn(f"Swords to Plowshares exiles {target.card.name}")
            update_goyf(gs)

    # Lightning Bolt — creature removal first, face only at ≤ 9 (Mardu is midrange, not pure burn)
    bolt = player.find_tag('bolt')
    if bolt and opp_can_cast(bolt, total_mana, gs, caster=player):
        def bolt_priority(c):
            if c.card.tag == 'tamiyo': return 0
            if c.card.tag == 'bowm':   return 1
            if c.toughness <= 2:       return 2
            if c.toughness == 3:       return 3
            return 99
        # Bolt costs 1R; mana after paying = total_mana - 1 (for ward check)
        _bolt_mana_after = total_mana - 1
        candidates = [c for c in opponent.creatures
                      if bolt_priority(c) < 99 and _can_target(c, _bolt_mana_after)]
        target = min(candidates, key=bolt_priority) if candidates else None
        go_face = (target is None and opponent.life <= 9)
        player.remove_from_hand(bolt); player.add_to_grave(bolt)
        total_mana -= 1
        if target:
            opponent.remove_creature(target)
            log_fn(f"Lightning Bolt → kills {target.card.name}", True); update_goyf(gs)
        elif go_face:
            opponent.life -= 3
            log_fn(f"Lightning Bolt face — opponent at {opponent.life}")
            gs.check_life_totals()

    # Combat — Bowmasters holds back
    opp_has_blockers = len(opponent.creatures) > 0
    mardu_desperate  = player.life < CT.DESPERATE_LIFE
    attackers = []
    for c in player.creatures:
        if c.summoning_sick: continue
        if c.card.tag == 'bowm':
            if not opp_has_blockers or mardu_desperate: attackers.append(c)
        elif c.card.tag == 'tamiyo':
            pass
        else:
            attackers.append(c)
    combat_declare(player, opponent, gs, log_entries, attackers)

    # Ragavan trigger — oracle: "deals combat damage to a player"
    if 'ragavan' in getattr(gs, '_combat_unblocked_tags', set()) and opponent.library:
        stolen = opponent.library.pop(0)
        # Track treasure for the active player (whoever controls Ragavan)
        tkey = 'p1_treasure' if player is gs.p1 else 'p2_treasure'
        treasure = getattr(gs, tkey, 0) + 1
        setattr(gs, tkey, treasure)
        log_fn(f"★ Ragavan exiles {stolen.name} + creates Treasure ({treasure} total)", True)
        update_goyf(gs)
        if not stolen.is_land() and stolen.cmc <= treasure and stolen.cmc > 0:
            if player is gs.p1:
                gs.p1_treasure -= stolen.cmc
            else:
                gs.p2_treasure -= stolen.cmc
            if stolen.is_creature():
                player.put_creature_in_play(stolen)
                log_fn(f"  Ragavan casts exiled {stolen.name}")
            else:
                player.add_to_grave(stolen)
                log_fn(f"  Ragavan casts exiled {stolen.name} (spell)")


