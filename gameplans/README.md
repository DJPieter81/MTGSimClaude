# gameplans/

Declarative per-deck game plans (PLANNING_REFERENCE.md §9 #6).

Each deck has a `<key>.json` describing:

- `mulligan_keys`: tag combinations to keep on a 7/6/5-card hand
- `goal_sequence`: ordered list of phase goals (e.g. "T1: deploy threat", "T2: strip hate", "T3: go off")
- `card_roles`: per-card-tag semantic labels (threat, removal, combo, etc.)
- `win_conditions`: tagged cards that end the game
- `notes`: free-form strategy summary

These are **declarative** — no Python code. A future `GoalEngine` (§9 #6)
reads them to drive strategy decisions without per-deck functions.

This directory currently holds stubs for the 7 full-strategy combo/lock
decks most likely to benefit from phase-aware play: storm, oops,
doomsday, reanimator, lands, prison, show. Adding more decks is just
a matter of authoring more JSON files — no engine edits required.

## Schema

```json
{
  "key": "storm",
  "name": "Storm (ANT)",
  "mulligan_keys": {
    "7": ["rituals>=2 AND (itutor OR tendrils)", "led AND rituals>=1"],
    "6": ["rituals>=1 AND (tendrils OR itutor)"],
    "5": ["has_any_kill_path"]
  },
  "goal_sequence": [
    {"phase": "setup",  "turns": [1, 2], "action": "cantrip + land drop; tseize if hate detected"},
    {"phase": "combo",  "turns": [3, 99], "action": "execute ritual chain → tendrils"}
  ],
  "card_roles": {
    "darkrit":  "ritual",
    "cabalrit": "ritual",
    "led":      "burst_mana",
    "itutor":   "tutor",
    "tendrils": "finisher",
    "ts":       "discard",
    "bs":       "cantrip",
    "ponder":   "cantrip",
    "adnauseam":"self_assembler",
    "pif":      "recursion",
    "vos":      "protection",
    "fow":      "protection",
    "fluster":  "protection"
  },
  "win_conditions": ["tendrils", "adnauseam", "pif"],
  "notes": "ANT Storm — goldfish T2-T3 with rituals + LED, protect with Veil/Flusterstorm/FoW."
}
```

## Validation

```bash
python3 -c "
import json, glob
for f in sorted(glob.glob('gameplans/*.json')):
    with open(f) as fh:
        d = json.load(fh)
    assert 'key' in d and 'goal_sequence' in d, f'missing keys in {f}'
    print(f'{d[\"key\"]:15s} — {len(d[\"goal_sequence\"])} phases, {len(d.get(\"card_roles\",{}))} tagged cards')
"
```

## Integration (future)

A `GoalEngine` class would:
1. Load the matching `gameplans/<deck>.json` on game start.
2. On each turn, pick the phase whose `turns` range matches `gs.turn`.
3. Translate the phase's `action` string into concrete strategy calls.

This replaces per-deck strategy functions for the decks with json plans.
For now the plans are informational — strategies still live in `engine.py`.
