"""Game-state feature extractor + trace collector.

Used by the neural-pivot prototype:
- `encode_state` — fixed-shape feature dict for one (gs, player, opponent) tuple.
  Reuses HandBelief from bhi.py and combat_clock from clock.py.
- `encode_state_vec` — same data as a fixed-order list[float] for NN input.
- `FEATURE_ORDER` — canonical column order so vectors stay aligned.
- `collect()` context manager + `record(...)` — opt-in trace emission.
  Strategies call `record(...)` at every decision gate; when no collector is
  active the call is a no-op so heuristic-only paths pay nothing.
"""

from __future__ import annotations
import contextlib
from typing import Any

# ── Canonical feature order (≈40 features, kept stable across versions) ─────
FEATURE_ORDER = [
    "turn",
    "life_me", "life_opp", "life_diff",
    "hand_me", "hand_opp",
    "mana_available",
    "lands_me", "lands_opp",
    "land_B", "land_U", "land_R", "land_G", "land_W", "land_generic",
    "spells_cast_this_turn",
    "tag_petal", "tag_chrome_mox", "tag_led", "tag_darkrit",
    "tag_cantrip", "tag_tutor", "tag_tendrils", "tag_vos",
    "bhi_p_free_counter", "bhi_p_counter", "bhi_p_removal", "bhi_p_burn",
    "combat_clock",
    "opp_creature_power_total",
    "opp_creature_count",
    "veil_active", "trinisphere_active", "thalia_on_board",
    "chalice_x",
    "mc_combo", "mc_aggro", "mc_prison", "mc_mirror", "mc_fast_combo",
    "is_p1",
]

_collectors: list[list[dict[str, Any]]] = []


def _color_buckets(player) -> dict[str, int]:
    """Count untapped lands producing each colour."""
    out = {"B": 0, "U": 0, "R": 0, "G": 0, "W": 0, "generic": 0}
    for land in player.lands:
        if land.tapped:
            continue
        produced = land.effective_produces()
        if not produced:
            out["generic"] += 1
        else:
            for col in produced:
                if col in out:
                    out[col] += 1
    return out


def _bhi_features(gs, opponent) -> dict[str, float]:
    """Pull HandBelief probabilities; cache via gs._bhi_p2 / gs._bhi_p1."""
    try:
        from bhi import HandBelief
    except Exception:
        return {"p_free_counter": 0.0, "p_counter": 0.0,
                "p_removal": 0.0, "p_burn": 0.0}

    cache_key = "_bhi_p2" if opponent is gs.p2 else "_bhi_p1"
    cached = getattr(gs, cache_key, None)
    deck_key = gs.p2_deck if opponent is gs.p2 else gs.p1_deck
    hand_size = len(opponent.hand)
    if (cached is None or cached.get("deck") != deck_key
            or cached.get("hand_size") != hand_size
            or cached.get("turn") != gs.turn):
        belief = HandBelief(deck_key,
                            cards_drawn=7 + max(0, gs.turn - 1),
                            cards_in_hand=hand_size)
        setattr(gs, cache_key, {"deck": deck_key, "hand_size": hand_size,
                                "turn": gs.turn, "belief": belief})
    else:
        belief = cached["belief"]
    return {
        "p_free_counter": float(getattr(belief, "p_free_counter", 0.0)),
        "p_counter": float(getattr(belief, "p_counter", 0.0)),
        "p_removal": float(getattr(belief, "p_removal", 0.0)),
        "p_burn": float(getattr(belief, "p_burn", 0.0)),
    }


def _matchup_onehot(gs) -> dict[str, int]:
    try:
        from config import MatchupCategory as MC
    except Exception:
        return {k: 0 for k in ("combo", "aggro", "prison", "mirror", "fast_combo")}
    return {
        "combo":      int(MC.is_combo(gs)),
        "aggro":      int(MC.is_aggro(gs)),
        "prison":     int(getattr(MC, "is_prison", lambda _g: False)(gs)),
        "mirror":     int(MC.is_mirror(gs)),
        "fast_combo": int(getattr(gs, "matchup", "")
                         in getattr(MC, "FAST_COMBO", set())),
    }


def _combat_clock(player, opponent) -> int:
    try:
        from clock import combat_clock
    except Exception:
        return 99
    eff_pow = sum(c.power for c in opponent.creatures
                  if not c.summoning_sick and not c.tapped)
    if eff_pow <= 0:
        return 99
    return combat_clock(player.life, eff_pow)


def encode_state(gs, player, opponent) -> dict[str, float]:
    """Fixed-shape feature dict — keys match FEATURE_ORDER."""
    colours = _color_buckets(player)
    bhi = _bhi_features(gs, opponent)
    mc = _matchup_onehot(gs)
    hand_tags = [c.tag for c in player.hand]

    def tag_count(t: str) -> int:
        return sum(1 for c in player.hand if c.tag == t)

    cantrip_count = sum(1 for c in player.hand
                        if c.tag in ("bs", "ponder", "probe"))
    tutor_count = sum(1 for c in player.hand
                      if c.tag in ("burning_wish", "infernal"))

    mana_avail = 0
    try:
        mana_avail = player.available_mana_count()
    except Exception:
        mana_avail = sum(1 for l in player.lands if not l.tapped)

    opp_power = sum(c.power for c in opponent.creatures
                    if not c.summoning_sick and not c.tapped)

    feats = {
        "turn": gs.turn,
        "life_me": player.life,
        "life_opp": opponent.life,
        "life_diff": player.life - opponent.life,
        "hand_me": len(player.hand),
        "hand_opp": len(opponent.hand),
        "mana_available": mana_avail,
        "lands_me": len(player.lands),
        "lands_opp": len(opponent.lands),
        "land_B": colours["B"],
        "land_U": colours["U"],
        "land_R": colours["R"],
        "land_G": colours["G"],
        "land_W": colours["W"],
        "land_generic": colours["generic"],
        "spells_cast_this_turn": getattr(player, "spells_cast_this_turn", 0),
        "tag_petal": tag_count("petal"),
        "tag_chrome_mox": tag_count("chrome_mox"),
        "tag_led": tag_count("led"),
        "tag_darkrit": tag_count("darkrit"),
        "tag_cantrip": cantrip_count,
        "tag_tutor": tutor_count,
        "tag_tendrils": tag_count("tendrils"),
        "tag_vos": tag_count("vos"),
        "bhi_p_free_counter": bhi["p_free_counter"],
        "bhi_p_counter": bhi["p_counter"],
        "bhi_p_removal": bhi["p_removal"],
        "bhi_p_burn": bhi["p_burn"],
        "combat_clock": _combat_clock(player, opponent),
        "opp_creature_power_total": opp_power,
        "opp_creature_count": len(opponent.creatures),
        "veil_active": int(getattr(gs, "veil_active", False)),
        "trinisphere_active": int(getattr(gs, "trinisphere_active", False)),
        "thalia_on_board": int(getattr(gs, "thalia_on_board", False)),
        "chalice_x": -1 if gs.chalice_x is None else int(gs.chalice_x),
        "mc_combo": mc["combo"],
        "mc_aggro": mc["aggro"],
        "mc_prison": mc["prison"],
        "mc_mirror": mc["mirror"],
        "mc_fast_combo": mc["fast_combo"],
        "is_p1": int(player is gs.p1),
    }
    # Sanity: every key in FEATURE_ORDER must be present (fail fast on schema drift).
    missing = [k for k in FEATURE_ORDER if k not in feats]
    if missing:
        raise RuntimeError(f"state_encoder missing keys: {missing}")
    return feats


def encode_state_vec(gs, player, opponent) -> list[float]:
    """Same as encode_state but as a fixed-order list[float] for NN input."""
    f = encode_state(gs, player, opponent)
    return [float(f[k]) for k in FEATURE_ORDER]


# ── Trace collector ─────────────────────────────────────────────────────────

@contextlib.contextmanager
def collect():
    """Context manager: yields a list that captures every record() call inside."""
    rows: list[dict[str, Any]] = []
    _collectors.append(rows)
    try:
        yield rows
    finally:
        _collectors.pop()


def record(decision_type: str, decision_value: Any, gs, player, opponent,
           **extras) -> None:
    """Append one row to the active collector. No-op when no collector active."""
    if not _collectors:
        return
    _collectors[-1].append({
        "decision_type": decision_type,
        "decision_value": decision_value,
        "state": encode_state(gs, player, opponent),
        **extras,
    })


def record_q(decision_type: str, candidates_with_apply: list,
             gs, player, opponent,
             K: int = 3, max_turns_remaining: int = 5,
             rng_seed_base: int = 0, **extras) -> None:
    """Lever 5 — emit `(state, action, rollout_outcome)` rows for each
    candidate via cloned-state rollouts. No-op when no collector active.

    `candidates_with_apply` is a list of `(action_tag, apply_fn)` where
    `apply_fn(cgs, cp, co)` mutates the clone with the candidate's effect.
    For each candidate we clone K times, apply, rollout, and emit one row
    per rollout with the binary outcome (1 = protagonist wins, 0 = loses).

    Strategy continues with its heuristic decision after this call returns
    — `record_q` is observation-only.
    """
    if not _collectors:
        return
    from gamestate_clone import clone_game_state
    from rollout import rollout_to_end
    state_features = encode_state(gs, player, opponent)
    proto_label = 1 if player is gs.p1 else 0
    for ci, (action_tag, apply_fn) in enumerate(candidates_with_apply):
        for k in range(K):
            try:
                clone = clone_game_state(gs)
                cp = clone.p1 if player is gs.p1 else clone.p2
                co = clone.p2 if opponent is gs.p2 else clone.p1
                apply_fn(clone, cp, co)
                outcome = rollout_to_end(
                    clone,
                    max_turns_remaining=max_turns_remaining,
                    rng_seed=rng_seed_base * 1000 + ci * 100 + k,
                )
                won = 1 if outcome == proto_label else 0
                _collectors[-1].append({
                    "decision_type": f"q_{decision_type}",
                    "decision_value": action_tag,
                    "rollout_idx": k,
                    "rollout_won": won,
                    "state": state_features,
                    **extras,
                })
            except Exception:
                # Skip this rollout silently — we don't want training data
                # generation to crash the game.
                continue
