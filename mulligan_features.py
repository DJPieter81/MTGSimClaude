"""Encode an opening hand into a fixed-shape feature vector for the
mulligan Q-net (Lever 6 of the neural pivot).

The features must be derivable from a list of `Card` objects + `matchup`
+ `deck_key` only — no `GameState` is available at mulligan time.
"""

from __future__ import annotations
from typing import List, Sequence

# ── Stable feature order (append-only). Don't reorder — q-net checkpoints
#    are tied to this layout. ────────────────────────────────────────────
HAND_FEATURE_ORDER = [
    "hand_size",                  # 6 or 7 (mull state)
    "n_lands",
    "n_basic_lands",
    "n_fetch_lands",
    "n_dual_lands",
    "n_creatures",
    "n_cantrips",                 # bs / ponder / probe / pre
    "n_counters",                 # any counterspell
    "n_free_counters",            # fow / fon / daze
    "n_removal",
    "n_combo_pieces",
    "n_win_conditions",
    "n_burn",                     # bolt / heat / lava spike / etc.
    "n_threats_1cmc",
    "n_threats_2cmc",
    "n_threats_3plus",
    "total_cmc",
    "n_blue_sources",
    "n_red_sources",
    "n_black_sources",
    "n_green_sources",
    "n_white_sources",
    # Matchup category one-hots — keep aligned with state_encoder mc_*.
    "mc_combo",
    "mc_aggro",
    "mc_prison",
    "mc_mirror",
    "mc_fast_combo",
    # Role: 1 if this player will be on the play this game, 0 if on the draw.
    # Mulligan policy genuinely depends on this — on the play you can be more
    # selective; on the draw a slightly worse hand still wins races sometimes.
    "goes_first",
]


_BURN_TAGS = {"bolt", "lavaspike", "rift", "shock", "heat", "shard"}
_CANTRIP_TAGS = {"bs", "ponder", "probe", "pre"}
_FREE_COUNTER_TAGS = {"fow", "fon", "daze"}
_COUNTER_TAGS = {"counter", "veto", "fluster", "fow", "fon", "daze",
                 "memlapse", "spell_pierce"}


def _color_sources(card) -> set[str]:
    """Approximate which colours a land produces."""
    if not card.is_land():
        return set()
    out = set()
    try:
        produced = card.effective_produces()  # may not exist on bare Card
        if produced:
            return set(produced) & {"B", "U", "R", "G", "W"}
    except Exception:
        pass
    # Fallback by name heuristics for common dual / fetch
    name = (card.name or "").lower()
    if "volcanic island" in name: out |= {"U", "R"}
    elif "underground sea" in name: out |= {"U", "B"}
    elif "tropical island" in name: out |= {"U", "G"}
    elif "tundra" in name: out |= {"U", "W"}
    elif "scrubland" in name: out |= {"W", "B"}
    elif "badlands" in name: out |= {"B", "R"}
    elif "taiga" in name: out |= {"R", "G"}
    elif "savannah" in name: out |= {"W", "G"}
    elif "plateau" in name: out |= {"R", "W"}
    elif "bayou" in name: out |= {"B", "G"}
    elif "wasteland" in name: out |= set()  # produces 1
    # Basics
    if "island" in name and "underground" not in name and "volcanic" not in name and "tropical" not in name and "tundra" not in name:
        out.add("U")
    elif "mountain" in name and "wasteland" not in name and "volcanic" not in name and "badlands" not in name:
        out.add("R")
    elif "swamp" in name and "underground" not in name and "scrubland" not in name and "bayou" not in name and "badlands" not in name:
        out.add("B")
    elif "forest" in name and "tropical" not in name and "savannah" not in name and "taiga" not in name and "bayou" not in name:
        out.add("G")
    elif "plains" in name and "tundra" not in name and "scrubland" not in name and "savannah" not in name and "plateau" not in name:
        out.add("W")
    return out


def _matchup_mc(matchup: str) -> dict[str, int]:
    """Use config.MatchupCategory if importable, else default to zero."""
    try:
        from config import MatchupCategory as MC
    except Exception:
        return {k: 0 for k in ("combo", "aggro", "prison", "mirror", "fast_combo")}
    # MC functions take a `gs`-like object with `.matchup`. We pass a stub.
    class _Stub: pass
    stub = _Stub(); stub.matchup = matchup
    return {
        "combo":      int(MC.is_combo(stub)),
        "aggro":      int(MC.is_aggro(stub)),
        "prison":     int(getattr(MC, "is_prison", lambda _g: False)(stub)),
        "mirror":     0,  # mirror needs both decks — unknown at mulligan time
        "fast_combo": int(matchup in getattr(MC, "FAST_COMBO", set())),
    }


def encode_hand(hand: Sequence, matchup: str = "",
                goes_first: bool = True) -> dict[str, float]:
    """Return a fixed-shape feature dict matching HAND_FEATURE_ORDER."""
    counts = {k: 0 for k in HAND_FEATURE_ORDER}
    counts["hand_size"] = len(hand)
    total_cmc = 0
    color_counts: dict[str, int] = {}
    for c in hand:
        if c.is_land():
            counts["n_lands"] += 1
            if getattr(c, "is_basic", False):
                counts["n_basic_lands"] += 1
            elif getattr(c, "is_fetch", False):
                counts["n_fetch_lands"] += 1
            elif getattr(c, "tag", "") == "dual":
                counts["n_dual_lands"] += 1
            for col in _color_sources(c):
                color_counts[col] = color_counts.get(col, 0) + 1
        else:
            cmc = getattr(c, "cmc", 0) or 0
            total_cmc += cmc
            tag = getattr(c, "tag", "")
            if c.is_creature():
                counts["n_creatures"] += 1
                if cmc <= 1: counts["n_threats_1cmc"] += 1
                elif cmc == 2: counts["n_threats_2cmc"] += 1
                else:        counts["n_threats_3plus"] += 1
            if tag in _CANTRIP_TAGS: counts["n_cantrips"] += 1
            if tag in _COUNTER_TAGS: counts["n_counters"] += 1
            if tag in _FREE_COUNTER_TAGS: counts["n_free_counters"] += 1
            if getattr(c, "is_removal", False) and tag not in _FREE_COUNTER_TAGS:
                counts["n_removal"] += 1
            if getattr(c, "is_combo_piece", False):
                counts["n_combo_pieces"] += 1
            if getattr(c, "win_condition", False):
                counts["n_win_conditions"] += 1
            if tag in _BURN_TAGS:
                counts["n_burn"] += 1
    counts["total_cmc"] = total_cmc
    counts["n_blue_sources"]  = color_counts.get("U", 0)
    counts["n_red_sources"]   = color_counts.get("R", 0)
    counts["n_black_sources"] = color_counts.get("B", 0)
    counts["n_green_sources"] = color_counts.get("G", 0)
    counts["n_white_sources"] = color_counts.get("W", 0)
    mc = _matchup_mc(matchup)
    counts["mc_combo"]      = mc["combo"]
    counts["mc_aggro"]      = mc["aggro"]
    counts["mc_prison"]     = mc["prison"]
    counts["mc_mirror"]     = mc["mirror"]
    counts["mc_fast_combo"] = mc["fast_combo"]
    counts["goes_first"] = int(goes_first)
    return counts


def encode_hand_vec(hand: Sequence, matchup: str = "",
                    goes_first: bool = True) -> List[float]:
    f = encode_hand(hand, matchup, goes_first=goes_first)
    return [float(f[k]) for k in HAND_FEATURE_ORDER]
