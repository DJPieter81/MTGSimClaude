# Design System Reference — Merged Modern + Legacy Replayer

## Theme: Light Clean (matches deck guide style)

```css
body { background: #ffffff; color: #1f2328; font-family: 'Segoe UI', system-ui, sans-serif;
       padding: 20px; max-width: 920px; margin: 0 auto; font-size: 13px; }
```

### Color System
| Element | Protagonist (P1) | Opponent (P2) |
|---------|------------------|---------------|
| Turn border-left | `#0969da` blue | `#d1242f` red |
| Player badge bg | `#ddf4ff` | `#ffebe9` |
| Player badge text | `#0969da` | `#d1242f` |
| Life chart line | `#0969da` | `#d1242f` |

### Category Badge Colors (light theme)
| Category | Background | Text |
|----------|-----------|------|
| LAND | `#dafbe1` | `#1a7f37` |
| SPELL/CAST | `#ddf4ff` | `#0969da` |
| COMBAT | `#ffebe9` | `#d1242f` |
| FETCH | `#f5f0ff` | `#6639ba` |
| COUNTER | `#f5f0ff` | `#6639ba` |
| REMOVE | `#ffebe9` | `#d1242f` |
| DRAW | `#f0f0ff` | `#5a5a9a` |
| COMBO | `#fff8e1` | `#9a6700` |
| TRIGGER | `#fff8e1` | `#9a6700` |
| MANA | `#dafbe1` | `#1a7f37` |
| DISCARD | `#f6f8fa` | `#656d76` |
| DIES/DEATH | `#ffebe9` | `#d1242f` |
| EXILE | `#f5f0ff` | `#6639ba` |
| DAMAGE | `#ffebe9` | `#d1242f` |
| LIFE | `#dafbe1` | `#1a7f37` |

### Turn Structure (section-label subsections)
Each turn body contains labeled subsections:
```
Draw:     draw-row with DRAW badge + card pill
Hand:     "Hand (N cards)" + pills of all cards
Plays:    numbered steps with category badges
Combat:   combat-detail boxes (⚔ attacker + damage → life)
Board:    board-grid with creature badges, land lists, artifacts, etc.
```

### Combat Detail Boxes
```html
<div class="combat-detail">⚔ Murktide Regent</div>
<div class="combat-detail">5 damage → life 15 → 10</div>
```
Styled: `background:#fff8f8; border:1px solid #f5b8b0; border-radius:5px; padding:6px 10px`

### Response Badges (interaction inline)
When a player responds to an opponent's spell:
```html
<div class="play play-response">
  <span class="respond-badge" style="color:#0969da">⚡ Protagonist</span>
  <span class="cat-badge">COUNTER</span>
  <span class="action">Cast Force of Will (exile Blue card)</span>
</div>
```
`play-response`: yellow bg `#fff8e1`, left border `#bf8700`

### Reasoning Toggles (hidden by default)
```html
<span class="reason-toggle" onclick="toggleReason('id')">·</span>
<div class="reasoning" id="id" style="display:none">← strategic reason</div>
```
Click `·` to expand reasoning. Reduces noise, shows detail on demand.

### Legend Box (top of replay)
```html
<div class="legend-box">
  <div class="legend-title">Badge Legend</div>
  <div class="legend-row">
    <div class="leg-item"><span class="cat-badge">LAND</span><span class="leg-label">Land drop</span></div>
    ...
  </div>
</div>
```

### Result Card
```html
<div class="result">
  <h2 class="bug-win">Protagonist Wins 2-1</h2>
  <div class="reason">Game 3: combat damage turn 14</div>
  <div class="stats">Total turns: 42 · Avg game length: 14</div>
</div>
```

### Features Kept from Legacy
- **17 play categories** (no 'other')
- **6 board zones** (creatures, lands, artifacts, enchantments, planeswalkers, graveyard)
- **Mulligan reasoning** with _explain_hand() composition analysis
- **Strategic narrative** via _narrate_turn() (purple italic)
- **Life chart SVG** (blue P1 / red P2 lines)
- **Keyboard navigation** (↑↓ between turns, Enter toggle)
