"""
rules.py — MTG Comprehensive Rules Engine v2
All game rules live here. Nothing in engine.py bypasses these.

Fixes applied in v2:
  C1  CR 601.2f  — mana must be available before casting
  C2  CR 508.1f  — attacking creatures become tapped
  S1  CR 103.5   — London mulligan: draw 7, put N on bottom
  S2  CR 103.1   — first player determined by coin flip
  S3  CR 305.7   — Blood Moon: nonbasic lands become Mountains (no mana ability except R)
  S4  CR 305.6   — Back to Basics: nonbasic lands don't untap
  S5  CR 702.?   — Force of Negation free only on opponent's turn
  L1  STP        — controller of exiled creature gains life = its power (not doubled)
  L2  Dismember  — also costs 1 mana (Phyrexian {B/P}{B/P})
  L3  Dismember  — only kills if toughness - 5 <= 0
  L4  CR 510.1   — blocker deals damage back to attacker
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict
import random


# ─────────────────────────────────────────────
# Stack object types  CR 113.3
# ─────────────────────────────────────────────

class StackType(Enum):
    SPELL      = auto()   # cast from hand — counterable by FoW etc.
    TRIGGERED  = auto()   # "when/whenever/at" — NOT counterable by spell counters
    ACTIVATED  = auto()   # "cost: effect" — NOT counterable by spell counters


# ─────────────────────────────────────────────
# Card types  CR 300
# ─────────────────────────────────────────────

class CardType(Enum):
    CREATURE     = "creature"
    INSTANT      = "instant"
    SORCERY      = "sorcery"
    ARTIFACT     = "artifact"
    ENCHANTMENT  = "enchantment"
    PLANESWALKER = "planeswalker"
    LAND         = "land"


class LandType(Enum):
    BASIC   = "basic"
    FETCH   = "fetch"
    DUAL    = "dual"
    UTILITY = "utility"


# ─────────────────────────────────────────────
# Mana  CR 106
# ─────────────────────────────────────────────

COLORS = {'W', 'U', 'B', 'R', 'G', 'C'}

@dataclass
class ManaPool:
    """Tracks available mana by colour. Empties at end of each step/phase (CR 106.4)."""
    pool: Dict[str, int] = field(default_factory=lambda: {c: 0 for c in COLORS})

    def add(self, color: str, amount: int = 1):
        assert color in COLORS, f"Unknown color: {color}"
        self.pool[color] = self.pool.get(color, 0) + amount

    def spend(self, cost: Dict[str, int]) -> bool:
        """
        CR 601.2f — pay total cost. Returns True if successful, mutates pool.
        cost keys: color letters + 'generic' for any-color generic mana.
        """
        sim = dict(self.pool)
        # Colored first
        for color, amount in cost.items():
            if color == 'generic':
                continue
            if sim.get(color, 0) < amount:
                return False
            sim[color] -= amount
        # Generic from cheapest colors
        generic = cost.get('generic', 0)
        if sum(sim.values()) < generic:
            return False
        for color in ['C', 'G', 'R', 'B', 'W', 'U']:
            if generic <= 0:
                break
            take = min(sim.get(color, 0), generic)
            sim[color] = sim.get(color, 0) - take
            generic -= take
        if generic > 0:
            return False
        self.pool = sim
        return True

    def can_pay(self, cost: Dict[str, int]) -> bool:
        """Check affordability without spending."""
        tmp = ManaPool(pool=dict(self.pool))
        return tmp.spend(cost)

    def total(self) -> int:
        return sum(self.pool.values())

    def has(self, color: str, amount: int = 1) -> bool:
        return self.pool.get(color, 0) >= amount

    def reset(self):
        """End of step/phase — mana drains. CR 106.4."""
        self.pool = {c: 0 for c in COLORS}

    def __repr__(self):
        parts = [f"{v}{k}" for k, v in self.pool.items() if v > 0]
        return f"ManaPool({', '.join(parts) or 'empty'})"


# ─────────────────────────────────────────────
# Card definition
# ─────────────────────────────────────────────

@dataclass
class Card:
    name: str
    card_type: CardType
    cmc: int                          # printed CMC — used for Chalice, Fatal Push, Abrupt Decay
    mana_cost: Dict[str, int]         # {'U':1, 'generic':1} etc. — used for actual casting
    colors: Set[str] = field(default_factory=set)
    subtypes: Set[str] = field(default_factory=set)
    base_power: int = 0
    base_toughness: int = 0
    # Keywords
    flash: bool = False
    haste: bool = False
    flying: bool = False
    reach: bool = False
    trample: bool = False
    indestructible: bool = False
    deathtouch: bool = False             # CR 702.2: any damage dealt is lethal damage
    lifelink: bool = False               # CR 702.15: damage dealt also causes life gain
    vigilance: bool = False              # CR 702.20: attacking doesn't cause creature to tap
    delve: bool = False
    free_cast_if_blue: bool = False   # FoW/FoN alternate cost: exile blue card
    life_cost: int = 0                # Additional life paid on cast (CR 118.9): Thoughtseize=2, Snuff Out=4
    # Land
    land_type: Optional[LandType] = None
    produces: Set[str] = field(default_factory=set)
    is_basic: bool = False
    is_fetch: bool = False
    fetch_targets: Set[str] = field(default_factory=set)
    # Sim tags
    tag: str = ""
    gy_type: str = ""
    is_combo_piece: bool = False
    win_condition: bool = False

    # Strategic role properties — set in cards.py from oracle text, used in engine/interaction.
    # These replace tag-based frozenset membership checks with property-based decisions.
    lock_piece: bool = False       # locks the game state (Chalice, Bridge, Moon, Trinisphere, B2B)
    engine: bool = False           # ongoing value each turn if it sticks (Vial, Kaito, WST, Narset)
    is_removal: bool = False       # destroys/exiles permanents or deals damage (Push, STP, Terminus)
    is_mass_removal: bool = False  # removes multiple permanents (Terminus, Wrath, Deluge)
    draw_trigger: bool = False     # triggers when opponent draws (Bowmasters, Narset passive)
    tutor_power_max: int = -1      # tutors creatures with power <= this; -1 = not a tutor
    is_cantrip: bool = False        # draws a card when cast (Brainstorm, Ponder, Preordain)
    mana_ritual: bool = False      # produces mana beyond its cost when cast (Dark Rit, Petal, Tomb)
    etb_damage: int = 0            # deals N damage to caster's opponent on each spell cast (Eidolon)

    def is_land(self): return self.card_type == CardType.LAND
    def is_creature(self): return self.card_type == CardType.CREATURE
    def is_spell(self):
        return self.card_type in (CardType.INSTANT, CardType.SORCERY,
            CardType.ARTIFACT, CardType.ENCHANTMENT,
            CardType.PLANESWALKER, CardType.CREATURE)

    def __repr__(self): return f"Card({self.name})"


# ─────────────────────────────────────────────
# Permanent
# ─────────────────────────────────────────────

@dataclass
class Permanent:
    card: Card
    controller: str
    tapped: bool = False
    summoning_sick: bool = True   # CR 302.6
    damage_marked: int = 0
    counters: Dict[str, int] = field(default_factory=dict)
    power_mod: int = 0
    toughness_mod: int = 0

    @property
    def name(self): return self.card.name
    @property
    def power(self): return max(0, self.card.base_power + self.power_mod)
    @property
    def toughness(self): return max(0, self.card.base_toughness + self.toughness_mod)
    @property
    def cmc(self): return self.card.cmc

    def can_attack(self) -> bool:
        """CR 508.1 — not tapped, no summoning sickness (unless haste)."""
        if self.tapped: return False
        if self.summoning_sick and not self.card.haste: return False
        return True

    def tap(self): self.tapped = True
    def untap(self): self.tapped = False
    def clear_summoning_sickness(self): self.summoning_sick = False

    def is_destroyed(self) -> bool:
        if self.card.indestructible: return False
        return self.damage_marked >= self.toughness

    def __repr__(self):
        sick = "[sick]" if self.summoning_sick else ""
        tap = "[T]" if self.tapped else ""
        if self.card.is_creature():
            return f"Perm({self.name} {self.power}/{self.toughness}{sick}{tap})"
        return f"Perm({self.name}{tap})"


# ─────────────────────────────────────────────
# Land permanent
# ─────────────────────────────────────────────

@dataclass
class LandPermanent:
    card: Card
    controller: str
    tapped: bool = False
    blood_moon_active: bool = False   # S3: Blood Moon makes nonbasics into Mountains
    b2b_active: bool = False          # S4: Back to Basics prevents nonbasic untap

    @property
    def name(self): return self.card.name
    @property
    def cmc(self): return self.card.cmc
    @property
    def is_basic(self): return self.card.is_basic
    @property
    def is_nonbasic(self): return not self.card.is_basic
    @property
    def is_fetch(self): return self.card.is_fetch

    def effective_produces(self) -> Set[str]:
        """
        CR 305.7 — Blood Moon: nonbasic lands become Mountains (produce R only).
        CR 305.6 — Back to Basics: nonbasic lands lose all abilities (produce nothing).
        B2B takes precedence over Blood Moon (more restrictive).
        """
        if self.is_fetch:
            return set()  # fetch lands never produce mana
        if self.b2b_active and self.is_nonbasic:
            return set()  # B2B: nonbasics lose all abilities including mana
        if self.blood_moon_active and self.is_nonbasic:
            return {'R'}  # Blood Moon: Mountains produce R
        return self.card.produces

    def tap_for_mana(self, pool: ManaPool, color: str) -> bool:
        if self.tapped: return False
        if self.is_fetch: return False
        effective = self.effective_produces()
        if color not in effective: return False
        self.tapped = True
        pool.add(color)
        return True

    def can_untap(self) -> bool:
        """S4 — Back to Basics: nonbasic lands don't untap."""
        if self.b2b_active and self.is_nonbasic:
            return False
        return True

    def untap(self):
        if self.can_untap():
            self.tapped = False

    def can_be_wastelanded(self) -> bool:
        return self.is_nonbasic

    def activate_fetch(self, library: List[Card], graveyard: List[Card]) -> Optional['LandPermanent']:
        """CR 701.20 — search library for land with matching subtype, put onto battlefield.
        Oracle: "put it onto the battlefield, then shuffle" — NO tapped clause. Enters untapped."""
        targets = [c for c in library if c.is_land()
                   and self.card.fetch_targets.intersection(c.subtypes)]
        if not targets:
            return None
        # Prefer untapped dual over basic (pilot choice)
        chosen = (next((c for c in targets if c.land_type and c.land_type.value == 'dual'), None) or targets[0])
        library.remove(chosen)
        graveyard.append(self.card)
        return LandPermanent(card=chosen, controller=self.controller, tapped=False)  # enters untapped — oracle has no 'tapped' clause

    def __repr__(self):
        return f"Land({self.name}{'[T]' if self.tapped else ''})"


# ─────────────────────────────────────────────
# Stack object  CR 112-113
# ─────────────────────────────────────────────

@dataclass
class StackObject:
    name: str
    stack_type: StackType
    controller: str
    source_card: Optional[Card] = None
    cmc: int = 0
    card_type: Optional[CardType] = None
    colors: Set[str] = field(default_factory=set)
    trigger_source: str = ""
    targets: list = field(default_factory=list)

    def is_counterable_by_spell(self) -> bool:
        """
        CR 113.9 — Activated and triggered abilities can't be countered by
        effects that counter only spells. Only StackType.SPELL is counterable.
        """
        return self.stack_type == StackType.SPELL

    def __repr__(self):
        return f"Stack({self.name} [{self.stack_type.name}])"


# ─────────────────────────────────────────────
# MTGRules — all game logic as static methods
# ─────────────────────────────────────────────

class MTGRules:

    # ── Mana / casting  CR 601.2 ──────────────

    @staticmethod
    def can_cast(card: Card, pool: ManaPool, graveyard_spell_count: int = 0,
                 is_free_blue: bool = False) -> bool:
        """
        CR 601.2f — can the player actually pay the mana cost?
        is_free_blue: True if casting via alternate cost (FoW, FoN, Force of Vigor style).
        delve: each spell exiled from GY pays 1 generic.
        """
        if is_free_blue:
            return True  # alternate cost path — no mana required
        cost = dict(card.mana_cost)
        if card.delve and graveyard_spell_count > 0:
            # Delve: exile spells to reduce generic cost
            reduce = min(graveyard_spell_count, cost.get('generic', 0))
            cost['generic'] = max(0, cost.get('generic', 0) - reduce)
        return pool.can_pay(cost)

    @staticmethod
    def pay_cost(card: Card, pool: ManaPool, graveyard: List[Card],
                 is_free_blue: bool = False) -> bool:
        """
        Deduct mana from pool. Returns False if can't pay (shouldn't happen if
        can_cast() was checked first). Handles delve exile.
        """
        if is_free_blue:
            return True
        cost = dict(card.mana_cost)
        spells_in_gy = [c for c in graveyard
                        if c.card_type in (CardType.INSTANT, CardType.SORCERY)]
        if card.delve and spells_in_gy:
            reduce = min(len(spells_in_gy), cost.get('generic', 0))
            for i in range(reduce):
                graveyard.remove(spells_in_gy[i])
            cost['generic'] = max(0, cost.get('generic', 0) - reduce)
        return pool.spend(cost)

    # ── Countering  CR 113.9 ──────────────────

    @staticmethod
    def force_of_will_can_counter(target: StackObject, hand: List[Card]) -> bool:
        """FoW: exile a blue card, counter target spell. CR 113.9."""
        if not target.is_counterable_by_spell(): return False
        has_fow = any(c.tag == 'fow' for c in hand)
        has_blue_other = any(c.tag != 'fow' and 'U' in c.colors for c in hand)
        return has_fow and has_blue_other

    @staticmethod
    def force_of_will_use(target: StackObject, hand: List[Card], log: List[str]) -> bool:
        if not MTGRules.force_of_will_can_counter(target, hand): return False
        fow = next(c for c in hand if c.tag == 'fow')
        # Pitch priority: cantrips first (easiest to replace), never FoN/Murktide.
        # Among equal-priority, prefer pitching duplicates.
        blue_cards = [c for c in hand if c.tag != 'fow' and 'U' in c.colors]
        pitch_priority = {'bs':0,'ponder':0,'daze':1,'fluster':2,'borrow':4,'strix':5,'tamiyo':6,'fon':8,'murk':9}
        from collections import Counter as _C
        _tc = _C(c.tag for c in hand)
        blue = min(blue_cards, key=lambda c: (pitch_priority.get(c.tag, 5), -_tc[c.tag]))
        hand.remove(fow)
        hand.remove(blue)
        log.append(f"Force of Will counters {target.name} (exiles {blue.name})")
        return True

    @staticmethod
    def force_of_negation_can_counter(target: StackObject, hand: List[Card],
                                       is_opponents_turn: bool) -> bool:
        """
        FoN — free only on OPPONENT's turn (S5 fix).
        Counters noncreature spells only.
        On your own turn it costs {1}{U}{U} — we treat that as unavailable
        since the sim doesn't track blue mana separately for FoN.
        """
        if not target.is_counterable_by_spell(): return False
        if target.card_type == CardType.CREATURE: return False
        if not any(c.tag == 'fon' for c in hand): return False
        return is_opponents_turn  # free only on opp's turn

    @staticmethod
    def force_of_negation_use(target: StackObject, hand: List[Card], log: List[str],
                               is_opponents_turn: bool) -> bool:
        if not MTGRules.force_of_negation_can_counter(target, hand, is_opponents_turn):
            return False
        fon = next(c for c in hand if c.tag == 'fon')
        # Alternate cost (CR 117.9d): exile FoN + exile another blue card from hand.
        # Check for a blue pitch card beyond FoN itself.
        blue_tags = {'fow','bs','ponder','murk','borrow','tamiyo','fluster','fon','fov','vos'}
        blue_pitch = next((c for c in hand if c is not fon and
                           c.tag in blue_tags), None)
        if not blue_pitch:
            return False  # no blue card to pitch — FoN cannot be cast for free
        hand.remove(fon)
        hand.remove(blue_pitch)
        log.append(f"Force of Negation counters {target.name} (free — opp's turn, exiles {blue_pitch.name})")
        return True

    @staticmethod
    def flusterstorm_can_counter(target: StackObject, hand: List[Card]) -> bool:
        if not target.is_counterable_by_spell(): return False
        if target.card_type not in (CardType.INSTANT, CardType.SORCERY): return False
        return any(c.tag == 'fluster' for c in hand)

    @staticmethod
    def flusterstorm_use(target: StackObject, hand: List[Card], log: List[str]) -> bool:
        if not MTGRules.flusterstorm_can_counter(target, hand): return False
        fl = next(c for c in hand if c.tag == 'fluster')
        hand.remove(fl)
        log.append(f"Flusterstorm counters {target.name}")
        return True

    @staticmethod
    def daze_can_counter(target: StackObject, hand: List[Card],
                         lands: List[LandPermanent]) -> bool:
        """
        Daze: return an Island you control, counter target spell unless opp pays {1}.
        Modelled as: we don't let opp pay — they counter it. Must have untapped
        Island-subtype land to bounce.
        """
        if not target.is_counterable_by_spell(): return False
        if not any(c.tag == 'daze' for c in hand): return False
        # Need an untapped land with Island subtype (produces U in our model)
        return any(not l.tapped and 'U' in l.effective_produces() for l in lands)

    @staticmethod
    def daze_use(target: StackObject, hand: List[Card],
                 lands: List[LandPermanent], log: List[str]) -> bool:
        if not MTGRules.daze_can_counter(target, hand, lands): return False
        daze_card = next(c for c in hand if c.tag == 'daze')
        blue_land = next((l for l in lands
                          if not l.tapped and 'U' in l.effective_produces()), None)
        if not blue_land: return False
        hand.remove(daze_card)
        lands.remove(blue_land)
        hand.append(blue_land.card)
        log.append(f"Daze counters {target.name} — {blue_land.name} returned to hand")
        return True

    @staticmethod
    def best_counter(target: StackObject, hand: List[Card],
                     lands: List[LandPermanent], log: List[str],
                     is_opponents_turn: bool = True) -> bool:
        """Try all available counters. Returns True if countered."""
        if MTGRules.force_of_will_use(target, hand, log): return True
        if MTGRules.force_of_negation_use(target, hand, log, is_opponents_turn): return True
        if MTGRules.flusterstorm_use(target, hand, log): return True
        if MTGRules.daze_use(target, hand, lands, log): return True
        return False

    # ── Wasteland / Marit Lage ────────────────

    @staticmethod
    def wasteland_can_target(land: LandPermanent) -> bool:
        """Wasteland destroys target nonbasic land. Can't target itself."""
        if land.card.tag == 'wl': return False  # can't target another Wasteland (or itself)
        return land.is_nonbasic

    @staticmethod
    def wasteland_is_counterable() -> bool:
        return False  # activated ability — CR 113.9

    @staticmethod
    def marit_lage_is_counterable() -> bool:
        return False  # triggered ability — CR 113.9

    @staticmethod
    def marit_lage_stack_type() -> StackType:
        return StackType.TRIGGERED

    # ── Fatal Push  CR 701.7 ──────────────────

    @staticmethod
    def fatal_push_valid_target(permanent: Permanent, revolt: bool) -> bool:
        """CMC ≤ 2; with revolt CMC ≤ 4. Power is irrelevant."""
        if permanent.card.card_type != CardType.CREATURE: return False
        threshold = 4 if revolt else 2
        return permanent.cmc <= threshold

    # ── Abrupt Decay ──────────────────────────

    @staticmethod
    def abrupt_decay_valid_target(permanent: Permanent) -> bool:
        """Destroys target permanent with CMC 3 or less. Cannot be countered."""
        return permanent.cmc <= 3

    # ── Chalice of the Void ───────────────────

    @staticmethod
    def chalice_counters_spell(spell: StackObject, chalice_x: int) -> bool:
        """Uses printed CMC — not the cost paid. CR 601.2f."""
        if spell.stack_type != StackType.SPELL: return False
        return spell.cmc == chalice_x

    # ── Ensnaring Bridge  CR 508.1 ────────────

    @staticmethod
    def bridge_prevents_attack(attacker: Permanent, hand_size: int) -> bool:
        """Creatures with power > number of cards in ATTACKER's hand can't attack."""
        return attacker.power > hand_size

    # ── Summoning sickness  CR 302.6 ─────────

    @staticmethod
    def has_summoning_sickness(permanent: Permanent) -> bool:
        if permanent.card.haste: return False
        return permanent.summoning_sick

    @staticmethod
    def can_attack(attacker: Permanent) -> bool:
        """CR 508.1 — creature can attack if untapped and no summoning sickness."""
        if attacker.card.card_type != CardType.CREATURE: return False
        if attacker.tapped: return False
        if MTGRules.has_summoning_sickness(attacker): return False
        return True

    # ── CR 508.1f — attackers tap ─────────────

    @staticmethod
    def tap_attacker(attacker: Permanent):
        """CR 508.1f: as part of declaring attackers, each attacker taps."""
        attacker.tap()

    # ── CR 510.1 — combat damage (two-way) ───

    @staticmethod
    def assign_combat_damage(attackers: List[Permanent],
                              blocker: Optional[Permanent]) -> Dict:
        """
        CR 510.1 — each attacking/blocking creature assigns damage equal to its power.
        CR 702.17 — trample: attacker assigns lethal damage to blocker, excess to player.
        Returns dict with: damage_to_player, damage_to_blocker, damage_to_attacker, blocked_attacker.
        """
        total_attack_power = sum(a.power for a in attackers)
        if blocker is None:
            return {
                'damage_to_player': total_attack_power,
                'damage_to_blocker': 0,
                'damage_to_attacker': 0,
                'blocked_attacker': None,
            }
        # Blocker blocks the first (or largest) attacker
        blocked = max(attackers, key=lambda a: a.power) if attackers else None
        unblocked_power = sum(a.power for a in attackers if a is not blocked)
        blocked_power = blocked.power if blocked else 0

        # CR 702.17 trample: lethal damage to blocker = min(power, blocker.toughness)
        # Excess spills through to defending player
        if blocked and blocked.card.trample:
            lethal_to_blocker = blocker.toughness  # minimum to kill blocker
            trample_excess = max(0, blocked_power - lethal_to_blocker)
            damage_to_blocker = blocked_power         # still deals full power to blocker
            damage_to_player = unblocked_power + trample_excess
        else:
            damage_to_blocker = blocked_power
            damage_to_player = unblocked_power

        return {
            'damage_to_player': damage_to_player,
            'damage_to_blocker': damage_to_blocker,
            'damage_to_attacker': blocker.power if blocked else 0,
            'blocked_attacker': blocked,
        }

    # ── Tarmogoyf  CR 208.2a ──────────────────

    @staticmethod
    def tarmogoyf_pt(b_graveyard: List[Card], o_graveyard: List[Card]) -> tuple:
        """P/T = card types in ALL graveyards / that + 1."""
        type_set = set()
        for card in b_graveyard + o_graveyard:
            if card.gy_type:
                type_set.add(card.gy_type)
        p = len(type_set)
        return (p, p + 1)

    # ── Bowmasters  CR 603 ────────────────────

    @staticmethod
    def bowmasters_trigger_count(cards_drawn: int) -> int:
        """One trigger per draw event. Brainstorm = 3 draws = 3 triggers."""
        return cards_drawn

    # ── Draw events ───────────────────────────

    @staticmethod
    def brainstorm_draws() -> int: return 3
    @staticmethod
    def brainstorm_puts_back() -> int: return 2
    @staticmethod
    def ponder_draws() -> int: return 1

    # ── Fetch land  CR 701.20 ─────────────────

    @staticmethod
    def fetch_produces_mana() -> bool: return False
    @staticmethod
    def fetch_costs_life() -> int: return 1

    # ── Swords to Plowshares  (L1 fix) ───────

    @staticmethod
    def stp_life_gain(creature: Permanent) -> int:
        """
        STP: exile target creature, its controller gains life equal to its power.
        CR 118.4 — life gain goes to the CONTROLLER of the exiled creature.
        Returns the amount. The calling code must add it to the right player.
        """
        return creature.power

    # ── Dismember  (L2/L3 fix) ────────────────

    @staticmethod
    def dismember_can_cast(pool: ManaPool) -> bool:
        """
        Dismember {1}{B/P}{B/P}: pay 1 generic + 4 life (all Phyrexian),
        or 1B + 2 life, or 1BB + 0 life.
        Simplification: we model it as pay-4-life variant which needs 1 mana.
        """
        return pool.total() >= 1  # needs at least 1 mana of any color

    @staticmethod
    def dismember_kills(creature: Permanent) -> bool:
        """
        Dismember gives -5/-5. Creature dies only if toughness - 5 <= 0 (L3 fix).
        Indestructible creatures can still be killed by -5/-5 toughness reduction.
        """
        new_toughness = creature.toughness - 5
        return new_toughness <= 0  # goes to graveyard due to 0/negative toughness (CR 704.5f)

    # ── State-based actions  CR 704 ──────────

    @staticmethod
    def check_lethal_damage(permanent: Permanent, deathtouch_source: bool = False) -> bool:
        """CR 704.5g — lethal damage. Deathtouch (CR 702.2e) makes any damage lethal."""
        if permanent.card.indestructible: return False
        if deathtouch_source and permanent.damage_marked > 0: return True
        return permanent.damage_marked >= permanent.toughness

    @staticmethod
    def check_zero_toughness(permanent: Permanent) -> bool:
        return permanent.toughness <= 0
