"""LLM gate advisor for `_strategy_tes` — Phase 2 of the neural pivot.

Three sparse strategic gates are delegated to Claude:
  1. should_go_off(gs, p, o)        → bool
  2. pick_wish_target(gs, p, o)     → "tendrils" | "empty"
  3. worth_echo_line(gs, p, o)      → bool

Each call uses the Anthropic SDK with:
  * model = `claude-opus-4-7` (per `claude-api` skill default)
  * adaptive thinking + low effort (we want a fast bounded decision)
  * structured outputs via `messages.parse()` + Pydantic
  * top-level `cache_control={"type": "ephemeral"}` so the static prefix
    (system + tool-free template + examples) is served from cache after
    the first call

A `LOG` JSONL is appended to per call (request, response, parsed) for
offline audit and replay.
"""

from __future__ import annotations
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

try:
    import anthropic
    from pydantic import BaseModel, Field
    _SDK_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _SDK_AVAILABLE = False
    _IMPORT_ERROR = _e

from state_encoder import encode_state

# ── Config ────────────────────────────────────────────────────────────────
MODEL_ID = "claude-opus-4-7"
LOG_DIR = Path("results/neural_logs")

_client: Optional["anthropic.Anthropic"] = None


def _client_singleton() -> "anthropic.Anthropic":
    global _client
    if _client is None:
        if not _SDK_AVAILABLE:
            raise RuntimeError(
                f"anthropic SDK not importable: {_IMPORT_ERROR!r}. "
                "Run: pip install anthropic pydantic"
            )
        _client = anthropic.Anthropic()
    return _client


# ── Pydantic schemas (structured outputs) ─────────────────────────────────

class GoOffDecision(BaseModel):
    decision: bool = Field(
        description="True iff TES should attempt to go off this turn.")
    rationale: str = Field(
        description="One-sentence reason, ≤ 25 words.",
        max_length=300)
    confidence: float = Field(
        description="Confidence 0.0–1.0.", ge=0.0, le=1.0)


class WishTargetDecision(BaseModel):
    target: Literal["tendrils", "empty"] = Field(
        description="'tendrils' for Tendrils of Agony, 'empty' for "
                    "Empty the Warrens.")
    rationale: str = Field(max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)


class EchoLineDecision(BaseModel):
    decision: bool = Field(
        description="True iff TES should crack LED to flashback Echo of Eons.")
    rationale: str = Field(max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)


# ── Prompt templates ──────────────────────────────────────────────────────

# The system block is intentionally large + deterministic so the prefix
# is cacheable. State (the volatile part) goes in the user block.

_TES_DOCTRINE = """\
You are an expert Magic: the Gathering Legacy player advising a simulator
playing The Epic Storm (TES). TES is an aggressive cantrip-driven storm
combo deck that wins by casting Tendrils of Agony for lethal storm count
or, against decks without lifegain / hand attack, by Empty the Warrens
for a token swarm.

Key cards in hand at decision time:
  - Lotus Petal, Chrome Mox, Lion's Eye Diamond (LED) — fast mana
  - Dark Ritual, Rite of Flame, Desperate Ritual, Seething Song — rituals
  - Brainstorm, Ponder, Gitaxian Probe — cantrips
  - Burning Wish — fetches a sorcery from the sideboard (Tendrils, Empty,
    Echo of Eons, etc.)
  - Infernal Tutor — hellbent, fetches any card
  - Veil of Summer — protect the chain from blue counters
  - Ad Nauseam — draw cards, lose life equal to CMC each
  - Echo of Eons — both players draw 7 (flashback for 3); used for a
    "no-mana, redraw a fresh 7" reset when LED is in play

Storm count below approximates spells cast this turn AND fast-mana cracks
(simplification — real Storm only counts spells, not activations like
Petal sac).

Lethal Tendrils math: damage = 2 * (storm + 1). With storm 4 you do 10
damage; storm 9 → 20 damage.

The Burn matchup is a race. Burn typically kills on turn 4 with Eidolon
of the Great Revel on board — Eidolon punishes every cantrip we cast for
2 damage. So later turns are MORE expensive for us, not cheaper.

You will return ONLY structured JSON matching the requested schema.
Be concise. Confidence is a calibrated estimate of correctness."""


_GO_OFF_INSTR = """\
DECISION: Should TES try to go off (cast the kill) this turn?

Going off means burning fast mana, chaining rituals, and resolving
Tendrils / Empty for the kill. Going off into a counter loses the game.

Consider:
  * Lethal-or-near-lethal storm achievable from current hand?
  * Is Veil of Summer ALREADY active, or castable for 1 mana to protect?
  * Does the opponent likely have a free counter (FoW / FoN / Daze)?
    bhi_p_free_counter > 0.45 is dangerous.
  * Race position: are we likely to die before next turn?
  * Trinisphere / Thalia active? If yes, the chain costs much more mana.

Conservative bias when:
  * proj_storm < 4 AND we're not desperate (life > 12, opp_clock > 2)
  * opp likely has 2+ free counters

Aggressive bias when:
  * Veil of Summer already up
  * Lethal Tendrils available right now
  * Life ≤ 10 (death is imminent — last chance)"""


_WISH_INSTR = """\
DECISION: Burning Wish target — Tendrils of Agony or Empty the Warrens?

Tendrils: 2 black, 2 generic; deals 2 * (storm + 1) damage.
Empty the Warrens: 1 red, 3 generic; creates 2 * (storm + 1) goblin tokens
that attack the next turn.

Pick Tendrils when:
  * Damage suffices to kill opponent (proj_tendrils_dmg >= opponent.life)
  * Opponent has no Leyline of Sanctity / Worship analog

Pick Empty when:
  * Tendrils does NOT lethal AND
  * Opponent is fair-non-blue (Mardu, D&T, Boros, Eldrazi, Mono-Black,
    Prison, Lands) — these decks struggle to deal with a goblin swarm
  * mana >= 4 (Empty costs 4)

Default to Tendrils when uncertain — it ends the game now."""


_ECHO_INSTR = """\
DECISION: Crack LED + flashback Echo of Eons for a fresh 7-card hand?

Echo line:
  * LED → +3 mana, dump current hand to GY (loses cards in hand)
  * Echo of Eons flashback (3 generic) → both players shuffle GY+hand
    into library, draw 7
  * Now you're hellbent + 7 fresh cards + 3 mana available

Take the line when:
  * Current storm < 5 AND
  * Current hand can't combo this turn AND
  * Opponent's fresh 7 is unlikely to swing the game (e.g. Burn just
    digs into more burn — usually not lethal next turn)

Skip when:
  * You can already kill this turn (don't risk decking yourself)
  * Opponent is the kind of deck that benefits massively from a redraw
    (Show and Tell, Reanimator with bin already loaded)"""


def _user_block(state: dict[str, Any], extras: dict[str, Any]) -> str:
    """Compact game-state JSON for the volatile part of the prompt."""
    payload = {"state": state, "extras": extras}
    return ("Current game state (numeric features + decision-specific "
            "extras):\n```json\n" + json.dumps(payload, sort_keys=True,
                                               indent=0) + "\n```")


def _log(record: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{datetime.utcnow():%Y%m%d}.jsonl"
    record["t"] = time.time()
    with path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _call_parse(system_blocks: list[dict[str, Any]],
                user_text: str,
                schema: type[BaseModel],
                gate: str) -> Optional[BaseModel]:
    """Call client.messages.parse with caching; return parsed object or None."""
    client = _client_singleton()
    try:
        resp = client.messages.parse(
            model=MODEL_ID,
            max_tokens=512,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            system=system_blocks,
            messages=[{"role": "user", "content": user_text}],
            output_format=schema,
        )
    except Exception as exc:  # pragma: no cover — network / API path
        _log({"gate": gate, "error": repr(exc)})
        return None

    parsed = resp.parsed_output
    _log({
        "gate": gate,
        "model": MODEL_ID,
        "user_tokens_uncached": getattr(resp.usage, "input_tokens", None),
        "cache_read": getattr(resp.usage, "cache_read_input_tokens", None),
        "cache_write": getattr(resp.usage, "cache_creation_input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
        "parsed": parsed.model_dump() if parsed else None,
        "stop_reason": resp.stop_reason,
    })
    return parsed


def _system_for(instruction: str) -> list[dict[str, Any]]:
    """Cache the doctrine + per-gate instruction together."""
    return [
        {"type": "text", "text": _TES_DOCTRINE},
        {
            "type": "text",
            "text": instruction,
            "cache_control": {"type": "ephemeral"},
        },
    ]


# ── Public API — three gates ──────────────────────────────────────────────

def should_go_off(gs, player, opponent, **gate_extras) -> Optional[bool]:
    """Return True/False to override the heuristic; None on API error."""
    state = encode_state(gs, player, opponent)
    user = _user_block(state, gate_extras)
    parsed = _call_parse(_system_for(_GO_OFF_INSTR), user,
                         GoOffDecision, gate="go_off")
    return None if parsed is None else parsed.decision


def pick_wish_target(gs, player, opponent,
                     **gate_extras) -> Optional[Literal["tendrils", "empty"]]:
    """Return 'tendrils' or 'empty'; None on API error."""
    state = encode_state(gs, player, opponent)
    user = _user_block(state, gate_extras)
    parsed = _call_parse(_system_for(_WISH_INSTR), user,
                         WishTargetDecision, gate="wish_target")
    return None if parsed is None else parsed.target


def worth_echo_line(gs, player, opponent, **gate_extras) -> Optional[bool]:
    """Return True/False; None on API error."""
    state = encode_state(gs, player, opponent)
    user = _user_block(state, gate_extras)
    parsed = _call_parse(_system_for(_ECHO_INSTR), user,
                         EchoLineDecision, gate="echo_line")
    return None if parsed is None else parsed.decision


# ── Smoke test (manual) ──────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover
    import random
    from sim import run_game
    random.seed(11)
    print("[neural_gates] Running 1 game with seed=11 to capture a state...")
    r = run_game("tes", "burn")
    print(f"  → winner={r.winner}, kill={r.kill_turn}, len={r.game_length}")
    print("[neural_gates] (no API call here — just import smoke)")
