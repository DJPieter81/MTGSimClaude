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

from config import (MatchupCategory as MC, InteractionParams as IP,
                    ThreatLevel, ClockDelta as CD, TSTargetPriority as TS)

if TYPE_CHECKING:
    from game import GameState


# ThreatLevel is defined in config.py and re-exported here so existing
# callers (`from interaction import ThreatLevel`) keep working.
__all__ = ['ThreatLevel', 'classify_threat', 'best_proactive_target',
           'threat_level_to_clock_delta', 'AnswerPlan']


def threat_level_to_clock_delta(level: int) -> float:
    """Convert the categorical ThreatLevel to a clock-delta float.

    Bridge to clock.py-style scoring (PLANNING_REFERENCE §9 #4). Use this
    where a strategy needs a numeric threat weight instead of a category —
    letting it compose with other clock deltas (burn damage, new creature,
    removal) without refactoring the existing classify_threat() callers.
    """
    return {
        ThreatLevel.MUST_ANSWER_NOW: CD.MUST_ANSWER_NOW,
        ThreatLevel.HIGH:            CD.HIGH,
        ThreatLevel.MEDIUM:          CD.MEDIUM,
        ThreatLevel.LOW:             CD.LOW,
    }.get(level, 0.0)


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


# best_reactive_answer() was removed on 2026-04-12 — it had been imported by
# engine.py but never actually called. Its P1-hardcoded `b = gs.p1` logic was
# cited as a cause of tempo-mirror asymmetry; that diagnosis was wrong (the
# real cause is the protagonist_turn / opp_turn path divergence — see
# results/tempo_mirror_root_cause.md). Removing the dead code keeps the
# module focused on what callers actually use: classify_threat() and
# best_proactive_target().


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
        """Higher = strip this first. Branch order matters — first match wins."""
        if c.is_land(): return 0
        if c.win_condition: return TS.WIN_CONDITION
        if c.is_combo_piece: return TS.COMBO_PIECE
        if c.lock_piece: return TS.LOCK_PIECE
        if c.engine: return TS.ENGINE
        # Mirror-only: draw-punisher (e.g. Bowmasters) outranks lock/engine here
        # but is checked AFTER them to preserve historical branch order.
        if is_mirror and c.draw_trigger: return TS.MIRROR_DRAW_TRIGGER
        # Counterspells — strip free protection in ALL matchups
        if c.free_cast_if_blue and c.cmc >= 3: return TS.FREE_COUNTER
        # Mirror only: cheaper free_cast (Brainstorm-class) still worth stripping
        if is_mirror and c.free_cast_if_blue: return TS.MIRROR_FREE_CAST
        if c.is_creature() and c.haste: return TS.HASTE_CREATURE
        if c.is_creature() and c.cmc >= 4: return TS.HIGH_CMC_CREATURE
        if c.is_creature() and c.cmc >= 2: return TS.MID_CMC_CREATURE
        if c.mana_ritual: return TS.RITUAL
        if c.is_removal: return TS.REMOVAL
        return TS.BASELINE

    scored = [(score(c), c) for c in hand if not c.is_land()]
    if not scored:
        return None
    return max(scored, key=lambda x: x[0])[1]


# ─────────────────────────────────────────────
# Proactive Push timing
# ─────────────────────────────────────────────

# should_push_now() was removed on 2026-04-12 for the same reason as
# best_reactive_answer above: imported but never called, P1-hardcoded,
# and not the root cause of tempo-mirror asymmetry (see that doc).
