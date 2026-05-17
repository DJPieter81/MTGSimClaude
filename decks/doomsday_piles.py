"""
Doomsday — typed Pile algebra (Phase B).

Mirrors `combo_engine.combo_plan`'s Execute/Hold/Defer/NoPlan shape: a
small set of frozen dataclasses representing the per-matchup pile shapes
the Doomsday strategy can build. Each Pile is a value with no
__init__-time side effects and no mutable state.

See `docs/design/2026-05-16_doomsday_cabal_therapy_piles.md` for the full
design. Phase B (this module) ships the dataclasses only — no engine
wiring. Phase C ships `select_pile()` (pure function returning one of
these types). Phase D wires the dispatch into `_strategy_doomsday`.

Architectural discipline (per the design doc's §7 Risks):
- Each pile declares its OWN resource cost (mana, life floor, draws).
- No shared mutation of `total_mana` / `player.life` outside the
  per-pile resolve callback in the strategy.
- This module imports nothing from `engine.py` — the dataclasses are
  pure values; the strategy reads them, the strategy never mutates them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pile:
    """Abstract base for the 4 concrete pile shapes.

    Fields:
        name:           short identifier used in Execute-token strings
                        (e.g. 'lurrus' → emits `combo:lurrus_pile`).
        cards:          tag sequence top→bottom (5 entries for a real
                        Doomsday pile).
        draws_to_win:   how many cards the deck must draw after DD
                        resolves to assemble the kill (Brainstorm = 3
                        cards, so OraclePile draws_to_win = 3).
        mana_to_execute: mana required AFTER DD resolves (for the
                        Brainstorm-Oracle execution).
        life_floor:     minimum own life pre-DD to survive execution
                        (DD costs half life rounded up; LurrusPile
                        accepts lower life floor than TendrilsPile).
    """
    name: str
    cards: tuple
    draws_to_win: int
    mana_to_execute: int
    life_floor: int


@dataclass(frozen=True)
class TendrilsPile(Pile):
    """Tendrils race line. 5-card pile drains opponent via LED + Dark
    Ritual + Cabal Ritual chain. Wins through counters by burning the
    stack pre-DD. Used vs COMBO_DECKS where racing the opposing combo
    is the only viable path."""


@dataclass(frozen=True)
class LurrusPile(Pile):
    """Lifegain pile. Lotus Petal → Brainstorm → Wraith × 3. Combined
    with Lurrus-rebuy of dying CMC-≤2 permanents, gains 6+ life via
    Lurrus's lifelink. Used vs AGGRO_DECKS at low life."""


@dataclass(frozen=True)
class WraithPile(Pile):
    """Resilience pile. Multi-Wraith chain with Brainstorm as the pile
    finisher. Used vs INTERACTION_DECKS where DD might get countered T2
    and the deck needs a recovery turn — the extra Wraiths buy time and
    fuel Cabal Therapy Flashback."""


@dataclass(frozen=True)
class OraclePile(Pile):
    """Default Oracle pile. No LED required — wins T+1 of the DD turn
    by drawing Brainstorm naturally. Used vs INTERACTION_DECKS when LED
    is in graveyard or exiled, or as the fallback when no other pile
    is applicable. Byte-equivalent to the pre-Phase-D existing kill
    line."""


# ─── Pile-selection thresholds ──────────────────────────────────────────────
# Named constants — no magic numbers per CLAUDE.md. Each constant gates a
# branch of the decision tree in select_pile(); changing one without
# updating its named test is a CI-detectable contract violation.

LIFE_FLOOR_AGGRO = 10
"""Below this life total against an AGGRO_DECKS opponent, the LurrusPile
(lifegain) is preferred over racing. Picked to match real-Legacy DD play:
at 11+ life vs Burn, pilots often opt for the Tendrils race instead."""


# ─── select_pile: the pile-selection subsystem ──────────────────────────────

def _has_tag(player, tag: str) -> bool:
    """Lurrus is available if in companion zone, in hand, or in play."""
    if any(c.tag == tag for c in player.hand):
        return True
    if getattr(player, 'companion_zone', None) is not None \
            and player.companion_zone.tag == tag:
        return True
    for perm in getattr(player, 'creatures', []):
        if perm.card.tag == tag:
            return True
    return False


def _hand_has(player, tag: str) -> bool:
    return any(c.tag == tag for c in player.hand)


# Deck classes read from the structural grader's canonical sets. Importing
# here keeps select_pile pure (no engine.py / sim.py dependency).
def _deck_classes():
    """Return (COMBO, AGGRO, INTERACTION) frozensets. Lazy import so this
    module stays importable in isolation."""
    import sys
    from pathlib import Path
    _scripts = Path(__file__).resolve().parent.parent / 'scripts'
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    import structural_grader as _sg  # noqa: E402
    return _sg.COMBO_DECKS, _sg.AGGRO_DECKS, _sg.INTERACTION_DECKS


def select_pile(player, opponent, gs) -> Pile:
    """Pure function: given the current GameState, return the Pile shape
    Doomsday should build when DD resolves this turn.

    Inputs read (no mutation):
      - opp deck class via the structural-grader's COMBO/AGGRO/INTERACTION
        sets (single source of truth — no deck-name string literals in
        this function).
      - player.life
      - player.hand tags (led, bs)
      - player.companion_zone / player.creatures for Lurrus availability

    Decision tree (matches §3.3 of the design doc):
      1. opp in AGGRO_DECKS AND player.life ≤ LIFE_FLOOR_AGGRO AND
         Lurrus available → LurrusPile
      2. opp in COMBO_DECKS → TendrilsPile
      3. opp in INTERACTION_DECKS AND has(LED) AND has(Brainstorm) →
         WraithPile
      4. otherwise → OraclePile (default; byte-equivalent to pre-Phase-D
         strategy behaviour)
    """
    COMBO, AGGRO, INTERACTION = _deck_classes()
    opp_deck = gs.p1_deck if player is getattr(gs, 'p2', None) else gs.p2_deck

    # Branch 1: lifegain pile.
    if (opp_deck in AGGRO
            and player.life <= LIFE_FLOOR_AGGRO
            and _has_tag(player, 'lurrus')):
        return LurrusPile(
            name='lurrus',
            cards=('petal', 'bs', 'wraith', 'wraith', 'wraith'),
            draws_to_win=3,
            mana_to_execute=2,
            life_floor=4,
        )

    # Branch 2: race the combo.
    if opp_deck in COMBO:
        return TendrilsPile(
            name='tendrils',
            cards=('led', 'darkrit', 'bs', 'oracle', 'wraith'),
            draws_to_win=3,
            mana_to_execute=3,
            life_floor=8,
        )

    # Branch 3: resilience vs interaction.
    if (opp_deck in INTERACTION
            and _hand_has(player, 'led')
            and _hand_has(player, 'bs')):
        return WraithPile(
            name='wraith',
            cards=('led', 'bs', 'wraith', 'wraith', 'oracle'),
            draws_to_win=3,
            mana_to_execute=2,
            life_floor=8,
        )

    # Branch 4: default Oracle pile (byte-equivalent fallback).
    return OraclePile(
        name='oracle',
        cards=('bs', 'oracle', 'wraith', 'wraith', 'petal'),
        draws_to_win=3,
        mana_to_execute=2,
        life_floor=8,
    )
