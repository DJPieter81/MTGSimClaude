---
name: mtg-bo3-replayer
description: Generate interactive Bo3 match replay HTML files from MTG simulation data. Use this skill whenever the user asks to replay a match, generate a play-by-play, debug a specific matchup, save a Bo3 game log, create an HTML replayer, or investigate why a deck wins/loses a specific matchup. Also triggers on "simulate a match", "show me a game between X and Y", "replay", "play-by-play", "Bo3", "best of 3", "game log", "match viewer", or any request to visually step through a simulated MTG match. Use this skill even if the user just says "run a match" or "show me how X beats Y" in the context of MTG sim work. This skill covers the full pipeline from running the sim, capturing action data, and producing a standalone HTML file with collapsible turns, life charts, AI reasoning, and keyboard navigation.
---

# MTG Bo3 Replayer

Generates interactive HTML replays of Bo3 matches from the MTG simulator, with full board state tracking, mulligan decisions with reasoning, strategic narrative, and per-turn play-by-play.

## When to Use

- User wants to watch/debug a specific matchup
- User asks "show me how X beats Y" or "why does X lose to Y"
- User wants a play-by-play or game log
- Debugging sim behavior — verifying strategy code works correctly
- Validating matrix data by spot-checking individual games

## Quick Start

```python
from game_replay import generate_html

# Bo3 replay: protagonist vs opponent
html = generate_html('opponent_deck', seeds=[42, 99, 7], protagonist='my_deck')
with open('output.html', 'w') as f:
    f.write(html)

# CLI equivalent
python3 game_replay.py opponent_deck --pro my_deck --bo3 42 99 7
```

The `protagonist` is always P1. The first argument (`matchup`) is the opponent (P2).

## Choosing Seeds

Seeds control randomization (shuffle, coin flip, draw order). For debugging:
- Use **fixed seeds** for reproducibility: `seeds=[42, 99, 7]`
- For a specific scenario, iterate seeds until you find the pattern:
  ```python
  for s in range(100):
      g = run_one_game('opponent', seed=s, protagonist='deck')
      if g['winner'] == 'DECK' and g['display_turn'] <= 6:
          print(f"Fast win at seed {s}")
  ```

## Output Structure

Single self-contained HTML file (40-100KB) with:

1. **Header** — Match title, series score, protagonist/opponent labels
2. **Game tabs** — Click to switch between games in the Bo3
3. **Mulligan decisions** — Full history of mulled/kept hands with reasoning
4. **Life chart** — SVG line graph tracking both players' life totals
5. **Collapsible turns** — Each turn shows:
   - Hand (pill badges of cards in hand)
   - Plays (numbered steps with category badges + reasoning)
   - Strategic narrative (context-aware commentary)
   - Board state (creatures P/T, lands, artifacts, enchantments, planeswalkers, graveyard)
6. **Keyboard navigation** — ↑↓ to move between turns, Enter to expand/collapse

Read `references/data_model.md` for the full turn data structure.
Read `references/design_system.md` for CSS variables and component patterns.

## Key Features

### Mulligan Tracking

The replayer wraps the keep function to capture every hand seen during London mulligan:
- Mulled hands shown with strikethrough pills + red `✗ MULL` + composition reason
- Kept hands get green analysis box with composition breakdown
- `_explain_hand(hand, deck_key)` analyzes: lands, threats, cantrips, counters, fast mana, combo pieces
- Identifies issues (no lands, flood, no action) and strengths (combo ready, threat+protection)

### Strategic Narrative

`_narrate_turn(td, prev_td, context)` generates per-turn commentary:
- Combo resolution, counter wars, Veil of Summer plays
- Mana denial (Wasteland), hand disruption (Thoughtseize)
- Aggressive combat, cantrip digging, missed land drops
- Only shows when there's something meaningful — no noise on routine turns

### Board State Zones (6 total)

| Zone | Icon | CSS Color | Data field |
|------|------|-----------|------------|
| Creatures | badges with P/T | white | `creatures` / `opp_creatures` |
| Lands | 🌿 | `#7ee787` green | `lands` / `opp_lands` |
| Artifacts | ⚙️ | `#e3b341` gold | `artifacts` / `opp_artifacts` |
| Enchantments | ✨ | `#d2a8ff` purple | `enchantments` / `opp_enchantments` |
| Planeswalkers | 🔮 | `#79c0ff` blue | `planeswalkers` / `opp_planeswalkers` |
| Graveyard | 🪦 | `#6e7681` grey | `graveyard` / `opp_graveyard` |

### Play Categories

Each play is classified into a visual category with a colored badge:

| Category | Badge | When |
|----------|-------|------|
| `draw` | DRAW | Draw step, upkeep draws |
| `land` | LAND | Land drops |
| `fetch` | FETCH | Fetchland crack + target |
| `combat` | COMBAT | Attacks, blocks, damage |
| `counter` | COUNTER | Force of Will, Daze, counterspells |
| `discard` | DISCARD | Thoughtseize, Unmask |
| `removal` | REMOVE | Push, Bolt, Swords |
| `combo` | COMBO | ★ Kill lines, Oops resolves |
| `spell` | CAST | Generic spell casts |
| `trigger` | TRIGGER | ETB, Bowmasters pings, tokens, energy |
| `cantrip` | DIG | Brainstorm, Ponder, Stock Up |
| `mana` | MANA | Lotus Petal, rituals, Spirit Guide |
| `death` | DIES | Creature death |
| `exile` | EXILE | Prismatic Ending, Swords, Binding |
| `sba` | SBA | Legend rule, sacrifice |
| `pw` | PW | Planeswalker activation, flip |
| `damage` | DMG | Direct damage, drain |
| `life` | LIFE | Life gain/loss/payment |

## Audit Methodology

After generating a replay, check for rules violations:

### Common Rules Violations
```python
# Double land play — >1 land per turn per player
for t in game['turns_data']:
    land_plays = sum(1 for p in t['plays'] if p['cat'] in ('land', 'fetch'))
    if land_plays > 1 and not any('exploration' in str(t.get('enchantments',[])).lower()):
        print(f"DOUBLE LAND T{t['num']} by {t['label']}")

# Negative life — game continuing after 0 or below
for t in game['turns_data']:
    if t['life'] <= 0 and t != game['turns_data'][-1]:
        print(f"NEGATIVE LIFE T{t['num']} {t['label']} at {t['life']}")
```

### Known Sim Limitations
| Issue | Symptom | Deck affected |
|-------|---------|---------------|
| No static lock modeling | Chalice/Trinisphere don't affect opponent costs | Eldrazi, Prison |
| No Karn lockout | Karn's -2 doesn't shut off opponent artifacts | Tron variants |
| Simplified combat | No first strike, no trample over (except Emrakul) | Aggro mirrors |

## Common Debug Patterns

### Verifying a deck works correctly
```python
# Run 5 games, check win rate and combo execution
for s in range(5):
    g = run_one_game('weak_opponent', seed=s, protagonist='suspect_deck')
    combo_fired = any(p['cat'] == 'combo' for t in g['turns_data'] for p in t['plays'])
    print(f"Seed {s}: {g['winner']} T{g['display_turn']} combo={combo_fired}")
```

### Finding a specific game pattern
```python
# Find a game where Burn kills before Sneak combos
for s in range(200):
    g = run_one_game('sneak_a', seed=s, protagonist='burn')
    if g['winner'] == 'BURN' and g['display_turn'] <= 8:
        html = generate_html('sneak_a', [s], protagonist='burn')
        break
```

### Spot-checking matrix data
```python
# Verify matrix WR matches actual sim
from sim import run_symmetric_game
wins = sum(1 for _ in range(50) if run_symmetric_game(d1, d2).winner == 'p1')
print(f"Sim: {wins/50*100:.0f}% vs matrix: {matrix_wr}%")
# If mismatch > 15pp, save a replay to debug
```

## File Structure

```
mtg-bo3-replayer/
├── SKILL.md (this file)
└── references/
    ├── data_model.md     — Turn data structure, mulligan history format
    └── design_system.md  — CSS classes, color system, component patterns
```

## classify_play() — 17 Categories

The function handles abbreviated card names from the sim's log output:

| Abbreviation | Full Name | Category |
|---|---|---|
| SSG | Simian Spirit Guide | mana |
| KozCmd | Kozilek's Command | cantrip (when "draw" in line) |
| TKS | Thought-Knot Seer | discard (when "exiles") |
| FoW | Force of Will | counter |
| Waste | Wasteland | interact |

**Fallback rule**: Any non-empty line that doesn't match a pattern defaults to `spell`
(creature/spell deployment), never `other`. Zero `other` is the quality bar.

## Audit Checklist

After generating any replay:
1. Count categories: `grep -o 'cat-[a-z]*' replay.html | sort | uniq -c`
2. Verify zero `other`: if any exist, classify_play needs a new pattern
3. Check double-land: no turn should have >1 LAND + FETCH combined
4. Check negative life: game should end when any player hits 0
