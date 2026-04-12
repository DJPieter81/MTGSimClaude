---
name: mtg-meta-matrix
description: Generate interactive MTG metagame heatmaps from simulation data. Use this skill whenever the user wants to build a meta matrix, metagame visualization, matchup heatmap, deck tier analysis, or interactive matchup grid for any card game format (Legacy, Modern, Pioneer, etc.). Also triggers on requests to visualize win rates across many decks, create tournament prep tools, or build interactive HTML dashboards showing deck-vs-deck performance. Use this skill even if the user just says "build the matrix" or "make the heatmap" in the context of MTG sim work.
---

# MTG Meta Matrix — Interactive Metagame Heatmap

Generates a single-file interactive HTML heatmap showing deck-vs-deck win rates with drill-down matchup details, deck profiles, card-level tracking, and meta-weighted win rates.

## When to Use

- User wants to visualize matchup data across many decks
- User asks for a metagame matrix, heatmap, or matchup grid
- User has simulation data and wants an interactive dashboard
- User wants tournament prep tools showing tier rankings and matchup spreads

## Architecture Overview

The output is a **single self-contained HTML file** (~800-900KB) with all data embedded as inline JSON and all interactivity in vanilla JS. No external dependencies, no build step, no server needed.

### Data Layers (embedded as JS constants)

| Constant | Source | Contents |
|----------|--------|----------|
| `D` | `meta_N.json` | Win matrix, averages, weighted WR, per-matchup stats |
| `DA` | `deck_agg.json` | Deck profiles: MVPs, finishers, matchup spreads, plan text |
| `I` | `interact_v3.json` | Interaction events: locks, removal, counters, pivots |
| `C` | `card_trimmed.json` | Per-matchup card stats: top casts, attackers, damage engines |
| `ARCH` | inline | Deck-to-archetype mapping |

### Data Pipeline

Read `references/data_pipeline.md` for the full extraction pipeline. Summary:

1. **Meta matrix** (`run_batch.py`): Run N games per matchup pair, collect win rates + game stats
2. **Interaction extraction** (`extract_interactions.py`): Parse game logs for strategic events
3. **Card-level extraction** (`extract_cards.py`): Parse logs for casts, attacks, damage, finishers
4. **Deck aggregation**: Roll up per-matchup data into deck-level profiles
5. **Weighted WR**: Calculate meta-weighted averages using opponent WR as representation proxy

### UI Components

Read `references/ui_components.md` for implementation details. Summary:

1. **Heatmap grid** — Color-coded cells (HSL gradient from red→green), click for detail
2. **Tier ranking** — Chips grouped by WR threshold (T1≥65%, T2 50-65%, T3 35-50%, T4<35%)
3. **Matchup detail panel** — Side panel with: finishers, card pills, game plans, events, play/draw bars
4. **Deck profile panel** — Click deck name: tier badge, both flat + weighted WR, MVP cards, finisher analysis, tier-grouped matchup spread bars
5. **Controls** — Sort, text filter, archetype filter, highlight deck, weighted WR toggle
6. **Tooltip** — Hover shows WR, archetype, reverse matchup, avg turns

### Key Design Decisions

- **Color scheme**: Dark background (#0c0e14), HSL gradient for cells, accent blue (#60a5fa)
- **Font stack**: JetBrains Mono for data, Outfit for UI text
- **Layout**: Main area (heatmap) + sliding detail panel (400px right sidebar)
- **Mobile**: Horizontal scroll on heatmap, panel overlays on small screens
- **Data format**: All matchup keys are `"deck1|deck2"` strings

### Critical Implementation Notes

**The forEach brace bug**: When generating JS with `if(condition){...forEach(...)})`, the `})` closes the forEach but NOT the if block. Always end with `});}`  not `})}`.

**Weighted WR formula**:
```
weighted_wr[deck] = Σ(wr_vs_opp × opp_avg_wr) / Σ(opp_avg_wr)
```

**Matchup data array format** (`M[key]`):
```
[win_rate, kill_turn, game_length, otp_wr, otd_wr, otp_n, otd_n, 
 p1_final_life, p2_final_life, p1_mulls, p2_mulls, win_reasons]
```

## File Structure

```
mtg-meta-matrix/
├── SKILL.md (this file)
└── references/
    ├── data_pipeline.md    — How to extract data from any sim engine
    ├── ui_components.md    — HTML/CSS/JS patterns for each component
    └── build_template.py   — Python script that assembles the final HTML
```

## Critical: pills() Function

The `pills(cards, color)` function renders card pill badges in the matchup detail panel.
It is the most commonly forgotten function when rebuilding the HTML.

**Always verify after any rebuild:**
```bash
grep 'function pills' output.html
```

If missing, inject before `closeDet()`:
```javascript
function pills(cards,color){
  return '<div style="display:flex;flex-wrap:wrap;gap:3px;margin:2px 0">'
    + cards.map(([c,n]) => '<span style="display:inline-block;background:'
    + color+'15;color:'+color+';border:1px solid '+color
    + '30;border-radius:10px;padding:1px 7px;font-size:10px;font-family:JetBrains Mono,monospace">'
    + c+' <span style="opacity:.5">×'+n+'</span></span>').join('')
    + '</div>';
}
```

## Refresh Pipeline

Never rebuild from scratch. Use the template and swap data:

```python
# 1. Load template
with open('templates/reference_meta_matrix.html') as f: html = f.read()

# 2. Replace each data constant
for name, data in [('D',meta),('DA',agg),('C',cards),('I',interact),('ARCH',arch)]:
    html = replace_const(html, name, json.dumps(data))

# 3. Verify pills() exists
if 'function pills' not in html:
    # inject it

# 4. Verify all 9 functions
for fn in ['pills','wc','tc','muc','getCT','tierOf','tierTag','getWR','closeDet']:
    assert f'function {fn}' in html, f'MISSING: {fn}'
```
