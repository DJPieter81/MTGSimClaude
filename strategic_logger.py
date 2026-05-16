"""
Strategic decision logger for AI tracing.

Attached to GameState as gs.strat_log. Off by default; enabled via the
--trace CLI flag on run_meta.py or the trace=True kwarg on run_game /
run_sweep. When enabled, strategy functions call gs.strat_log.log_decision(...)
at each branch point, and the accumulated entries are appended to
GameResult.log_lines before return.

Scope: instrumentation is currently wired into the three P0-relevant
strategies (_strategy_storm, _strategy_oops, _strategy_dnt). Further
strategies get added incrementally as matchups need debugging. This mirrors
the "port Modern's strategic_logger pattern" prerequisite from
PLANNING_REFERENCE.md Section 9 #1.
"""


class StrategicLogger:
    """Thin decision recorder. Cost when disabled: one attribute read per call."""

    __slots__ = ('enabled', 'entries', '_plan_cache')

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.entries: list[dict] = []
        # Per-deck GoalEngine cache (lazy — only hit if enabled + call-site asks)
        self._plan_cache: dict = {}

    def log_decision(self, turn: int, deck: str, candidates, chosen, reason: str,
                     phase: str = None) -> None:
        """Record a strategic decision.

        Args:
            turn:       game turn (gs.turn).
            deck:       active deck key.
            candidates: iterable of option labels considered.
            chosen:     the option label selected.
            reason:     short justification.
            phase:      OPTIONAL override. When provided, this exact phase
                        label is used in the dump (e.g. 'combat' for a
                        Goblin-Lackey trigger). When None (default), the
                        gameplan lookup (`_phase_for`) supplies the phase.
                        Phase A unified `combo_engine.log_combo_decision`
                        into this method; the override parameter preserves
                        Phase 4's `phase='combat'` semantics without forcing
                        a gameplan entry.
        """
        if not self.enabled:
            return
        # Enrich with gameplan phase label unless caller supplied an override
        if phase is None:
            phase = self._phase_for(deck, turn)
        self.entries.append({
            'turn': turn,
            'deck': deck,
            'candidates': list(candidates),
            'chosen': chosen,
            'reason': reason,
            'phase': phase,
        })

    def log_disruption(self, turn: int, gs, player, kind: str, target_tag: str,
                       instrument_tag: str, reason: str) -> None:
        """Single canonical emit-site for a typed disruption token.

        Replaces the `_attacker_deck = gs.p1_deck if player is gs.p1 else
        gs.p2_deck` + `log_decision(..., chosen=f'{kind}_<tag>_with_<instr>')`
        boilerplate that was duplicated across ~50 spot-removal / counter /
        discard sites in engine.py and sim.py (PRs #150, #151, #155).

        Args:
            turn:            game turn (gs.turn).
            gs:              GameState, used for the player→deck binding.
            player:          PlayerState — the disrupting deck's player slot
                             (the one CASTING the counter / discard / removal).
                             Resolved to `gs.p1_deck` if player is gs.p1
                             else `gs.p2_deck`.
            kind:            one of 'counter', 'discard', 'remove' — produces
                             the typed token prefix `{kind}_…`. Matches the
                             strict-prefix contract in scripts/structural_grader.py.
            target_tag:      tag of the targeted card (or fallback string
                             like 'creature' / 'spell' / 'card' / 'permanent'
                             at call-sites where the tag may be None).
            instrument_tag:  tag of the disruption instrument
                             (e.g. 'fow' for Force of Will, 'push' for Fatal
                             Push, 'ts' for Thoughtseize).
            reason:          short justification — passed through verbatim.

        The candidates list is fixed per-kind to mirror the historic
        wirings: ['counter','let_resolve'] for counter, ['thoughtseize','pass']
        for discard, ['remove','pass'] for remove. Picked to be
        byte-identical with the existing emissions so downstream parsers
        (llm_judge, structural_grader) see no diff.
        """
        if kind == 'counter':
            candidates = ['counter', 'let_resolve']
        elif kind == 'discard':
            candidates = ['thoughtseize', 'pass']
        elif kind == 'remove':
            candidates = ['remove', 'pass']
        else:
            raise ValueError(
                f"log_disruption: kind must be one of "
                f"'counter'/'discard'/'remove', got {kind!r}")
        deck = gs.p1_deck if player is gs.p1 else gs.p2_deck
        chosen = f'{kind}_{target_tag}_with_{instrument_tag}'
        self.log_decision(turn, deck, candidates=candidates,
                          chosen=chosen, reason=reason)

    def _phase_for(self, deck: str, turn: int):
        """Look up the gameplan phase for this turn. Returns None when no plan."""
        if deck not in self._plan_cache:
            try:
                from goal_engine import GoalEngine  # local import — optional dep
                self._plan_cache[deck] = GoalEngine(deck)
            except Exception:
                self._plan_cache[deck] = None
        ge = self._plan_cache[deck]
        if ge is None or not ge.has_plan:
            return None
        phase = ge.phase_for_turn(turn)
        return phase.get('phase') if phase else None

    def dump(self) -> list[str]:
        """Flatten entries into log_lines-compatible strings."""
        out = []
        for e in self.entries:
            cands = ','.join(str(c) for c in e['candidates'])
            phase_tag = f" [phase:{e['phase']}]" if e.get('phase') else ''
            out.append(
                f"T{e['turn']} [{e['deck']}]{phase_tag} chose {e['chosen']} "
                f"from [{cands}] — {e['reason']}"
            )
        return out

    def clear(self) -> None:
        self.entries.clear()
