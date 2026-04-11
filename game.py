"""
game.py — Game state, player state, turn structure.

v2 fixes:
  S1  CR 103.5   — London mulligan: draw 7, put N on bottom (see sim.py)
  S2  CR 103.1   — first player coin flip (see sim.py run_game)
  S3  CR 305.7   — Blood Moon applied in untap (LandPermanent.effective_produces)
  S4  CR 305.6   — Back to Basics applied in untap (LandPermanent.can_untap)
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from rules import (Card, CardType, Permanent, LandPermanent, ManaPool,
                   StackObject, StackType, MTGRules)


@dataclass
class LogEntry:
    turn: int
    player: str
    phase: str
    message: str
    is_key_event: bool = False
    def __str__(self):
        marker = "★ " if self.is_key_event else "  "
        return f"T{self.turn} [{self.player.upper()}][{self.phase}] {marker}{self.message}"


@dataclass
class PlayerState:
    name: str
    life: int = 20
    hand: List[Card] = field(default_factory=list)
    library: List[Card] = field(default_factory=list)
    graveyard: List[Card] = field(default_factory=list)
    exile: List[Card] = field(default_factory=list)
    lands: List[LandPermanent] = field(default_factory=list)
    creatures: List[Permanent] = field(default_factory=list)
    artifacts: List[Permanent] = field(default_factory=list)
    enchantments: List[Permanent] = field(default_factory=list)
    planeswalkers: List[Permanent] = field(default_factory=list)
    mana: ManaPool = field(default_factory=ManaPool)
    land_played_this_turn: bool = False
    revolt_this_turn: bool = False
    draws_this_turn: int = 0  # track for Tamiyo flip (3rd draw) and Bowmasters
    spells_cast_this_turn: int = 0  # for Mindbreak Trap free condition
    opp_cast_blue_black_this_turn: bool = False  # for Veil of Summer conditional draw
    leyline_exile: bool = False  # if True, cards go to exile instead of GY (Leyline of the Void)

    @property
    def all_permanents(self):
        return self.creatures + self.artifacts + self.enchantments + self.planeswalkers

    def draw(self, n: int = 1, is_draw_step: bool = False) -> List[Card]:
        """Draw n cards. is_draw_step=True exempts the first card from Bowmasters (oracle).
        Narset, Parter of Veils: if opp controls Narset, BUG can only draw their first card
        each turn — subsequent draws are replaced by nothing (CR 614)."""
        drawn = []
        for i in range(n):
            if self.library:
                # Narset lock: if this player already drew this turn and Narset is active,
                # skip additional draws (replacement effect — card stays in library)
                if self.draws_this_turn >= 1 and getattr(self, '_narset_lock', False):
                    break  # subsequent draws don't happen
                card = self.library.pop(0)
                self.hand.append(card)
                drawn.append(card)
                self.draws_this_turn += 1
        return drawn

    def add_to_grave(self, card: Card):
        if self.leyline_exile:
            self.exile.append(card)
        else:
            self.graveyard.append(card)

    def tap_lands_for_mana(self):
        """Tap all available lands for their best mana color."""
        for land in self.lands:
            if not land.tapped and not land.is_fetch:
                effective = land.effective_produces()
                for color in ['U', 'B', 'G', 'R', 'C', 'W']:
                    if color in effective:
                        land.tap_for_mana(self.mana, color)
                        break

    def available_mana_count(self) -> int:
        """Count untapped mana-producing lands (for quick checks)."""
        count = 0
        for l in self.lands:
            if not l.tapped and not l.is_fetch and l.effective_produces():
                count += 1
        return count

    def untap_all(self):
        """Untap step — lands and permanents. B2B/Blood Moon applied via LandPermanent."""
        for land in self.lands:
            land.untap()  # LandPermanent.untap() checks can_untap() for B2B
        for perm in self.all_permanents:
            perm.untap()
        self.land_played_this_turn = False
        self.draws_this_turn = 0
        self.spells_cast_this_turn = 0
        self.opp_cast_blue_black_this_turn = False
        self.mana.reset()

    def clear_summoning_sickness(self):
        for c in self.creatures:
            c.clear_summoning_sickness()

    def find_tag(self, tag: str) -> Optional[Card]:
        return next((c for c in self.hand if c.tag == tag), None)

    def find_any(self, condition) -> Optional[Card]:
        return next((c for c in self.hand if condition(c)), None)

    def remove_from_hand(self, card: Card):
        if card in self.hand:
            self.hand.remove(card)

    def cast_spell(self, card: Card, log_fn=None) -> bool:
        """Move card hand→GY and pay life_cost (CR 118.9, CR 601.2h).
        Returns True. Callers handle mana budget deduction separately.
        log_fn: optional callable(msg) — emits a life-payment log line.
        """
        self.remove_from_hand(card)
        self.add_to_grave(card)
        if card.life_cost > 0:
            self.life -= card.life_cost
            if log_fn:
                log_fn(f"{card.name} (−{card.life_cost} life, {self.life})")
        return True

    def play_land(self, card: Card) -> Optional[LandPermanent]:
        if self.land_played_this_turn: return None
        if card not in self.hand or not card.is_land(): return None
        self.hand.remove(card)
        # CR 305.3 — some lands enter tapped unless a condition is met.
        # Undercity Sewers and similar: enter tapped unless controller controls 2+ other lands.
        enters_tapped = False
        if getattr(card, 'enters_tapped_unless_two_others', False):
            enters_tapped = len(self.lands) < 2
        perm = LandPermanent(card=card, controller=self.name, tapped=enters_tapped)
        self.lands.append(perm)
        self.land_played_this_turn = True
        return perm

    def use_fetch(self, fetch_perm: LandPermanent) -> Optional[LandPermanent]:
        """Sacrifice fetch: pay 1 life, search library. CR 701.20"""
        if fetch_perm not in self.lands: return None
        if fetch_perm.tapped: return None
        # CR 704.5a — if a player has 0 or less life, they lose. Don't crack a fetch
        # that would reduce life to 0 (suicidal fetch).
        if self.life - MTGRules.fetch_costs_life() <= 0: return None
        self.lands.remove(fetch_perm)
        self.add_to_grave(fetch_perm.card)
        self.life -= MTGRules.fetch_costs_life()
        self.revolt_this_turn = True
        result = fetch_perm.activate_fetch(self.library, self.graveyard)
        if result:
            self.lands.append(result)
        return result

    def put_creature_in_play(self, card: Card, tapped: bool = False) -> Permanent:
        perm = Permanent(card=card, controller=self.name,
                         tapped=tapped,
                         summoning_sick=not card.haste)
        self.creatures.append(perm)
        return perm

    def remove_creature(self, perm: Permanent, to_exile: bool = False) -> None:
        """Remove a creature from the battlefield — centralises revolt + GY routing.
        CR 700.4: 'destroy' moves to GY; exile moves to exile zone.
        Always sets revolt_this_turn (a permanent left the battlefield).
        """
        if perm not in self.creatures:
            return
        self.creatures.remove(perm)
        if to_exile:
            self.exile.append(perm.card)
        else:
            self.add_to_grave(perm.card)
        self.revolt_this_turn = True  # CR 702.29: any permanent leaving = revolt

    def put_artifact_in_play(self, card: Card) -> Permanent:
        perm = Permanent(card=card, controller=self.name, summoning_sick=False)
        self.artifacts.append(perm)
        return perm

    def put_enchantment_in_play(self, card: Card) -> Permanent:
        perm = Permanent(card=card, controller=self.name, summoning_sick=False)
        self.enchantments.append(perm)
        return perm

    def put_planeswalker_in_play(self, card: Card) -> Permanent:
        perm = Permanent(card=card, controller=self.name, summoning_sick=False)
        self.planeswalkers.append(perm)
        return perm

    def spell_count_in_graveyard(self) -> int:
        return sum(1 for c in self.graveyard
                   if c.card_type in (CardType.INSTANT, CardType.SORCERY))

    def apply_blood_moon(self, active: bool):
        """S3: toggle Blood Moon effect on all controlled lands."""
        for land in self.lands:
            land.blood_moon_active = active

    def apply_b2b(self, active: bool):
        """S4: toggle Back to Basics effect on all controlled lands."""
        for land in self.lands:
            land.b2b_active = active


@dataclass
class GameState:
    p1: PlayerState                   # player 1 (protagonist)
    p2: PlayerState                   # player 2 (antagonist)
    turn: int = 1
    active_player: str = 'b'
    log: List[LogEntry] = field(default_factory=list)
    game_over: bool = False
    winner: Optional[str] = None      # 'p1' or 'p2'
    win_reason: str = ''
    kill_turn: Optional[int] = None
    # Board flags
    chalice_x: Optional[int] = None
    bridge_on_board: bool = False
    moon_on_board: bool = False       # Blood Moon
    b2b_on_board: bool = False        # Back to Basics
    # P1 tracking — bowmasters_on_board and orc_army are computed properties (see below)
    leyline_active: bool = False      # Leyline of the Void in play pre-game
    trinisphere_active: bool = False  # Trinisphere — all spells cost ≥ {3}
    eidolon_active: bool = False      # Eidolon of the Great Revel — 2 dmg to p1 per CMC≥2 spell cast
    tamiyo_flipped: bool = False
    combat_this_turn: bool = False    # Set by combat_declare, reset at turn start
    p1_goes_first: bool = True        # S2: set by coin flip in run_game
    vial_counters: int = 0            # Aether Vial counter tracker
    _vial_entered_last_turn: bool = False  # prevents tick on entry turn
    matchup: str = ''                 # current matchup name for strategy-aware decisions
    p1_deck: str = ''                 # protagonist deck key
    p2_deck: str = ''                 # antagonist deck key
    # Kept for Storm/Oops spell-count tracking
    pending_bauble_draws: int = 0
    # Trace mode: when True, turn functions emit phase markers and state snapshots
    trace: bool = False

    # ── Computed properties — always derived from board state, never manually synced ──

    @property
    def bowmasters_on_board(self) -> bool:
        """True iff ANY player controls at least one Orcish Bowmasters permanent."""
        return any(c.card.tag == 'bowm'
                   for c in self.p1.creatures + self.p2.creatures)

    @bowmasters_on_board.setter
    def bowmasters_on_board(self, value):
        pass  # silently ignore manual sets — truth is the board

    @property
    def orc_army(self):
        """The Orc Army token permanent, or None. Checks both players."""
        return next((c for c in self.p1.creatures + self.p2.creatures
                     if c.card.tag == 'orc_army'), None)

    @orc_army.setter
    def orc_army(self, value):
        pass  # silently ignore — the creature list is the truth

    @property
    def shepherd_in_play(self) -> bool:
        """True iff Allosaurus Shepherd is in play anywhere — green spells uncounterable."""
        return any(c.card.tag == 'shepherd' for c in self.p1.creatures + self.p2.creatures)
    @shepherd_in_play.setter
    def shepherd_in_play(self, value):
        pass  # derived from board

    @property
    def thalia_on_board(self) -> bool:
        """True iff ANY player controls Thalia — noncreature spells cost +1 (CR 613)."""
        return any(c.card.tag == 'thalia'
                   for c in self.p1.creatures + self.p2.creatures)

    @thalia_on_board.setter
    def thalia_on_board(self, value):
        pass  # silently ignore — derived from board

    @property
    def narset_active(self) -> bool:
        """True iff ANY player controls Narset — opponents can't draw extra cards.
        Note: Narset's draw lock is applied per-player in play_turn via _narset_lock."""
        p1_narset = any(c.card.tag == 'narset' for c in self.p1.planeswalkers) if hasattr(self.p1, 'planeswalkers') else False
        p2_narset = any(c.card.tag == 'narset' for c in self.p2.planeswalkers) if hasattr(self.p2, 'planeswalkers') else False
        return p1_narset or p2_narset

    def log_event(self, player: str, phase: str, message: str, key: bool = False):
        self.log.append(LogEntry(self.turn, player, phase, message, key))

    def check_life_totals(self):
        if self.p1.life <= 0 and not self.game_over:
            self.game_over = True
            self.winner = 'p2'
            self.win_reason = f'BUG life reaches {self.p1.life} on turn {self.turn}'
        if self.p2.life <= 0 and not self.game_over:
            self.game_over = True
            self.winner = 'p1'
            self.win_reason = f'Opp life reaches {self.p2.life} on turn {self.turn}'
            self.kill_turn = self.turn

    def spell_blocked_by_chalice(self, spell_cmc: int) -> bool:
        if self.chalice_x is None: return False
        return spell_cmc == self.chalice_x

    def get_attackers(self, player: PlayerState) -> List[Permanent]:
        """
        CR 508.1 — declare attackers. Applies general combat EV assessment:
        attack only when expected value is positive. Mirrors real Legacy play.

        EV(attack) > 0 when:
          A. No blockers — free damage, always attack.
          B. Unblocked path — flying attacker vs no flying/reach defenders.
          C. Favorable trade — attacker kills blocker AND survives.
          D. Lethal or near-lethal pressure — push through regardless.

        EV(attack) <= 0 when:
          E. Losing trade — attacker dies without killing blocker.
          F. Even trade while at board parity or behind — reinforces opp lead.
          G. Deathtouch blocker — attacker dies regardless of power.
        """
        defender   = self.p2 if player == self.p1 else self.p1
        # Bridge uses defender's hand size (Bridge controller = defender)
        hand_size  = len(defender.hand)
        blockers   = defender.creatures
        has_blockers = bool(blockers)
        board_lead = len(player.creatures) > len(blockers)
        board_behind = len(player.creatures) < len(blockers)

        # Lethal pressure: opp at or near lethal — attack regardless
        def_player = defender if player == self.p1 else player
        near_lethal = def_player.life <= sum(
            c.power for c in player.creatures if MTGRules.can_attack(c)
        ) * 0.75  # within striking distance

        def best_blocker_for(attacker: 'Permanent') -> 'Optional[Permanent]':
            """Find the best legal blocker the defender would assign to this attacker."""
            can_block = []
            for b in blockers:
                # Flying/reach can block anything; ground only blocks ground
                if b.card.flying or getattr(b.card, 'reach', False):
                    can_block.append(b)
                elif not attacker.card.flying:
                    can_block.append(b)
                # Brazen Borrower can only block flying
                elif b.card.tag == 'borrow' and attacker.card.flying:
                    can_block.append(b)
            if not can_block:
                return None
            # Defender picks blocker that kills the attacker if possible,
            # otherwise the one with highest toughness
            killers = [b for b in can_block if b.power >= attacker.toughness or b.card.deathtouch]
            return killers[0] if killers else max(can_block, key=lambda b: b.toughness)

        def combat_ev(attacker: 'Permanent') -> str:
            """
            Returns one of: 'attack', 'skip', 'borderline'
            'attack'     — clearly positive EV
            'skip'       — clearly negative EV
            'borderline' — context-dependent (board state resolves it)
            """
            blocker = best_blocker_for(attacker)

            # A. No blocker → unblocked damage, always attack
            if blocker is None:
                return 'attack'

            # Compute trade outcome
            # Deathtouch: any damage from a deathtouch source is lethal
            attacker_dies = (blocker.power >= attacker.toughness or
                             (blocker.card.deathtouch and blocker.power > 0))
            blocker_dies  = (attacker.power >= blocker.toughness or
                             (attacker.card.deathtouch and attacker.power > 0))

            # B. Unblocked path: flying attacker, all blockers are ground
            if attacker.card.flying and not any(
                b.card.flying or getattr(b.card, 'reach', False) for b in blockers
            ):
                return 'attack'  # flies over everything

            # C. Favorable trade: attacker kills blocker AND attacker survives
            if blocker_dies and not attacker_dies:
                return 'attack'

            # E. Losing trade: attacker dies, blocker survives
            if attacker_dies and not blocker_dies:
                return 'skip'

            # G. Deathtouch blocker: attacker dies regardless of its power
            # (even if blocker also dies it may not be worth trading a finisher)
            if blocker.card.deathtouch and attacker_dies:
                # High-value attacker (finisher/engine) into deathtouch = bad
                is_high_value = attacker.power >= 3 or attacker.card.tag in (
                    'bowm', 'wst', 'murk', 'tamiyo')
                if is_high_value:
                    return 'skip'
                return 'borderline'  # cheap creature into deathtouch is borderline

            # F. Even trade (both die):
            if attacker_dies and blocker_dies:
                return 'borderline'

            # Both survive: attacking deals no permanent board advantage
            # but does chip damage — attack if ahead or applying pressure
            return 'borderline'

        # WST guard: Wan Shi Tong has flying + vigilance — it blocks AND draws cards.
        # BUG should not trade valuable ground attackers into a flying blocker that
        # untaps (vigilance) and draws a card each fetch crack. Skip attacking unless
        # near lethal or attacker has flying (can't be blocked by WST if... wait, WST flies).
        # Real play: hold threats and race with Bowmasters pings instead.
        wst_blocking = next((c for c in blockers if c.card.tag == 'wst'), None)

        can_attack = []
        for c in player.creatures:
            if not MTGRules.can_attack(c): continue
            if self.bridge_on_board and MTGRules.bridge_prevents_attack(c, hand_size): continue

            # Rule: never send 0-power into defended board (deals 0, may die)
            if has_blockers and c.power == 0:
                continue

            # WST guard: skip ground attackers into WST unless near lethal.
            # WST is flying — ground creatures can't reach it anyway. But WST CAN block
            # ground creatures, so we need to check if WST would be the assigned blocker.
            if wst_blocking and not near_lethal:
                assigned = best_blocker_for(c)
                if assigned and assigned.card.tag == 'wst':
                    # WST blocks, survives (high toughness), draws a card — bad EV
                    continue

            verdict = combat_ev(c)

            if verdict == 'attack':
                can_attack.append(c)
            elif verdict == 'skip':
                pass  # hold back
            else:  # borderline — context resolves it
                # Attack if: near lethal, board lead, or trample pushes damage through
                if near_lethal or board_lead or c.card.trample:
                    can_attack.append(c)
                elif board_behind:
                    pass  # hold back when behind and trade is unclear
                else:
                    # Parity — attack with the even trade (tempo deck, keep pressing)
                    can_attack.append(c)

        return can_attack

    def state_based_actions(self):
        """CR 704 - lethal damage, 0-toughness, and legend rule."""
        for player in [self.p1, self.p2]:
            # CR 704.5a/b - lethal damage and 0-toughness
            dead = [c for c in player.creatures
                    if MTGRules.check_lethal_damage(c) or MTGRules.check_zero_toughness(c)]
            for c in dead:
                player.remove_creature(c)  # handles revolt + GY automatically

            # CR 704.5j - Legend rule: if a player controls two or more legendary
            # permanents with the same name, keep one (highest power), rest to GY.
            # Legendary creatures in the sim: Tamiyo, Murktide Regent, Wan Shi Tong
            # NOTE: Orcish Bowmasters is NOT legendary (Creature - Orc Archer)
            legendary_tags = {'tamiyo', 'murk', 'wst'}
            for tag in legendary_tags:
                copies = [c for c in player.creatures if c.card.tag == tag]
                if len(copies) > 1:
                    copies.sort(key=lambda c: c.power, reverse=True)
                    for c in copies[1:]:
                        player.remove_creature(c)  # handles revolt + GY automatically

        # Sync derived flags — bowmasters_on_board must reflect actual board state
        self.bowmasters_on_board = any(
            c.card.tag == 'bowm' for c in self.p1.creatures
        )
        # Sync orc_army reference
        orc = next((c for c in self.p1.creatures if c.card.tag == 'orc_army'), None)
        if orc is None:
            self.orc_army = None

        self.check_life_totals()

    def set_moon(self, active: bool):
        """S3: apply/remove Blood Moon to both players' lands."""
        self.moon_on_board = active
        self.p1.apply_blood_moon(active)
        self.p2.apply_blood_moon(active)

    def set_b2b(self, active: bool):
        """S4: apply/remove Back to Basics to both players' lands."""
        self.b2b_on_board = active
        self.p1.apply_b2b(active)
        self.p2.apply_b2b(active)

    def apply_continuous_effects(self, perm) -> None:
        """CR 613 — apply all currently active global continuous effects to a
        newly entered permanent.  Call this from every entry point that puts a
        permanent onto the battlefield (play_land, use_fetch, put_creature_in_play,
        put_artifact_in_play, put_enchantment_in_play).

        Currently modelled continuous effects:
          - Blood Moon (CR 305.7): nonbasic lands become Mountains {R} only
          - Back to Basics (CR 305.6): nonbasic lands lose all abilities
        """
        from rules import LandPermanent
        if not isinstance(perm, LandPermanent):
            return  # Moon/B2B only affect lands
        if perm.is_nonbasic:
            if self.moon_on_board:
                perm.blood_moon_active = True
            if self.b2b_on_board:
                perm.b2b_active = True


# ─────────────────────────────────────────────
# Mulligan  CR 103.5 — London format
# ─────────────────────────────────────────────

def london_mulligan(deck_fn, keep_fn, matchup: str = '', trace: bool = False) -> tuple:
    """
    S1 fix — London mulligan: draw 7, put N on bottom (choosing best N to discard).
    Returns (hand, library, mulls_taken) or (hand, library, mulls_taken, trace_lines) if trace=True.
    """
    trace_lines = [] if trace else None

    def _hand_detail(hand):
        """Per-card listing with type annotation."""
        lines = []
        for i, c in enumerate(hand, 1):
            parts = [f"    {i}. {c.name}"]
            tags = []
            if c.is_land():
                if getattr(c, 'is_fetch', False): tags.append('fetch')
                elif c.is_basic: tags.append('basic')
                elif getattr(c, 'tag', '') == 'dual': tags.append('dual')
                else: tags.append('land')
            else:
                if c.is_creature(): tags.append(f"creature {c.base_power}/{c.base_toughness}")
                elif c.card_type.name == 'INSTANT': tags.append('instant')
                elif c.card_type.name == 'SORCERY': tags.append('sorcery')
                elif c.card_type.name == 'ARTIFACT': tags.append('artifact')
                elif c.card_type.name == 'PLANESWALKER': tags.append('planeswalker')
                tags.append(f"CMC {c.cmc}")
                if c.is_combo_piece: tags.append('combo')
                if c.win_condition: tags.append('win-con')
                if c.tag in ('fow', 'fon'): tags.append('free counter')
                elif c.tag in ('daze',): tags.append('free counter')
                elif c.tag in ('counter', 'veto', 'fluster'): tags.append('counter')
                if c.is_removal and c.tag not in ('fow', 'fon', 'daze'): tags.append('removal')
                if c.tag in ('bs', 'ponder'): tags.append('cantrip')
            lines.append(f"{parts[0]} ({', '.join(tags)})")
        return lines

    def _hand_summary(hand):
        lands = sum(1 for c in hand if c.is_land())
        creatures = sum(1 for c in hand if c.is_creature())
        counters = sum(1 for c in hand if c.tag in ('fow', 'fon', 'daze', 'fluster', 'counter', 'veto'))
        cantrips = sum(1 for c in hand if c.tag in ('bs', 'ponder'))
        removal = sum(1 for c in hand if c.is_removal and c.tag not in ('fow', 'fon', 'daze'))
        combo = sum(1 for c in hand if c.is_combo_piece or c.win_condition)
        parts = [f"Lands: {lands}"]
        if creatures: parts.append(f"Creatures: {creatures}")
        if counters: parts.append(f"Counters: {counters}")
        if cantrips: parts.append(f"Cantrips: {cantrips}")
        if removal: parts.append(f"Removal: {removal}")
        if combo: parts.append(f"Combo: {combo}")
        other = len(hand) - lands - creatures - counters - cantrips - removal - combo
        if other > 0: parts.append(f"Other: {other}")
        return '  '.join(parts)

    def _keep_reason(hand, kept):
        """Generate human-readable explanation for keep/mull decision."""
        lands = sum(1 for c in hand if c.is_land())
        threats = sum(1 for c in hand if c.is_creature() or c.win_condition)
        counters = sum(1 for c in hand if c.tag in ('fow', 'fon', 'daze', 'fluster', 'counter', 'veto'))
        cantrips = sum(1 for c in hand if c.tag in ('bs', 'ponder'))
        removal = sum(1 for c in hand if c.is_removal and c.tag not in ('fow', 'fon', 'daze'))
        combo = sum(1 for c in hand if c.is_combo_piece or c.win_condition)
        action = threats + counters + cantrips + removal + combo

        if kept:
            reasons = []
            if 2 <= lands <= 3:
                reasons.append(f"{lands} lands — good mana base")
            elif lands == 1 and cantrips:
                reasons.append("1 land + cantrip to find more")
            elif lands == 4:
                reasons.append("4 lands — slightly land-heavy but playable")
            if threats >= 1:
                reasons.append(f"{threats} threat(s) for a clock")
            if counters >= 1:
                reasons.append(f"{counters} counter(s) for protection/disruption")
            if cantrips and not threats:
                reasons.append("cantrip(s) to dig for threats")
            if combo >= 2:
                reasons.append(f"combo pieces present — can threaten early kill")
            if removal:
                reasons.append(f"removal for opponent's threats")
            return "    Reason: " + "; ".join(reasons) if reasons else "    Reason: meets minimum keep criteria"
        else:
            problems = []
            if lands < 1:
                problems.append("zero lands — can't cast anything")
            elif lands == 1 and not cantrips:
                problems.append("only 1 land with no cantrips to find more")
            elif lands >= 5:
                problems.append(f"{lands} lands — too flooded, not enough spells")
            if action == 0:
                problems.append("no action (threats, counters, or cantrips)")
            if threats == 0 and combo == 0 and counters >= 3:
                problems.append("too many counters, no proactive plan")
            if lands >= 2 and action >= 2 and not problems:
                problems.append("doesn't meet deck-specific keep criteria")
            return "    Reason: " + "; ".join(problems) if problems else "    Reason: doesn't meet keep criteria"

    for mulls in range(4):  # 0 mulls = keep opening 7, max 3 mulls
        deck = list(deck_fn())
        random.shuffle(deck)
        # Always draw 7
        hand7 = deck[:7]
        rest = deck[7:]

        if trace:
            if mulls == 0:
                trace_lines.append(f"  Draw 7:")
            else:
                trace_lines.append(f"  Mulligan #{mulls} — draw 7:")
            trace_lines += _hand_detail(hand7)
            trace_lines.append(f"    [{_hand_summary(hand7)}]")

        if mulls == 0:
            if keep_fn(hand7, matchup):
                if trace:
                    trace_lines.append(f"  → KEEP (opening 7)")
                    trace_lines.append(_keep_reason(hand7, True))
                return (hand7, rest, 0, trace_lines) if trace else (hand7, rest, 0)
            if trace:
                trace_lines.append(f"  → MULLIGAN")
                trace_lines.append(_keep_reason(hand7, False))
            continue

        # Keep the best (7 - mulls) cards from the 7 seen
        hand = _choose_best_n(hand7, 7 - mulls)
        bottomed = [c for c in hand7 if c not in hand]
        library = rest + bottomed  # bottomed go to... bottom

        if trace:
            trace_lines.append(f"  Keep best {7 - mulls}: {', '.join(c.name for c in hand)}")
            trace_lines.append(f"  Bottom {mulls}: {', '.join(c.name for c in bottomed)}")
            trace_lines.append(f"    Bottom rationale: weakest by priority (counters > creatures > cantrips > other)")

        if keep_fn(hand, matchup):
            if trace:
                trace_lines.append(f"  → KEEP (mull to {7 - mulls})")
                trace_lines.append(_keep_reason(hand, True))
            return (hand, library, mulls, trace_lines) if trace else (hand, library, mulls)
        if trace:
            trace_lines.append(f"  → MULLIGAN")
            trace_lines.append(_keep_reason(hand, False))

    # Forced keep after 3 mulligans — still draw 7, keep best 4
    deck = list(deck_fn())
    random.shuffle(deck)
    hand7 = deck[:7]
    rest  = deck[7:]
    hand  = _choose_best_n(hand7, 4)  # choose best 4 (prioritises lands)
    bottomed = [c for c in hand7 if c not in hand]
    if trace:
        trace_lines.append(f"  Forced keep after 3 mulligans — draw 7:")
        trace_lines += _hand_detail(hand7)
        trace_lines.append(f"  Keep best 4: {', '.join(c.name for c in hand)}")
        trace_lines.append(f"  Bottom 3: {', '.join(c.name for c in bottomed)}")
    result = (hand, rest + bottomed, 3)
    return (*result, trace_lines) if trace else result


def _choose_best_n(hand7: List[Card], n: int) -> List[Card]:
    """
    From 7 cards, choose the best n to keep.
    Priority: lands (1-3 of them), then threats, counters, cantrips.
    """
    if n >= 7:
        return list(hand7)
    lands = [c for c in hand7 if c.is_land()]
    nonlands = [c for c in hand7 if not c.is_land()]

    # Score each card — higher = more keepable
    def score(c):
        if c.is_land():
            # Want 2-3 lands; penalize 4th+
            return 3
        if c.tag in ('fow', 'fon'): return 5
        if c.is_creature(): return 4
        if c.tag in ('bs', 'ponder'): return 3
        if c.tag in ('ts', 'push', 'ad'): return 3
        if c.tag in ('daze', 'fluster'): return 2
        return 1

    sorted_hand = sorted(hand7, key=score, reverse=True)
    return sorted_hand[:n]


def _colour_feasible(hand: List[Card]) -> bool:
    """
    M1 fix — colour feasibility check for London mulligan.
    Verify that every coloured spell in hand can plausibly be cast
    given the lands present.

    Fetch lands (Polluted Delta etc.) can find Underground Sea (UB),
    Tropical Island (UG), or Swamp (B) → effectively provide U, B, G.
    Wasteland provides nothing. Volcanic Island provides U, R only.

    If a spell requires a colour that no land in hand can produce,
    this hand is uncastable and should be mulliganed.
    """
    lands = [c for c in hand if c.is_land()]
    spells = [c for c in hand if not c.is_land()]

    available: set = set()
    for land in lands:
        if land.is_fetch:
            # Fetches can find any dual — assume access to all 5 colours
            available.update({'U', 'B', 'G', 'R', 'W'})
        else:
            available.update(land.produces)

    for spell in spells:
        cost = getattr(spell, 'mana_cost', {}) or {}
        for colour in ('U', 'B', 'G', 'R', 'W'):
            if cost.get(colour, 0) > 0 and colour not in available:
                return False  # spell is uncastable with these lands
    return True


def bug_keep(hand: List[Card], matchup: str = '') -> bool:
    """
    London mulligan keep decision for BUG Tempo.
    A keepable hand needs: mana development, at least one threat or interaction,
    and colour feasibility. Real players reject flood (5+ lands), screw (0-1 mana
    with no cantrip), and 0-action hands unconditionally.
    """
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)

    prod_lands = [l for l in lands if l.produces or l.is_fetch]
    if not prod_lands or lc > 5: return False
    if not _colour_feasible(hand): return False

    blue_access = any('U' in l.produces or l.is_fetch for l in lands)
    threats  = [c for c in nonlands if c.is_creature()]
    counters = [c for c in nonlands if c.tag in ('fow', 'fon', 'daze', 'fluster')]
    cantrips = [c for c in nonlands if c.tag in ('bs', 'ponder')]
    removal  = [c for c in nonlands if c.tag in ('push', 'ts', 'ad', 'dismember')]
    action   = len(threats) + len(counters) + len(cantrips) + len(removal)

    # Hard rejects — always mulligan these regardless of hand size
    if action == 0: return False               # zero action — just lands and bad cards
    if not blue_access and lc < 3: return False  # can't cast blue spells early

    # Hand quality by land count
    if lc == 1:
        # 1-land: only keep with cantrip to find more lands
        return blue_access and len(cantrips) >= 1 and action >= 2
    if lc == 2:
        # 2-land: need blue access and meaningful action
        return blue_access and action >= 2
    if lc == 3:
        # 3-land: the classic BUG keep — needs at least 1 threat or counter
        high_value = len(threats) + len(counters) + len(removal)
        return high_value >= 1 or (len(cantrips) >= 1 and action >= 2)
    if lc == 4:
        # 4-land: need 2+ action cards to justify the flood risk
        return action >= 2
    # lc == 5 rejected above
    return False


def opp_keep(hand: List[Card], matchup: str = '') -> bool:
    """
    Opponent mulligan keep. Checks deck_registry for a custom keep function
    first; falls back to generic logic for built-in decks.
    """
    # ── Check registry for deck-specific keep function ──
    try:
        from deck_registry import get_keep_fn
        keep_fn = get_keep_fn(matchup)
        if keep_fn:
            return keep_fn(hand, matchup)
    except ImportError:
        pass
    lands = [c for c in hand if c.is_land()]
    nonlands = [c for c in hand if not c.is_land()]
    lc = len(lands)
    prod = [l for l in lands if l.produces or l.is_fetch]

    # Combo decks that can function without lands — check BEFORE generic land gate
    if matchup in ('tes', 'storm', 'belcher'):
        if len(nonlands) < 1: return False
        tags = {c.tag for c in hand}

    if matchup == 'tes':
        # TES needs: mana source + fast mana + tutor or cantrip to find combo
        has_tutor = any(t in tags for t in ('burning_wish', 'infernal'))
        has_cantrip = any(c.tag in ('bs', 'ponder', 'probe') for c in nonlands)
        fast_mana = sum(1 for c in nonlands if c.tag in ('petal', 'led', 'chrome_mox', 'darkrit'))
        has_mana = lc >= 1 or fast_mana >= 2  # land, or 2+ artifact mana for 0-land hands
        has_action = has_tutor or has_cantrip
        if len(hand) <= 5:
            return has_mana and has_action
        # 6-7 cards: need mana + fast mana + tutor/cantrip
        return has_mana and fast_mana >= 1 and has_action

    if not prod or lc > 5: return False
    if len(nonlands) < 1: return False  # need at least 1 spell
    if not _colour_feasible(hand): return False
    # Combo decks: need a piece or a cantrip to find one
    if matchup in ('oops', 'show', 'doomsday', 'reanimator'):
        combo = [c for c in nonlands if c.is_combo_piece or c.win_condition]
        can   = [c for c in nonlands if c.tag in ('bs','ponder')]
        return 1 <= lc <= 4 and (combo or can)
    if matchup == 'storm':
        # ANT keep: needs mana acceleration (ritual/LED) + payoff or setup.
        # Real ANT keeps ~70% of 7s, ~85% of 6s — be permissive.
        rituals  = [c for c in nonlands if c.mana_ritual or c.tag in ('darkrit','cabalrit')]
        led      = any(c.tag == 'led' for c in nonlands)
        combo    = [c for c in nonlands if c.is_combo_piece or c.win_condition]
        can      = [c for c in nonlands if c.tag in ('bs','ponder')]
        protect  = [c for c in nonlands if c.tag in ('fow','vos','fluster','ts')]
        has_mana = len(rituals) >= 1 or led
        # LED counts as a land — LED in hand means 0-land keeps are fine
        effective_lands = lc + (1 if led else 0)
        has_payoff = bool(combo or can)  # has something to do with mana
        has_action = bool(combo or can or protect)  # broader: any useful spell
        # 7-card: mana + land structure. Storm draws into payoffs.
        # Don't require a combo piece upfront — any mana + land is fine.
        if len(hand) == 7:
            too_many_lands = lc >= 5  # 5+ lands = reject even with mana
            return 1 <= effective_lands <= 4 and has_mana and not too_many_lands
        # 6-card: mana + at least 1 land or LED
        if len(hand) == 6:
            return 0 <= effective_lands <= 3 and has_mana
        # 5-card: mana + land, or LED + anything
        if len(hand) == 5:
            return (has_mana and lc >= 1) or (led and len(nonlands) >= 2)
        # 4-card forced: always keep
        return True

    # 8-Cast: needs fast mana land (Tomb/City/Seat) + lock piece or engine
    if matchup == 'eight_cast':
        tags = {c.tag for c in hand}
        fast_land  = any(c.tag in ('ancient_tomb','city','seat','vault') for c in lands)
        lock_piece = 'chalice' in tags
        engine     = any(t in tags for t in ('emry','monitor','sai','karn','saga'))
        has_mana   = 'opal' in tags or 'petal' in tags or fast_land
        return has_mana and (lock_piece or engine)
    # Prison/Eldrazi: need a lock piece or early threat
    if matchup in ('prison', 'eldrazi'):
        lock = [c for c in nonlands if c.tag in ('chalice','bridge','trini')]
        thr  = [c for c in nonlands if c.is_creature()]
        return 2 <= lc <= 4 and (lock or thr)
    # Belcher: needs fast mana + Charbelcher or tutor
    if matchup == 'belcher':
        tags = {c.tag for c in hand}
        fast = sum(1 for c in nonlands if c.tag in ('petal','led','chrome_mox','esg','ssg','darkrit','rite'))
        has_belcher = 'belcher' in tags or 'burning_wish' in tags
        has_empty = 'empty' in tags
        # Keep any hand with fast mana + win condition
        if len(hand) <= 5: return fast >= 1 and (has_belcher or has_empty)
        return fast >= 2 and (has_belcher or has_empty)
    # Burn: keep almost any hand with 1-3 lands
    if matchup == 'burn':
        return 1 <= lc <= 3
    # Infect: needs infect creature + pump spell or land
    if matchup == 'infect':
        tags = {c.tag for c in hand}
        has_infect = any(t in tags for t in ('glistener','blighted','inkmoth'))
        has_pump = any(t in tags for t in ('invigorate','mutagenic','berserk','vines','defense'))
        if len(hand) <= 5: return has_infect and lc >= 1
        return has_infect and lc >= 1 and (has_pump or any(c.is_cantrip for c in nonlands))
    # Depths: needs a combo land or tutor for it
    if matchup == 'depths':
        tags = {c.tag for c in hand}
        has_combo = ('depths' in tags and 'stage' in tags)
        has_tutor = any(t in tags for t in ('crop','scrying','reclaimer','gsz','once'))
        has_piece = 'depths' in tags or 'stage' in tags
        if len(hand) <= 5: return lc >= 1 and (has_piece or has_tutor)
        return lc >= 1 and (has_combo or (has_piece and has_tutor) or has_tutor)
    # Goblins: needs land + Lackey/Vial or creatures
    if matchup == 'goblins':
        tags = {c.tag for c in hand}
        has_t1 = 'lackey' in tags or 'vial' in tags
        threats = sum(1 for c in nonlands if c.is_creature())
        return 2 <= lc <= 4 and (has_t1 or threats >= 2)
    # UR Delver: needs land + threat + cantrip/counter
    if matchup == 'ur_delver':
        threats = sum(1 for c in nonlands if c.is_creature())
        cantrips = sum(1 for c in nonlands if c.tag in ('bs','ponder','pre'))
        return 1 <= lc <= 3 and threats >= 1 and (cantrips >= 1 or len(hand) <= 5)

    # Sneak & Show: needs mana (land/petal/tomb) + combo piece (SnT) or payoff + cantrip
    if matchup in ('sneak_a', 'sneak_b'):
        tags = {c.tag for c in hand}
        has_sat = 'sat' in tags  # Show and Tell
        has_payoff = any(t in tags for t in ('emrakul', 'atraxa', 'omni', 'sneak'))
        has_cantrip = any(c.is_cantrip for c in nonlands)
        fast_mana = sum(1 for c in hand if c.tag in ('petal', 'tomb', 'city'))
        mana_ok = lc >= 1 or fast_mana >= 1
        if len(hand) <= 5:
            # Small hands: keep any hand with mana + either combo or cantrip
            return mana_ok and (has_sat or has_payoff or has_cantrip)
        # 6-7 cards: need mana + (combo piece or cantrip to find one)
        # Sneak & Show keeps most hands with a land and something to do
        has_action = has_sat or has_payoff or has_cantrip
        return mana_ok and 1 <= lc <= 5 and has_action

    # Affinity / 8-Cast variant: needs fast mana + artifacts + threat/engine
    if matchup == 'affinity':
        tags = {c.tag for c in hand}
        fast_mana = sum(1 for c in hand if c.tag in ('petal', 'opal', 'tomb', 'seat'))
        threats = sum(1 for c in nonlands if c.is_creature())
        engine = any(t in tags for t in ('emry', 'monitor', 'automaton', 'cannoneer', 'saga'))
        return fast_mana >= 1 and (threats >= 1 or engine)

    # UR Tempo: needs land + threat + action
    if matchup == 'ur_tempo':
        threats = sum(1 for c in nonlands if c.is_creature())
        cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder', 'bauble'))
        return 1 <= lc <= 3 and threats >= 1 and (cantrips >= 1 or len(hand) <= 5)

    # Dimir C/D: same as BUG — need mana + action
    if matchup in ('dimir_c', 'dimir_d'):
        blue_access = any('U' in l.produces or l.is_fetch for l in lands)
        threats = sum(1 for c in nonlands if c.is_creature())
        cantrips = sum(1 for c in nonlands if c.tag in ('bs', 'ponder'))
        counters = sum(1 for c in nonlands if c.tag in ('fow', 'daze'))
        action = threats + cantrips + counters
        if action == 0: return False
        if lc == 1: return blue_access and cantrips >= 1
        return 2 <= lc <= 4 and action >= 2

    # Cephalid Breakfast: needs mana + combo piece or cantrip to find it
    if matchup == 'cephalid':
        tags = {c.tag for c in hand}
        has_combo = any(t in tags for t in ('illusionist', 'nomads', 'shuko'))
        has_cantrip = any(c.is_cantrip for c in nonlands)
        has_protection = any(t in tags for t in ('fow', 'daze', 'chant'))
        if len(hand) <= 5: return lc >= 1 and (has_combo or has_cantrip)
        return 1 <= lc <= 4 and (has_combo or has_cantrip) and (has_combo or has_protection)

    # Cloudpost: needs lands (especially Locus/Tron) + payoff or ramp spell
    if matchup == 'cloudpost':
        tags = {c.tag for c in hand}
        locus = sum(1 for c in lands if c.tag in ('post', 'glimmer', 'nexus'))
        tron = sum(1 for c in lands if c.tag in ('tower', 'mine', 'plant'))
        has_ramp = any(t in tags for t in ('crop', 'map', 'petal'))
        has_payoff = any(t in tags for t in ('karn', 'ring', 'ugin', 'ulamog', 'koz_cmd'))
        if len(hand) <= 5: return lc >= 1 and (has_ramp or has_payoff)
        return lc >= 2 and (locus >= 1 or tron >= 1 or has_ramp) and (has_payoff or has_ramp)

    # Fair decks: need 2 lands and meaningful action
    threats  = [c for c in nonlands if c.is_creature()]
    counters = [c for c in nonlands if c.tag in ('fow','fon','daze')]
    cantrips = [c for c in nonlands if c.tag in ('bs','ponder')]
    removal  = [c for c in nonlands if c.tag in ('push','ts','ad')]
    action   = len(threats) + len(counters) + len(cantrips) + len(removal)
    return 2 <= lc <= 4 and action >= 2


# ─────────────────────────────────────────────
# On-demand mana tapping — replaces bulk upfront tap
# ─────────────────────────────────────────────

def tap_for_cost(player: 'PlayerState', cost: dict) -> bool:
    """
    CR 601.2f — tap lands to pay a specific cost, on demand.
    Tries to satisfy colored requirements first, then generic.
    Returns True if the cost can be met and taps the required lands.
    Does NOT use the ManaPool — directly taps lands.
    """
    # Build a list of untapped lands and their available colors
    available = [(l, l.effective_produces()) for l in player.lands
                 if not l.tapped and not l.is_fetch and l.effective_produces()]

    # Clone the cost
    remaining = dict(cost)

    # 1. Satisfy colored requirements
    for color in ['U', 'B', 'G', 'R', 'W', 'C']:
        needed = remaining.get(color, 0)
        if needed <= 0:
            continue
        for land, produces in available:
            if needed <= 0:
                break
            if land.tapped:
                continue
            if color in produces:
                land.tapped = True
                needed -= 1
        remaining[color] = needed

    # 2. Satisfy generic with any remaining untapped land
    generic = remaining.get('generic', 0)
    for land, produces in available:
        if generic <= 0:
            break
        if land.tapped:
            continue
        land.tapped = True
        generic -= 1
    remaining['generic'] = generic

    # Check if everything was paid
    unpaid = sum(v for v in remaining.values() if v > 0)
    return unpaid == 0


def can_afford(player: 'PlayerState', cost: dict) -> bool:
    """
    Check if the player can pay a mana cost without actually tapping lands.
    Uses pool mana + untapped land count.
    """
    from rules import ManaPool
    # Count available colored mana from untapped lands + pool
    available_by_color = dict(player.mana.pool)
    for land in player.lands:
        if not land.tapped and not land.is_fetch:
            for color in land.effective_produces():
                available_by_color[color] = available_by_color.get(color, 0) + 1

    remaining = dict(cost)

    # Colored requirements
    for color in ['U', 'B', 'G', 'R', 'W', 'C']:
        needed = remaining.get(color, 0)
        if needed <= 0:
            continue
        if available_by_color.get(color, 0) < needed:
            return False
        available_by_color[color] -= needed
        remaining[color] = 0

    # Generic from total remainder
    total_remaining = sum(available_by_color.values())
    return total_remaining >= remaining.get('generic', 0)
