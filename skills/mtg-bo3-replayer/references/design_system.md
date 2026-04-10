# Design System Reference

## Color System

```
Background:   #0d1117 (body), #161b22 (panels), #21262d (badges), #0d1117 (board)
Text:         #c9d1d9 (primary), #8b949e (secondary), #484f58 (muted), #f0f6fc (bright)
Protagonist:  #58a6ff (blue) — borders, labels, life line, dots
Opponent:     #f85149 (red) — borders, labels, life line, dots
Cards/pills:  #e3b341 (gold) on #21262d background
```

## Player Side Colors

| Element | Protagonist (P1) | Opponent (P2) |
|---------|-------------------|---------------|
| Turn border-left | `#58a6ff` | `#f85149` |
| Turn number | `.tnum.bug` `#58a6ff` | `.tnum.opp` `#f85149` |
| Player badge | `bg:#0d2847 color:#58a6ff` | `bg:#3d1418 color:#f85149` |
| Life chart line | `#58a6ff` | `#f85149` |
| Hand box border | `border-left:3px solid #58a6ff` | `border-left:3px solid #f85149` |
| Game tab winner dot | `bg:#58a6ff` | `bg:#f85149` |

## Board State Zone Colors

| Zone | Icon | Color | CSS class |
|------|------|-------|-----------|
| Lands | (text) | `#7ee787` green | `.land-list` |
| Artifacts | ⚙️ | `#e3b341` gold | `.art-list` |
| Enchantments | ✨ | `#d2a8ff` purple | `.ench-list` |
| Planeswalkers | 🔮 | `#79c0ff` blue | `.pw-list` |
| Graveyard | 🪦 | `#6e7681` grey | `.gy-list` |

## Mulligan Components

```css
.mull-step     — flex row: hand size label + keep/mull tag
.mull-label    — grey "7 cards" / "6 cards" label
.keep-tag      — green "✓ KEEP" (#3fb950)
.mull-tag      — red "✗ MULL" (#f85149)
.mull-pills    — opacity:0.5, strikethrough pills for mulled hands
.mull-reason   — red italic left-bordered explanation
.hand-analysis — green box with composition breakdown for kept hand
```

## Strategic Narrative

```css
.turn-narrative — purple italic (#d2a8ff), left-bordered, 0.8em
                  background: #d2a8ff08, border-left: 2px solid #d2a8ff40
```

## Play Category Badges

Each play gets a colored badge based on its category:

```css
.cat-badge     — base: inline-block, border-radius:3px, padding:1px 6px, font-size:0.7em
.cat-draw      — color:#8b949e (grey)
.cat-land      — color:#7ee787 (green)
.cat-combat    — color:#f85149 (red)
.cat-interact  — color:#58a6ff (blue)
.cat-discard   — color:#d2a8ff (purple)
.cat-removal   — color:#f85149 (red)
.cat-combo     — color:#e3b341, background:#e3b34120 (gold, highlighted)
.cat-spell     — color:#79c0ff (light blue)
.cat-trigger   — color:#d2a8ff (purple)
.cat-cantrip   — color:#8b949e (grey)
.cat-mana      — color:#e3b341 (gold)
```

## Key Components

### Turn (collapsible)
```html
<div class="turn bug" data-idx="0">        <!-- border-left colored by player -->
  <div class="turn-header" onclick="toggle(this.parentElement)">
    <div class="left">
      <span class="tnum bug">T1</span>     <!-- turn number -->
      <span class="player bug">BURN</span> <!-- player badge -->
      <span class="life">Life: <b>20</b> | Opp: 20</span>
    </div>
    <span class="arrow">▶</span>           <!-- rotates 90° when open -->
  </div>
  <div class="turn-body">
    <!-- Hand pills → Plays → Narrative → Board State -->
  </div>
</div>
```

### Play line
```html
<div class="play">
  <span class="step">1.</span>
  <span class="cat-badge cat-land">LAND</span>
  <span class="action">Land: Mountain (1 lands)</span>
  <span class="reasoning">← develop mana</span>
</div>
```

### Creature badge
```html
<span class="creature-badge">
  DRC<span class="pt">3/3</span>
  <span class="sick">(sick)</span>  <!-- if summoning sick -->
</span>
```

### Life chart (SVG)
```html
<svg viewBox="0 0 {turns*40} 80">
  <!-- Line segments + circles at each turn -->
  <!-- Blue (#58a6ff) for protagonist, Red (#f85149) for opponent -->
  <!-- Labels above/below circles showing life total -->
</svg>
```

## Keyboard Navigation

```javascript
↑ / ↓    — Navigate between turns (adds .active class)
Enter    — Toggle expand/collapse on active turn
```

Active turn gets `border-color: #e3b341` (gold highlight).
