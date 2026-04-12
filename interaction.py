"""
interaction.py — Holistic interaction decision engine.

Decisions are property-based (Card.lock_piece, Card.engine, Card.haste, etc.)
rather than tag-based frozenset membership checks.

Only unavoidable card-specific mechanics still use tag:
  - Terminus (miracle), Karakas (legendary bounce), Flickerwisp (ETB blink),
    Painter+Grindstone (tap combo), WST (fetch trigger), Bauble (upkeep draw)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from config import MatchupCategory as MC, InteractionParams as IP

if TYPE_CHECKING:
    from game import GameState


# ─────────────────────────────────────────────
# Threat levels
# ─────────────────────────────────────────────

class ThreatLevel:
    MUST_ANSWER_NOW = 4   # combo / win-con — resolve = likely lose
    HIGH            = 3   # engine / lock / haste — permanent advantage
    MEDIUM          = 2   # fair threat answerable next turn
    LOW             = 1   # cantrip / ritual / minor spell


def classify_threat(spell_card, gs) -> int:
    """
    Property-based threat classification.
    No frozenset membership checks — derives from Card attributes set at construction.
    """
    cmc = spell_card.cmc

    # ── MUST: combo pieces and win conditions ──────────────────────────
    if spell_card.is_combo_piece or spell_card.win_condition:
        return ThreatLevel.MUST_ANSWER_NOW

    # ── HIGH: lock pieces ──────────────────────────────────────────────
    # Chalice, Bridge, Moon, Trinisphere, Back to Basics
    if spell_card.lock_piece:
        return ThreatLevel.HIGH

    # ── HIGH: ongoing-value engines ────────────────────────────────────
    # Vial, Kaito, WST, Narset, SFM — snowball if they stick
    if spell_card.engine:
        return ThreatLevel.HIGH

    # ── HIGH: haste / immediate-impact creatures ────────────────────────
    if spell_card.is_creature() and spell_card.haste:
        return ThreatLevel.HIGH

    # ── HIGH: mass removal ─────────────────────────────────────────────
    if spell_card.is_mass_removal:
        return ThreatLevel.HIGH

    # ── HIGH: CMC5+ finishers ──────────────────────────────────────────
    if cmc >= 5:
        return ThreatLevel.HIGH

    # ── HIGH: CMC2+ creature in non-mirror context ─────────────────────
    # In reactive context, Fatal Push cannot counter stacked spells.
    # FoW is the only answer, so threshold is lowered.
    # Exception: cycling creatures (like Street Wraith in Doomsday) are never cast
    # as threats — they're pure utility. Identified by having life_cost > 0 and
    # not having meaningful combat stats (base_power == base_toughness == 0 heuristic
    # doesn't work since Wraith is 2/3). Use tag-based exception for known cyclers.
    _CYCLING_ONLY_TAGS = frozenset({'wraith', 'edge'})  # Street Wraith, Edge of Autumn
    if spell_card.is_creature() and cmc >= 2 and not MC.is_mirror(gs):
        if spell_card.tag not in _CYCLING_ONLY_TAGS:
            return ThreatLevel.HIGH

    # ── MEDIUM: removal spells worth Dazing ───────────────────────────
    if spell_card.is_removal:
        return ThreatLevel.MEDIUM

    # ── MEDIUM: creatures (mirror or CMC1) ────────────────────────────
    if spell_card.is_creature():
        return ThreatLevel.MEDIUM

    # ── LOW: cantrips, rituals, enablers ──────────────────────────────
    return ThreatLevel.LOW


# ─────────────────────────────────────────────
# Answer selection
# ─────────────────────────────────────────────

@dataclass
class AnswerPlan:
    tool: str     # 'push'|'ad'|'fow'|'fon'|'fluster'|'daze'|'none'
    reason: str


def _has(b, tag: str) -> bool:
    return any(c.tag == tag for c in b.hand)

def _hand_size(b) -> int:
    return len(b.hand)


def best_reactive_answer(spell_card, gs, is_opponents_turn: bool) -> AnswerPlan:
    """
    Choose cheapest answer to a spell on the stack.
    Push/AD cannot counter stacked spells — only counters available here.
    """
    b = gs.p1
    tag = spell_card.tag
    cmc = spell_card.cmc
    is_creature = spell_card.is_creature()

    threat = classify_threat(spell_card, gs)
    opp_untapped = gs.p2.available_mana_count()
    hand = _hand_size(b)
    life = b.life
    is_mirror = MC.is_mirror(gs)
    critical = life <= IP.CRITICAL_LIFE

    # ── LOW: only Fluster/Daze, never hard counters ──
    if threat == ThreatLevel.LOW:
        if _has(b, 'fluster') and not is_creature:
            return AnswerPlan('fluster', f'Flusterstorm low-threat {tag}')
        if opp_untapped <= cmc:
            return AnswerPlan('daze', f'Daze low-threat {tag}')
        return AnswerPlan('none', f'LOW threat — pass {tag}')

    # ── FoN: free on opp's turn for noncreature spells ──
    fon_ok = is_opponents_turn and not is_creature and _has(b, 'fon') and hand >= 2
    if fon_ok and threat >= ThreatLevel.MEDIUM:
        return AnswerPlan('fon', f'FoN noncreature CMC{cmc}')

    # ── FoW threshold ──
    # Creatures: FoW is often the only reactive answer (Push can't counter stacked spells).
    #   Mirror: MEDIUM threshold (every creature matters).
    #   Non-mirror: HIGH threshold (CMC2+ already HIGH via classify_threat).
    # Noncreatures: HIGH+ only (FoN handled MEDIUM).
    gate = IP.FOW_HAND_GATE_DnT if MC.is_vial(gs) else IP.FOW_HAND_GATE
    fow_ok_economy = hand >= gate or threat == ThreatLevel.MUST_ANSWER_NOW or critical

    if is_creature:
        fow_threshold = ThreatLevel.MEDIUM if is_mirror else ThreatLevel.HIGH
        fow_needed = threat >= fow_threshold
    else:
        fow_needed = threat >= ThreatLevel.HIGH

    if fow_needed and fow_ok_economy and _has(b, 'fow'):
        return AnswerPlan('fow', f'FoW threat={threat}')

    # ── Flusterstorm: 1U, instant/sorcery only ──
    if _has(b, 'fluster') and not is_creature and threat >= ThreatLevel.MEDIUM:
        return AnswerPlan('fluster', f'Flusterstorm CMC{cmc}')

    # ── Daze: free when opp tapped out ──
    if opp_untapped <= cmc and threat >= ThreatLevel.MEDIUM:
        return AnswerPlan('daze', f'Daze ({opp_untapped} mana vs CMC{cmc})')

    # ── FoW last resort for MUST_ANSWER ──
    if threat == ThreatLevel.MUST_ANSWER_NOW and _has(b, 'fow'):
        return AnswerPlan('fow', 'FoW last resort — MUST_ANSWER')

    return AnswerPlan('none', f'No answer for {tag}')


# ─────────────────────────────────────────────
# Proactive Thoughtseize targeting
# ─────────────────────────────────────────────

def best_proactive_target(gs, opponent=None):
    """
    Property-based Thoughtseize targeting.
    Orders by strategic priority, not tag membership.
    `opponent` is the player whose hand to search. If not provided, defaults to gs.p2
    (correct only when the caster is P1).
    """
    o = opponent if opponent is not None else gs.p2
    if not o.hand:
        return None

    hand = o.hand
    is_mirror = MC.is_mirror(gs)

    def score(c) -> int:
        """Higher = strip this first."""
        if c.is_land(): return 0
        # Win conditions and core combo pieces
        if c.win_condition: return 100
        if c.is_combo_piece: return 90
        # Lock pieces / engines — snowball severely
        if c.lock_piece: return 80
        if c.engine: return 70
        # Bowmasters in mirror — punishes every draw forever
        if is_mirror and c.draw_trigger: return 85
        # Counterspells — strip their protection in ALL matchups (not just mirror)
        # FoW / FoN enable them to protect their combo; always worth stripping
        if c.free_cast_if_blue and c.cmc >= 3: return 65  # FoW=5, FoN=3; not Brainstorm
        # Mirror: lower-CMC free_cast (Brainstorm etc.) still valuable in mirror
        if is_mirror and c.free_cast_if_blue: return 60
        # Haste / immediate impact
        if c.is_creature() and c.haste: return 60
        # General high-CMC threats
        if c.is_creature() and c.cmc >= 4: return 50
        if c.is_creature() and c.cmc >= 2: return 40
        # Mana rituals — delay their combo by 1 turn; worth stripping over cantrips
        if c.mana_ritual: return 25
        # Removal / disruption
        if c.is_removal: return 30
        # Low-impact (cantrips, etc.)
        return 10

    scored = [(score(c), c) for c in hand if not c.is_land()]
    if not scored:
        return None
    return max(scored, key=lambda x: x[0])[1]


# ─────────────────────────────────────────────
# Proactive Push timing
# ─────────────────────────────────────────────

def should_push_now(gs, target_perm) -> bool:
    """Should BUG spend Fatal Push on target_perm now vs holding mana for a counter?"""
    from rules import MTGRules
    b = gs.p1
    revolt = b.revolt_this_turn

    if not MTGRules.fatal_push_valid_target(target_perm, revolt):
        return False

    card = target_perm.card
    # Always Push immediately: engines, lock pieces, haste threats, draw triggers
    if card.engine or card.lock_piece or card.haste or card.draw_trigger:
        return True

    # Push if it's blocking our win
    bug_power = sum(c.power for c in b.creatures
                    if not c.summoning_sick and not c.tapped)
    if target_perm.toughness >= bug_power > 0:
        return True

    # Hold if we have a counter and opp likely has more spells
    has_counter = any(c.free_cast_if_blue or c.tag in ('fow','fon','daze','fluster')
                      for c in b.hand)
    opp_has_spells = any(not c.is_land() for c in gs.p2.hand)
    if has_counter and opp_has_spells:
        return False

    return True
