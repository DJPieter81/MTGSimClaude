"""Gameplan stub – provides imports expected by engine.py.

The full gameplan module is not yet implemented; this stub lets the
simulator run with gs.opp_goal = None for all matchups.
"""

from enum import Enum, auto


class Goal(Enum):
    AGGRO = auto()
    CONTROL = auto()
    COMBO = auto()


GAMEPLANS: dict = {}


def assess(gs, turn):
    """Return a board assessment (placeholder)."""
    return None


def active_goal(plan, board_assessment):
    """Return the active goal given a plan and assessment (placeholder)."""
    return None
