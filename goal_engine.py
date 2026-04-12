"""
goal_engine.py — Reader for declarative deck gameplans (PLANNING_REFERENCE §9 #6).

Loads `gameplans/<deck>.json` files and exposes simple lookup/dispatch helpers.
No wiring to engine.py yet — this is the data-access layer. A future
adoption step will thread `pick_phase(gs)` into `_strategy_*` functions
so they can branch on declared phase actions.

Usage:

    from goal_engine import GoalEngine

    ge = GoalEngine('storm')                       # loads gameplans/storm.json
    ge.phase_for_turn(1)      → {"phase": "setup",  "turns": [1,2], "action": "..."}
    ge.win_conditions         → ["tendrils", "adnauseam", "pif"]
    ge.card_roles["darkrit"]  → "ritual"
    ge.has_plan               → True   (False if no json exists for this deck)

    # list all decks with gameplans
    GoalEngine.available()    → ["doomsday", "lands", "oops", ...]
"""
from __future__ import annotations

import glob
import json
import os
from typing import Optional


HERE = os.path.dirname(os.path.abspath(__file__))
PLANS_DIR = os.path.join(HERE, 'gameplans')


class GoalEngine:
    """Lazy loader for a single deck's gameplan."""

    __slots__ = ('deck', 'plan', '_path')

    def __init__(self, deck: str):
        self.deck = deck
        self._path = os.path.join(PLANS_DIR, f'{deck}.json')
        self.plan: Optional[dict] = None
        if os.path.exists(self._path):
            with open(self._path) as f:
                self.plan = json.load(f)

    @property
    def has_plan(self) -> bool:
        return self.plan is not None

    @property
    def goal_sequence(self) -> list:
        return self.plan['goal_sequence'] if self.plan else []

    @property
    def win_conditions(self) -> list:
        return self.plan.get('win_conditions', []) if self.plan else []

    @property
    def card_roles(self) -> dict:
        return self.plan.get('card_roles', {}) if self.plan else {}

    @property
    def archetype(self) -> str:
        return self.plan.get('archetype', 'unknown') if self.plan else 'unknown'

    @property
    def mulligan_keys(self) -> dict:
        return self.plan.get('mulligan_keys', {}) if self.plan else {}

    def phase_for_turn(self, turn: int) -> Optional[dict]:
        """Return the goal-sequence entry whose turn range includes `turn`.

        Ranges are `[lo, hi]` inclusive. If multiple phases overlap a turn,
        the first match wins (phases should be ordered by precedence in the
        gameplan).
        """
        for phase in self.goal_sequence:
            turns = phase.get('turns', [1, 99])
            if turns[0] <= turn <= turns[1]:
                return phase
        return None

    def role_of(self, card_tag: str) -> Optional[str]:
        return self.card_roles.get(card_tag)

    @classmethod
    def available(cls) -> list:
        """List deck keys with a gameplan JSON present."""
        return sorted(
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(PLANS_DIR, '*.json'))
            if not p.endswith('README.md')
        )

    def __repr__(self) -> str:
        status = 'loaded' if self.has_plan else 'MISSING'
        return f'<GoalEngine deck={self.deck!r} {status}>'


# ── Smoke test ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    plans = GoalEngine.available()
    print(f"Available gameplans ({len(plans)}):")
    for name in plans:
        ge = GoalEngine(name)
        p1 = ge.phase_for_turn(1)
        p5 = ge.phase_for_turn(5)
        p1_label = p1['phase'] if p1 else '-'
        p5_label = p5['phase'] if p5 else '-'
        print(f"  {ge.archetype:>14}  {name:12}  T1→{p1_label:10}  T5→{p5_label:10}  "
              f"roles={len(ge.card_roles)}  wins={ge.win_conditions}")
    # Missing deck (default path)
    ge = GoalEngine('burn')
    print(f"\nBurn (no plan): has_plan={ge.has_plan} (expected False)")
    assert not ge.has_plan
    print("\nAll GoalEngine reads clean.")
