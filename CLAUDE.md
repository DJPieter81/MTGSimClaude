# CLAUDE.md — MTGSimClaude Session Instructions

Read this file at the start of every session. It is the source of truth.

## Setup

```bash
cd MTGSimClaude
git pull origin main
python3 -c "from cards import DECKS; print(f'{len(DECKS)} decks')"
```

Check `results/` for latest matrix JSON by timestamp. Spot-check 3-5 matchups
with `run_symmetric_game(d1, d2)` before building any outputs.

## Three Products

### 1. Meta Matrix (HTML + JSX)

**Template**: Use `results/mtg_meta_matrix.html` as the canonical template.
Never rebuild from scratch — replace the 5 data constants (D, DA, C, I, ARCH).

**Required JS functions** (all must exist before `render()`):
`pills(cards,color)`, `wc(w)`, `tc(w)`, `muc(w)`, `getCT()`, `tierOf(w)`,
`tierTag(w)`, `getWR(d)`, `closeDet()`

After any rebuild, verify: `grep 'function pills' output.html` — if missing, inject it.

**Data layers**: D (matchup WRs), DA (deck profiles), C (card-level stats),
I (interaction events), ARCH (archetype map).

**Weighted WR**: T1+T2 opponents only (flat ≥50%). Thresholds: 58/48/33 weighted, 65/50/35 flat.

### 2. Deck Guides (HTML)

**Design system** (merged Amulet Titan + Legacy):

- **Theme**: Light. White bg, system sans-serif font, max-width 960px.
- **Hero**: 4-column grid (Format, WR flat+weighted, Rank/Tier, Best/Worst).
- **Decklist**: Two-column. Mainboard left with card role badges, sideboard + findings right.
- **Card role badges**: threat, burn, engine, reach, finisher, removal, draw, tutor, hate, flex, enabler.
- **Scryfall hovers**: Every card name gets `class="card-tip" data-card="Card Name"`.
  JS tooltip loads `api.scryfall.com/cards/named?fuzzy=NAME&format=image&version=normal`.
- **Game plan**: Vertical timeline with colored dots + 3 phase boxes.
- **Kill turn chart**: CSS flex bars with percentage labels.
- **Hand archetype WR bars**: Horizontal bars with baseline marker (2,000 games).
- **Real sim hands**: Keep (green border) / Mull (red border) boxes with T-by-T logs.
- **Provenance footer**: `MTGSimClaude · run_symmetric_game() × N/pair · N decks · date`

**Metagame strategy section** (7 visual components — NO text walls):
1. Archetype WR horizontal bars (green ≥65% / amber 45-65% / red <45%)
2. Tournament histogram (8-round sim, 10K runs)
3. Prey / Competitive / Danger triptych cards
4. Tournament arc segmented bar (R1-3 bank → R4-6 gauntlet → R7-8 top tables)
5. Delta proof chart (flat→weighted drop across T1 decks)
6. Danger matchup cards (red gradient header + ✗/⚡/★ icon bullets)
7. Game plan as vertical timeline with phase boxes

### 3. Bo3 Replayer (HTML)

**API**: `generate_html(opponent, seeds=[42,99,7], protagonist='deck')`

**Design system** (merged Modern + Legacy):

- **Theme**: Light. White bg, system sans-serif, max-width 920px.
- **17 play categories**: draw, land, fetch, combat, counter, discard, death,
  exile, sba, removal, combo, spell, trigger, cantrip, mana, damage, life.
  Zero 'other' — `classify_play()` catches abbreviated names (SSG, KozCmd, TKS, FoW, Waste).
- **Turn structure** with section labels: Draw → Hand (N cards) → Plays → Combat → Board.
- **Combat detail boxes**: `⚔ Creature` + `N damage → life X → Y`.
- **Draw step as pill**: Shows what was drawn.
- **Full hand pills**: Every card in hand shown as pills every turn.
- **Reasoning hidden by default**: Click `·` toggle to reveal.
- **Response badges**: `⚡ Player` badge for counterspells/interaction.
- **Legend box at top**: Badge color explanation.
- **Result card**: Gradient styled winner announcement with stats.
- **6 board zones**: creatures (P/T), lands, artifacts, enchantments, planeswalkers, graveyard.
- **Mulligan reasoning**: `_explain_hand()` composition analysis.
- **Strategic narrative**: `_narrate_turn()` per-turn commentary.
- **Life chart SVG**: Blue P1 / red P2 lines.

## Data Pipeline

```
run_symmetric_game() × 50/pair → meta_fresh.json (D)
                                → deck_agg.json (DA)
extract_cards.py               → card_trimmed.json (C)
extract_interactions.py        → interact_v3.json (I)
DECKS + agg                    → ARCH map
```

## Quality Checks

Before sharing any output:
1. Matrix: all 9 JS functions defined (grep for each)
2. Guides: Scryfall hovers working (check data-card attrs exist)
3. Replayer: zero 'other' category plays (count with regex)
4. All: provenance footer with date and game count
5. Spot-check 3-5 matchups against live sim before building dashboards

## Sim API Quick Reference

```python
from sim import run_symmetric_game
r = run_symmetric_game('burn', 'ur_delver')  # returns GameResult
# r.winner ('p1'/'p2'), r.kill_turn, r.log_lines

from game_replay import generate_html
html = generate_html('ur_delver', seeds=[42,99,7], protagonist='burn')

from cards import DECKS  # dict of all deck keys
```

## Never

- Never re-run the matrix if results/*.json files exist (unless explicitly asked)
- Never use MTGSimManu imports/paths — this is MTGSimClaude (Legacy)
- Never produce text-wall metagame sections — use the 7 visual components
- Never show reasoning by default in replayer — use toggle
- Never skip the provenance footer
- Never rebuild matrix HTML from scratch — use the template and swap data constants
