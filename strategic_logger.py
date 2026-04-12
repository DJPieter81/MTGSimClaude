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

    __slots__ = ('enabled', 'entries')

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.entries: list[dict] = []

    def log_decision(self, turn: int, deck: str, candidates, chosen, reason: str) -> None:
        if not self.enabled:
            return
        self.entries.append({
            'turn': turn,
            'deck': deck,
            'candidates': list(candidates),
            'chosen': chosen,
            'reason': reason,
        })

    def dump(self) -> list[str]:
        """Flatten entries into log_lines-compatible strings."""
        out = []
        for e in self.entries:
            cands = ','.join(str(c) for c in e['candidates'])
            out.append(
                f"T{e['turn']} [{e['deck']}] chose {e['chosen']} "
                f"from [{cands}] — {e['reason']}"
            )
        return out

    def clear(self) -> None:
        self.entries.clear()
