"""
card_validation.py — Card stat validation for MTGSimClaude

Validates every card built by registered deck constructors against a reference
table of known correct stats (power, toughness, cmc, keyword abilities).
Returns error strings for any mismatches.

Usage:
    from card_validation import validate_all_decks
    errors = validate_all_decks()
    for e in errors:
        print(e)
"""

from typing import List, Dict, Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN_CARDS — reference stats for frequently played Legacy cards
#
# Each entry is a dict of attributes to check. Only listed attributes are
# validated; unlisted attributes are silently ignored (allows deck-specific
# flavouring such as tag, is_combo_piece, etc.).
#
# Attribute keys match Card dataclass field names in rules.py:
#   base_power, base_toughness, cmc, flying, haste, trample,
#   deathtouch, lifelink, vigilance, indestructible, flash, reach
#
# Real-card references: mtg.wtf / Scryfall oracle text (April 2026).
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_CARDS: Dict[str, Dict[str, Any]] = {
    # ── Burn / Red aggro ───────────────────────────────────────────────────
    "Goblin Guide": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 1,
        "haste": True,
        "flying": False,
    },
    "Monastery Swiftspear": {
        "base_power": 1,
        "base_toughness": 2,
        "cmc": 1,
        "haste": True,
        "flying": False,
    },
    "Eidolon of the Great Revel": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 2,
        "flying": False,
    },
    "Ragavan, Nimble Pilferer": {
        "base_power": 2,
        "base_toughness": 1,
        "cmc": 1,
        "haste": True,
        "flying": False,
    },

    # ── Blue tempo creatures ────────────────────────────────────────────────
    # Delver of Secrets is a 1/1 with NO flying while unflipped.
    # Flying only applies after the Insectile Aberration flip (not modelled).
    "Delver of Secrets": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
        "flying": False,
    },
    "Snapcaster Mage": {
        "base_power": 2,
        "base_toughness": 1,
        "cmc": 2,
        "flash": True,
        "flying": False,
    },
    "Brazen Borrower": {
        "base_power": 3,
        "base_toughness": 1,
        "cmc": 3,
        "flash": True,
        "flying": True,
    },
    "Murktide Regent": {
        # Base stats (0 exiled instants/sorceries). Sim uses 3/3 as baseline
        # since delve fires at cast time, so we check what the deck actually sets.
        # Delve makes it variable — we only enforce cmc and flying here.
        "cmc": 7,
        "flying": True,
    },

    # ── Infect creatures ────────────────────────────────────────────────────
    "Glistener Elf": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
        "flying": False,
    },
    "Blighted Agent": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 2,
        "flying": False,
    },

    # ── Mana dorks / support ────────────────────────────────────────────────
    "Noble Hierarch": {
        "base_power": 0,
        "base_toughness": 1,
        "cmc": 1,
        "flying": False,
    },
    "Llanowar Elves": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Elvish Mystic": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Heritage Druid": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Elvish Visionary": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Wirewood Symbiote": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Quirion Ranger": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Dryad Arbor": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 0,
    },
    "Simian Spirit Guide": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 3,
    },

    # ── White weenie / DnT ─────────────────────────────────────────────────
    "Thalia, Guardian of Thraben": {
        "base_power": 2,
        "base_toughness": 1,
        "cmc": 2,
        "flying": False,
    },
    "Stoneforge Mystic": {
        "base_power": 1,
        "base_toughness": 2,
        "cmc": 2,
        "flying": False,
    },
    "Recruiter of the Guard": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 3,
    },
    "Flickerwisp": {
        "base_power": 3,
        "base_toughness": 1,
        "cmc": 3,
        "flying": True,
    },
    "Skyclave Apparition": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 3,
        "flying": False,
    },
    "Sanctum Prelate": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 3,
    },
    "Phelia, Exuberant Shepherd": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 2,
    },
    "Solitude": {
        "base_power": 3,
        "base_toughness": 2,
        "cmc": 5,
        "flying": True,
        "lifelink": True,
    },

    # ── Goblins ─────────────────────────────────────────────────────────────
    "Goblin Lackey": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
        "haste": False,
    },
    "Goblin Matron": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 3,
    },
    "Goblin Warchief": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 3,
        "haste": True,
    },
    "Goblin Ringleader": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 4,
    },
    "Muxus, Goblin Grandee": {
        "base_power": 4,
        "base_toughness": 4,
        "cmc": 6,
    },
    "Skirk Prospector": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Goblin Cratermaker": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 2,
    },

    # ── Elves ────────────────────────────────────────────────────────────────
    "Allosaurus Shepherd": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 1,
    },
    "Nettle Sentinel": {
        "base_power": 2,
        "base_toughness": 2,
        "cmc": 1,
    },
    "Craterhoof Behemoth": {
        "base_power": 5,
        "base_toughness": 5,
        "cmc": 8,
        "trample": True,
        "haste": True,
    },

    # ── Combo / reanimation / control ───────────────────────────────────────
    "Griselbrand": {
        "base_power": 7,
        "base_toughness": 7,
        "cmc": 8,
        "flying": True,
        "lifelink": True,
        "deathtouch": False,
    },
    "Emrakul, the Aeons Torn": {
        "base_power": 15,
        "base_toughness": 15,
        "cmc": 15,
        "flying": True,
        "trample": True,
        "haste": True,
    },
    "Atraxa, Grand Unifier": {
        "base_power": 7,
        "base_toughness": 7,
        "cmc": 7,
        "flying": True,
        "lifelink": True,
        "deathtouch": True,
        "vigilance": True,
    },
    "Archon of Cruelty": {
        "base_power": 6,
        "base_toughness": 6,
        "cmc": 8,
        "flying": True,
        "lifelink": True,
        "deathtouch": False,
    },
    "Thassa's Oracle": {
        "base_power": 1,
        "base_toughness": 3,
        "cmc": 2,
    },
    "Street Wraith": {
        "base_power": 3,
        "base_toughness": 4,
        "cmc": 5,
    },
    "Thought-Knot Seer": {
        "base_power": 4,
        "base_toughness": 4,
        "cmc": 4,
    },

    # ── Midrange / value ────────────────────────────────────────────────────
    "Orcish Bowmasters": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 2,
        "flash": True,
    },
    "Baleful Strix": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 2,
        "flying": True,
        "deathtouch": True,
    },
    "Dauthi Voidwalker": {
        "base_power": 3,
        "base_toughness": 2,
        "cmc": 2,
    },
    "Grief": {
        "base_power": 3,
        "base_toughness": 2,
        "cmc": 5,
        "flying": False,
    },
    "Fury": {
        "base_power": 3,
        "base_toughness": 3,
        "cmc": 5,
        "trample": True,
    },
    "Endurance": {
        "base_power": 3,
        "base_toughness": 4,
        "cmc": 3,
        "reach": True,
    },
    "Painter's Servant": {
        "base_power": 1,
        "base_toughness": 3,
        "cmc": 2,
    },
    "Narcomoeba": {
        "base_power": 1,
        "base_toughness": 1,
        "cmc": 2,
        "flying": True,
    },

    # ── Dragon's Rage Channeler ─────────────────────────────────────────────
    # Base stats (no delirium). Delirium → 3/3 is a continuous effect in game.
    "Dragon's Rage Channeler": {
        "cmc": 1,
        # base_power can be 1 or 3 depending on delirium modelling — not enforced
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN_ALT_COSTS — notes on alternate cost requirements for specific cards.
#
# These are informational and used for documentation / future validation;
# the current sim encodes them differently (life_cost, free_cast_if_blue, etc.)
# so we don't generate errors for them here.
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_ALT_COSTS: Dict[str, str] = {
    "Fireblast": (
        "Alternate cost: sacrifice two Mountains (basic Mountain permanents). "
        "Cannot be paid with non-Mountain red sources. CMC=6."
    ),
    "Invigorate": (
        "Alternate cost: opponent gains 3 life, castable for free only if "
        "opponent controls a Forest (CR 702.35). CMC=3."
    ),
    "Force of Will": (
        "Alternate cost: pay 1 life and exile a blue card from hand. "
        "Requires a blue card in hand to use the free cast. CMC=5."
    ),
    "Force of Negation": (
        "Alternate cost: exile a blue card from hand. "
        "Only free on opponent's turn (CR 702.?). CMC=3."
    ),
    "Grief": (
        "Evoke cost: exile a black card from hand. "
        "Creature is sacrificed at end step if evoked."
    ),
    "Fury": (
        "Evoke cost: exile a red card from hand. "
        "Creature is sacrificed at end step if evoked."
    ),
    "Endurance": (
        "Evoke cost: exile a green card from hand. "
        "Creature is sacrificed at end step if evoked."
    ),
    "Solitude": (
        "Evoke cost: exile a white card from hand. "
        "Creature is sacrificed at end step if evoked."
    ),
    "Snuff Out": (
        "Alternate cost: pay 4 life instead of {3}{B}, only if you control a Swamp."
    ),
    "Mutagenic Growth": (
        "Alternate cost: pay 2 life instead of {G} (Phyrexian mana {G/P})."
    ),
    "Daze": (
        "Alternate cost: return an Island you control to hand instead of paying {1}{U}."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_card(deck_key: str, card, seen: set) -> List[str]:
    """
    Check a single Card object against KNOWN_CARDS.

    Returns a list of error strings (empty if card is fine or not in KNOWN_CARDS).
    `seen` tracks which (deck_key, card_name) pairs have already been reported so
    duplicates in a deck don't produce repeated errors.
    """
    name = card.name
    if name not in KNOWN_CARDS:
        return []

    dedup_key = (deck_key, name)
    if dedup_key in seen:
        return []
    seen.add(dedup_key)

    ref = KNOWN_CARDS[name]
    errors: List[str] = []

    for attr, expected in ref.items():
        actual = getattr(card, attr, None)
        if actual is None:
            # Attribute doesn't exist on this card — skip silently (non-creature cards
            # won't have base_power/base_toughness fields that matter)
            continue
        if actual != expected:
            errors.append(
                f"[{deck_key}] {name}.{attr} = {actual!r}, expected {expected!r}"
            )

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate_deck(deck_key: str) -> List[str]:
    """
    Validate all cards in a single deck.

    Parameters
    ----------
    deck_key : str
        The registered deck key (e.g. 'burn', 'ur_delver').

    Returns
    -------
    List[str]
        Error strings for each stat mismatch found. Empty list = all good.
    """
    from deck_registry import get_registry

    registry = get_registry()
    meta = registry.get(deck_key)
    if meta is None:
        return [f"[{deck_key}] Deck key not found in registry"]

    try:
        deck = meta["make_deck"]()
    except Exception as exc:
        return [f"[{deck_key}] make_deck() raised {type(exc).__name__}: {exc}"]

    seen: set = set()
    errors: List[str] = []
    for card in deck:
        errors.extend(_check_card(deck_key, card, seen))

    return errors


def validate_all_decks(decks: Optional[List[str]] = None) -> List[str]:
    """
    Validate every registered deck (or a specific subset).

    Parameters
    ----------
    decks : list[str] | None
        If provided, only validate these deck keys. Otherwise validates all.

    Returns
    -------
    List[str]
        All error strings found across every deck, sorted by deck key then card name.
        An empty list means no mismatches were detected.
    """
    from deck_registry import get_all_keys

    keys = decks if decks is not None else get_all_keys()
    all_errors: List[str] = []

    for key in sorted(keys):
        all_errors.extend(validate_deck(key))

    return all_errors


def print_validation_report(decks: Optional[List[str]] = None) -> int:
    """
    Run validation and print a human-readable report.

    Returns the number of errors found (0 = clean).
    """
    errors = validate_all_decks(decks)
    if not errors:
        print("Card validation: all decks OK (no stat mismatches found).")
    else:
        print(f"Card validation: {len(errors)} error(s) found:")
        for e in errors:
            print(f"  {e}")
    return len(errors)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    specific = sys.argv[1:] if len(sys.argv) > 1 else None
    n = print_validation_report(specific)
    sys.exit(0 if n == 0 else 1)
