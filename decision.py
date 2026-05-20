"""Typed Decision algebra — replaces the prefix-string token contract.

Each Decision is a frozen dataclass; the grader switches on isinstance()
rather than prefix-matching `chosen` strings. Token-string serialization
remains via `.to_token()` for trace JSON byte-equality with the prior schema.

Six subclasses model the axes the structural grader already recognizes:
  ComboDecision      — execute / hold / defer / tried
  DisruptionDecision — counter / discard / remove / extract / land_destroy
  CombatDecision     — attack / block / hold
  ManaDecision       — ramp / fix / burn / keep_open (scaffold, not yet wired)
  MulliganDecision   — mull / keep                    (scaffold)
  MetaDecision       — play_around / sideboard        (scaffold)

The legacy `log_decision(turn, deck, candidates, chosen, reason, phase)` call
still works unchanged — strategies that haven't been migrated keep emitting
raw token strings. The grader sees both shapes interchangeably (see
`_count_structural` in `scripts/structural_grader.py`).

See `docs/design/2026-05-16_typed-decision-algebra.md` for the full
design rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Decision:
    """Root of the Decision algebra.

    Every subclass carries the same four bookkeeping fields the trace JSON
    already records. The `kind` discriminator on each subclass narrows the
    mechanic; the `tag` fields carry the typed sub-payload.
    """
    turn: int
    deck: str
    phase: str | None = None
    reason: str = ''
    candidates: tuple[str, ...] = ()

    def to_token(self) -> str:
        """Serialize this Decision to its `chosen`-field token string.

        The output is byte-identical with the prefix-encoded string the
        strategy layer currently writes for this mechanic — this is what
        keeps trace JSON serialization stable across the refactor.
        """
        raise NotImplementedError(f'{type(self).__name__}.to_token() must be overridden')

    def to_log_entry(self) -> dict:
        """Convert to the dict shape `StrategicLogger.entries` already uses.

        Result keys: turn, deck, phase, candidates, chosen, reason —
        identical to what `log_decision(...)` currently appends.
        """
        return {
            'turn': self.turn,
            'deck': self.deck,
            'phase': self.phase,
            'candidates': list(self.candidates),
            'chosen': self.to_token(),
            'reason': self.reason,
        }


@dataclass(frozen=True)
class ComboDecision(Decision):
    """A combo-axis decision: did the deck fire its plan, hold a piece,
    pass on the turn, or play pieces that got disrupted?

    `kind` discriminates the four cases; `path_tag` and `piece_tag` carry
    the sub-mechanic name (storm / reanimate / depths / darkrit / tendrils …).
    Tag values are *mechanic names*, never literal card names.
    """
    kind: Literal['execute', 'hold', 'defer', 'tried'] = 'execute'
    path_tag: str = ''
    piece_tag: str = ''

    def to_token(self) -> str:
        if self.kind == 'execute':
            # `kill_C` was the legacy bare-execute token; `combo:<path>` is
            # the typed form. Empty path → legacy bare form.
            return f'combo:{self.path_tag}' if self.path_tag else 'kill_C'
        if self.kind == 'hold':
            return f'hold_{self.piece_tag or "piece"}'
        if self.kind == 'defer':
            return 'defer'
        if self.kind == 'tried':
            return f'tried_combo:{self.piece_tag or "piece"}'
        raise ValueError(f'ComboDecision.kind {self.kind!r} not in '
                         "{'execute','hold','defer','tried'}")


@dataclass(frozen=True)
class DisruptionDecision(Decision):
    """A disruption-axis decision: counter / discard / remove / extract /
    land_destroy.

    `target_tag` names the threat-type that was disrupted (mechanic name —
    never a literal card name); `instrument_tag` names the disruption spell
    type (also a mechanic name).
    """
    kind: Literal['counter', 'discard', 'remove', 'extract', 'land_destroy'] = 'counter'
    target_tag: str = ''
    instrument_tag: str = ''

    def to_token(self) -> str:
        # All five disruption kinds serialize as `<kind>_<target>_with_<instrument>`.
        # The grader's prefix helpers (_is_counter / _is_discard / _is_removal)
        # split on the `<kind>_` prefix to bucket.
        return (f'{self.kind}_{self.target_tag or "target"}'
                f'_with_{self.instrument_tag or "spell"}')


@dataclass(frozen=True)
class CombatDecision(Decision):
    """A combat-axis decision: attack / block / hold.

    `attacker_count` is the number of bodies committed; `attacker_tag` is
    the mechanic-name tribe / role descriptor (e.g. 'goblins', 'creatures',
    'elementals').
    """
    kind: Literal['attack', 'block', 'hold'] = 'attack'
    attacker_count: int = 0
    attacker_tag: str = ''

    def to_token(self) -> str:
        if self.kind == 'attack':
            # 'attack with N <tribe>' is the legacy phrase the structural
            # grader's `_is_combat_decision` recognizes via the 'attack'
            # prefix. Preserve it byte-for-byte.
            return f'attack with {self.attacker_count} {self.attacker_tag or "creatures"}'
        # block / hold variants: '<kind>_<tribe>' (not yet wired by callsites).
        return f'{self.kind}_{self.attacker_tag or "creatures"}'


@dataclass(frozen=True)
class ManaDecision(Decision):
    """A mana-axis decision: ramp / fix / burn / keep_open. Scaffold —
    no production callsite emits this yet.
    """
    kind: Literal['ramp', 'fix', 'burn', 'keep_open'] = 'ramp'
    mana_value: int = 0

    def to_token(self) -> str:
        return f'mana_{self.kind}_{self.mana_value}'


@dataclass(frozen=True)
class MulliganDecision(Decision):
    """A mulligan decision: mull / keep. Scaffold — production callsites
    log mulligan choices via a different mechanism today.
    """
    kind: Literal['mull', 'keep'] = 'keep'
    hand_size: int = 7
    reason_tag: str = ''

    def to_token(self) -> str:
        if self.kind == 'mull':
            return f'mull_to_{self.hand_size}_for_{self.reason_tag or "plan"}'
        return f'keep_{self.hand_size}_with_{self.reason_tag or "plan"}'


@dataclass(frozen=True)
class MetaDecision(Decision):
    """A meta-axis decision: play_around / sideboard. Scaffold — used for
    future matchup-awareness instrumentation.
    """
    kind: Literal['play_around', 'sideboard'] = 'play_around'
    threat_tag: str = ''

    def to_token(self) -> str:
        return f'meta_{self.kind}_{self.threat_tag or "threat"}'


__all__ = [
    'Decision',
    'ComboDecision',
    'DisruptionDecision',
    'CombatDecision',
    'ManaDecision',
    'MulliganDecision',
    'MetaDecision',
]
