"""
combo_engine.py — combo-deck decision-making.

See:
  docs/design/2026-05-09_combo_engine_architecture.md (Phase 1, original)
  docs/design/2026-05-15_post-phase-6-re-architecture.md (Phases A-D)

Phase A retired `log_combo_decision` (now in
strategic_logger.StrategicLogger.log_decision with optional phase=).

Phase B (this module) replaces the three overlapping predicates
(is_combo_ready_this_turn, combo_protection_check, fastest_assemble_plan)
with a single typed entry point:

    plan = combo_plan(view: GameView) -> Plan
    match plan:
      case Execute(path):  fire the combo line
      case Hold(card):     hold a protection card
      case Defer():        skip the combo turn
      case NoPlan():       no combo metadata or no satisfiable path

Plan variants are frozen dataclasses; callers use isinstance.

GameView is the immutable subset of GameState that combo decisions
read. Built via `GameView.from_state(player, opponent, gs)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ─── Path schema (subtypes in Phase B2) ──────────────────────────────────

@dataclass(frozen=True)
class AssemblyPath:
    """One way for a combo deck to assemble its win condition.

    Phase B2 will split this into deck-shape subtypes (StormPath,
    ReanimatePath, LandComboPath, TribalPath) so each subtype's fields
    name what that mechanic actually needs. For now the schema is the
    Phase 5 shape:

      tag:           internal name (no card-name string)
      required_tags: tag strings (NOT card names) that must be present
                     in hand ∪ graveyard
      mana_cost:     minimum mana floor to start the chain (semantics
                     vary by deck — Phase B2 fixes this)
      turns_to_kill: turns from path-completion to win
      target_tags:   optional — when non-empty, at least one tag from
                     this set must also be in hand ∪ graveyard
    """
    tag:           str
    required_tags: frozenset
    mana_cost:     int
    turns_to_kill: int
    target_tags:   frozenset = frozenset()

    def is_satisfiable(self, view: GameView) -> bool:
        if not self.required_tags.issubset(view.available):
            return False
        if self.target_tags and not (self.target_tags & view.available):
            return False
        if self.mana_cost > view.mana:
            return False
        return True


# ─── GameView ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GameView:
    """Immutable subset of GameState that combo decisions read.

    Pure data — no references to mutable game objects. Built once per
    decision via `GameView.from_state(player, opponent, gs)`.
    """
    own_deck:  str
    opp_deck:  str
    available: frozenset       # tags in hand ∪ graveyard
    hand:      tuple           # actual Card objects (for Hold(card, ...))
    mana:      int             # mana floor for this decision
    turn:      int
    opp_hand_size: int         # for BHI construction

    @classmethod
    def from_state(cls, player, opponent, gs) -> GameView:
        avail = (
            {getattr(c, 'tag', None) for c in player.hand}
            | {getattr(c, 'tag', None) for c in player.graveyard}
        )
        avail.discard(None)
        # Mana floor: caller-set `gs._executing_mana` takes precedence
        # (set by sim._execute_turn before strategy dispatch); else fall
        # back to untapped lands.
        mana = getattr(gs, '_executing_mana', None)
        if mana is None:
            mana = sum(1 for ld in player.lands if not ld.tapped)
        return cls(
            own_deck=gs.p1_deck if player is gs.p1 else gs.p2_deck,
            opp_deck=gs.p2_deck if opponent is gs.p2 else gs.p1_deck,
            available=frozenset(avail),
            hand=tuple(player.hand),
            mana=mana,
            turn=gs.turn,
            opp_hand_size=len(opponent.hand),
        )


# ─── Plan algebra ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Plan:
    """Base for the four Plan variants. Strategies switch on isinstance.

    The `reason` field is always populated and contains the keyword that
    the heuristic grader (scripts/grade_traces.py) keys on for this
    Plan variant. Phase A's StrategicLogger.log_decision call writes
    `reason` verbatim into the decision-trace.
    """
    reason: str


@dataclass(frozen=True)
class Execute(Plan):
    """A satisfiable combo path was found — fire it.

    `path` is the cheapest AssemblyPath returned by the chooser.
    `reason` will contain the keyword 'combo' so the grader keys on it.
    """
    path: AssemblyPath


@dataclass(frozen=True)
class Hold(Plan):
    """Hold a specific protection card this turn.

    Returned when opponent is likely to have free counters (BHI gate)
    AND a protection card is in hand. `card` is the Card object to
    keep; `reason` contains the keyword 'protect'.
    """
    card: object   # Card — typed as object to avoid circular import


@dataclass(frozen=True)
class Defer(Plan):
    """Defer the combo turn entirely.

    Returned when opponent is likely to have free counters AND no
    protection card is in hand. `reason` contains the keyword 'protect'.
    """
    pass


@dataclass(frozen=True)
class NoPlan(Plan):
    """No combo plan available — deck has no metadata, or no path
    satisfies the current hand/graveyard/mana state.

    Strategies typically fall through to their fair-play branch when
    this variant is returned.
    """
    pass


# ─── Single entry point ───────────────────────────────────────────────────

def combo_plan(player, opponent, gs) -> Plan:
    """Decide what the combo deck should do this turn.

    Reads `combo` metadata from the deck registry. Returns:

      * `NoPlan(reason='no combo metadata')` — deck didn't declare it.
      * `NoPlan(reason='no satisfiable assembly path')` — pieces/mana
        don't satisfy any declared path.
      * `Hold(card, reason)` — opp BHI suggests free counter AND a
        protection-tag card is in hand.
      * `Defer(reason)` — opp BHI suggests free counter AND no
        protection in hand.
      * `Execute(path, reason)` — a satisfiable path was found, no
        protection trigger.

    Pure function: reads game state but does not mutate it.

    The protection-check (Hold/Defer) is consulted **before** the
    assembly-path chooser, because the strategy may want to skip
    firing combo this turn even if a path is satisfiable.
    """
    from deck_registry import get_combo_meta

    view = GameView.from_state(player, opponent, gs)
    cm = get_combo_meta(view.own_deck)
    if cm is None:
        return NoPlan(reason='no combo metadata for deck')

    # 1. Protection check via BHI.
    protect_plan = _check_protection(view, cm)
    if protect_plan is not None:
        return protect_plan

    # 2. Find the cheapest satisfiable path.
    paths = cm.get('assembly_paths', ())
    if not paths:
        return NoPlan(reason='no assembly paths declared')

    satisfiable = [p for p in paths if p.is_satisfiable(view)]
    if not satisfiable:
        return NoPlan(reason='no assembly path satisfiable')

    # Sort by (turns_to_kill, mana_cost), cheapest first.
    fastest = min(satisfiable, key=lambda p: (p.turns_to_kill, p.mana_cost))
    return Execute(
        path=fastest,
        reason=f'combo:{fastest.tag} (turns={fastest.turns_to_kill}, '
               f'mana={fastest.mana_cost})',
    )


def _check_protection(view: GameView, cm: dict) -> Optional[Plan]:
    """Return Hold(card)/Defer() if opp BHI triggers protection; else None.

    Internal helper of combo_plan. Splits out for readability and to keep
    the BHI / config imports local to the protection branch.
    """
    from bhi import HandBelief
    from config import InteractionParams as IP

    belief = HandBelief(
        view.opp_deck,
        cards_drawn=7 + max(0, view.turn - 1),
        cards_in_hand=view.opp_hand_size,
    )
    if belief.p_free_counter <= IP.BHI_FREE_COUNTER_THRESHOLD:
        return None   # proceed — no protection needed

    protection_tags = cm.get('protection_tags', frozenset())
    hold_card = next(
        (c for c in view.hand if getattr(c, 'tag', None) in protection_tags),
        None,
    )
    if hold_card is not None:
        return Hold(
            card=hold_card,
            reason=f'protect combo: hold {hold_card.tag} '
                   f'vs opp p_free_counter={belief.p_free_counter:.2f}',
        )
    return Defer(
        reason=f'protect combo by deferring: opp p_free_counter='
               f'{belief.p_free_counter:.2f}, no protection in hand',
    )
