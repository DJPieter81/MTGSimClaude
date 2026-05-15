"""
combo_engine.py — single owner of combo-deck decision-making.

See docs/design/2026-05-09_combo_engine_architecture.md.

Phase 1 implements `log_combo_decision` and the dataclasses; the three
predicate functions are stubs (NotImplementedError) until Phases 2/3/5
land their behaviour.

The `log_combo_decision` line format is the canonical source of decisions
parsed by `llm_judge.collect()` (which keys the heuristic grader's
`strategic_decisions`). Format:

    T<turn> [<deck>] [phase:<phase>] chose <chosen> from [<candidates>] — <reason>

Tests in `sim.run_rules_tests` round-trip the format through
`llm_judge.collect`'s parser to pin this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ─── Dataclasses ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AssemblyPath:
    """One way for a combo deck to assemble its win condition.

    `required_tags` is a frozenset of tag strings (NOT card names) that
    name combo pieces. Engine/AI code consults this via the deck-registry
    `'combo'` metadata; deck modules construct it from their own card
    knowledge.

    `target_tags` (optional) — when non-empty, the path is satisfied only
    if AT LEAST ONE tag in this set is also present in
    hand/graveyard. Use this to model "needs a creature target" lines
    (Reanimator) or "needs a damage source" lines (Belcher). Empty set
    (default) means the path has no target requirement (Storm/Tendrils).
    """
    tag:           str
    required_tags: frozenset
    mana_cost:     int
    turns_to_kill: int
    target_tags:   frozenset = frozenset()


@dataclass(frozen=True)
class ProtectionDecision:
    """Result of consulting opponent's known disruption before going off.

    `defer` — should the strategy hold this turn instead of firing combo?
    `hold`  — the Card to keep in hand as protection (None if defer=False
              or no protection is possible).
    `reason` — short human-readable reason; goes into the
               `strategic_decisions` log line.
    """
    defer:  bool
    hold:   object  # Card or None — typed as object to avoid circular import
    reason: str


# ─── Decision emitter (Phase 1) ──────────────────────────────────────────

def log_combo_decision(log_fn, *, turn, deck, phase, chosen, reason,
                       candidates=None) -> None:
    """Emit a single strategic-decision line into the game log.

    The format is the contract consumed by `llm_judge.collect()` (which
    populates `trace['strategic_decisions']` for the heuristic grader and
    the LLM rubric).

    Args:
        log_fn:     the strategy's `log_fn` callback (engine pattern).
        turn:       int — `gs.turn`.
        deck:       str — deck key (e.g. 'storm').
        phase:      str — one of {'mulligan','mana','combat','combo',
                                  'interaction','meta','setup'}.
        chosen:     str — the chosen action label.
        reason:     str — short human-readable justification.
        candidates: list[str] | None — optional alternatives considered.
    """
    cands = candidates if candidates is not None else []
    cand_str = '[' + ', '.join(str(c) for c in cands) + ']'
    log_fn(f"T{turn} [{deck}] [phase:{phase}] chose {chosen} "
           f"from {cand_str} — {reason}")


# ─── Predicates (Phases 2-5 implement) ───────────────────────────────────

def is_combo_ready_this_turn(player, gs) -> bool:
    """True iff at least one declared `AssemblyPath` is satisfiable from
    the current player's hand+graveyard (tags) AND the active mana floor
    (`gs._executing_mana` if set, otherwise the count of untapped lands).

    The predicate is consulted by the shared discard preamble in
    `sim._execute_turn` to skip the preamble when the combo is ready —
    otherwise discard would burn the only mana source and fizzle the
    line. Reanimator T2 is the canonical case (Land → Dark Ritual →
    Unmask → Reanimate); without the skip the matchup vs Burn drops to
    ~20%.

    Returns False (cleanly) for any deck without `'combo'` metadata, so
    the predicate is safe to call from the shared preamble unconditionally.
    """
    from deck_registry import get_combo_meta

    own_deck_key = gs.p1_deck if player is gs.p1 else gs.p2_deck
    cm = get_combo_meta(own_deck_key)
    if cm is None:
        return False

    paths = cm.get('assembly_paths', ())
    if not paths:
        return False

    # Tags currently available — pieces in hand OR (for graveyard-targets)
    # in the graveyard. The deck-registry `pieces` schema doesn't
    # distinguish zones; we accept either as "present".
    available = {getattr(c, 'tag', None) for c in player.hand}
    available |= {getattr(c, 'tag', None) for c in player.graveyard}
    available.discard(None)

    # Mana floor: prefer caller-supplied `_executing_mana` (set by
    # sim._execute_turn before dispatch); fall back to untapped lands.
    mana = getattr(gs, '_executing_mana', None)
    if mana is None:
        mana = sum(1 for ld in player.lands if not ld.tapped)

    for path in paths:
        if not (path.required_tags.issubset(available) and path.mana_cost <= mana):
            continue
        # Optional target requirement: when non-empty, at least one
        # target tag must be available too.
        if path.target_tags and not (path.target_tags & available):
            continue
        return True
    return False


def combo_protection_check(player, opponent, gs) -> ProtectionDecision:
    """Decide whether to defer combo / hold protection given opponent's
    known disruption.

    Reads `combo.protection_tags` from the deck-registry combo metadata,
    consults `bhi.HandBelief` for `p_free_counter`, and:

      * If `p_free_counter` ≤ `IP.BHI_FREE_COUNTER_THRESHOLD` →
        proceed (defer=False, hold=None).
      * If above threshold AND a card with a protection tag is in hand →
        hold that card (defer=False, hold=card). Reason includes the
        keyword 'protect' so the heuristic grader keys on it.
      * If above threshold AND no protection in hand →
        defer one turn (defer=True, hold=None). Reason also contains
        'protect'.

    Pure function: reads `gs`/`player`/`opponent` but does not mutate
    them. The HandBelief is constructed locally; callers that need
    cached belief state should consult `gs._bhi_*` directly.

    Returns `ProtectionDecision(defer=False, hold=None,
    reason='no combo metadata')` for non-combo decks (no metadata
    declared). This makes the function safe to call from any strategy.
    """
    from bhi import HandBelief
    from config import InteractionParams as IP
    from deck_registry import get_combo_meta

    own_deck_key = gs.p1_deck if player is gs.p1 else gs.p2_deck
    cm = get_combo_meta(own_deck_key)
    if cm is None:
        return ProtectionDecision(defer=False, hold=None,
                                  reason='no combo metadata for deck')

    opp_deck_key = gs.p2_deck if opponent is gs.p2 else gs.p1_deck
    belief = HandBelief(opp_deck_key,
                        cards_drawn=7 + max(0, gs.turn - 1),
                        cards_in_hand=len(opponent.hand))

    if belief.p_free_counter <= IP.BHI_FREE_COUNTER_THRESHOLD:
        return ProtectionDecision(
            defer=False, hold=None,
            reason=f'opp p_free_counter={belief.p_free_counter:.2f} '
                   f'≤ {IP.BHI_FREE_COUNTER_THRESHOLD:.2f}, no protection needed'
        )

    protection_tags = cm.get('protection_tags', frozenset())
    hold_card = next((c for c in player.hand
                      if getattr(c, 'tag', None) in protection_tags), None)
    if hold_card is not None:
        return ProtectionDecision(
            defer=False, hold=hold_card,
            reason=f'protect combo: hold {hold_card.tag} '
                   f'vs opp p_free_counter={belief.p_free_counter:.2f}'
        )

    return ProtectionDecision(
        defer=True, hold=None,
        reason=f'protect combo by deferring: opp p_free_counter='
               f'{belief.p_free_counter:.2f}, no protection in hand'
    )


def fastest_assemble_plan(player, gs, paths) -> Optional[AssemblyPath]:
    """Pick the lowest-`(turns_to_kill, mana_cost)` `AssemblyPath` from
    `paths` that the player can satisfy.

    Satisfaction criteria mirror `is_combo_ready_this_turn`:
      * `required_tags` ⊆ `available` (hand ∪ graveyard tags), AND
      * `target_tags` ∩ `available` ≠ ∅ when `target_tags` is non-empty, AND
      * `mana_cost` ≤ `gs._executing_mana` (falling back to count of
        untapped lands if `_executing_mana` is unset).

    Pure function: reads `player`/`gs`/`paths` but does not mutate them.
    Accepts `paths` as any iterable (list, tuple, generator) — sorted
    locally before iteration.

    Returns the cheapest satisfiable `AssemblyPath`, or `None` if nothing
    in `paths` is satisfiable.
    """
    # Tags currently available — pieces in hand OR graveyard. Same
    # split-zone semantics as is_combo_ready_this_turn.
    available = {getattr(c, 'tag', None) for c in player.hand}
    available |= {getattr(c, 'tag', None) for c in player.graveyard}
    available.discard(None)

    # Mana floor: prefer caller-supplied `_executing_mana`, fall back to
    # untapped lands.
    mana = getattr(gs, '_executing_mana', None)
    if mana is None:
        mana = sum(1 for ld in player.lands if not ld.tapped)

    # Sort by (turns_to_kill, mana_cost) so we consider the fastest
    # cheapest plan first. tuple() materialises generator inputs.
    ordered = sorted(tuple(paths), key=lambda p: (p.turns_to_kill, p.mana_cost))

    for path in ordered:
        if not path.required_tags.issubset(available):
            continue
        if path.target_tags and not (path.target_tags & available):
            continue
        if path.mana_cost > mana:
            continue
        return path
    return None
