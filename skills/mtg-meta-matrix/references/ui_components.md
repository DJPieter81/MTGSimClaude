# UI Components Reference

## Layout Architecture

```
┌──────────────────────────────────────────┬──────────────────┐
│  MAIN AREA                               │  DETAIL PANEL    │
│  ┌─ Controls ─────────────────────┐      │  (400px, slides) │
│  │ Sort | Filter | Archetype | HL │      │                  │
│  └────────────────────────────────┘      │  Matchup Detail  │
│  ┌─ Tier Ranking ─────────────────┐      │  — or —          │
│  │ T1: [chip] [chip]  T2: [chip]  │      │  Deck Profile    │
│  └────────────────────────────────┘      │                  │
│  ┌─ Heatmap Grid ─────────────────┐      │                  │
│  │      d1  d2  d3  d4  avg       │      │                  │
│  │  d1  —   72  45  88  68%       │      │                  │
│  │  d2  38  —   55  62  52%       │      │                  │
│  └────────────────────────────────┘      │                  │
└──────────────────────────────────────────┴──────────────────┘
```

## Color System

```css
:root {
  --bg: #0c0e14;      /* main background */
  --bg2: #12151e;     /* panel background */
  --bg3: #181c28;     /* card/section background */
  --tx: #c8cdd8;      /* primary text */
  --tx2: #8891a4;     /* secondary text */
  --tx3: #5a6270;     /* tertiary/label text */
  --acc: #60a5fa;     /* accent blue */
  --grn: #4ade80;     /* positive/winning */
  --red: #f87171;     /* negative/losing */
  --orn: #d97706;     /* warning/even */
  --gold: #c9a227;    /* highlight/finisher */
}
```

### Win Rate → Color Mapping

```javascript
function wc(w) {
  if (w <= 25) return `hsl(0, 55%, ${18 + w * 0.3}%)`;
  if (w <= 40) return `hsl(${(w - 25) * 1.6}, 45%, 25%)`;
  if (w <= 50) return `hsl(${24 + (w - 40) * 3.6}, 35%, 24%)`;
  if (w <= 65) return `hsl(${60 + (w - 50) * 5.3}, 45%, 24%)`;
  return `hsl(140, 50%, ${24 + (w - 65) * 0.4}%)`;
}
```

## Component: Heatmap Cell

```html
<td class="c" style="background:${bg};color:${fg}" data-k="${d1}|${d2}">
  ${Math.round(wr)}
</td>
```

- Click → open matchup detail panel
- Hover → show tooltip
- Highlight mode → dim unrelated cells to `opacity: 0.15`
- Selected cell → `outline: 2px solid var(--acc)`

## Component: Tier Ranking Chips

```html
<span class="rchip" style="color:${tc};background:${wc}" data-d="${deck}">
  <span style="opacity:.4">${rank}</span> ${name} <b>${wr}%</b>
</span>
```

Grouped under tier headers. Click chip → highlight that deck's row/column.

## Component: Matchup Detail Panel

Sections in order:
1. **Header**: `d1 vs d2` with archetype labels
2. **Win Rate**: Large number with color
3. **Finishers** ("How d1 Wins"): `fin-row` with count + card name
4. **Key Cards** (d1 and d2): Pill badges for casts, attackers, damage
5. **Game Plans**: Text blocks from deck profiles
6. **Events**: Categorized (locks, removal, counters, pivots)
7. **Play/Draw Bars**: Two horizontal bars with percentage
8. **Tempo Stats**: Kill turn, game length, final life totals

### Pill Badge Component

```javascript
function pills(cards, color) {
  return '<div class="pill-grid">' + cards.map(([c, n]) =>
    `<span class="pill" style="background:${color}15;color:${color};
     border:1px solid ${color}30">${c} <span style="opacity:.5">×${n}</span>
     </span>`
  ).join('') + '</div>';
}
```

### Event Categories

| Category | Icon | Color | Label format |
|----------|------|-------|--------------|
| Locks | 🔒 | `--orn` | `N/20 games` |
| Removal | ⚔️ | `--red` | `N× total` |
| Counters | 🛡️ | `--acc` | `N× total` |
| Pivots | ⚡ | `--grn` | `N/20 games` |

## Component: Deck Profile Panel

Triggered by clicking deck name or diagonal cell. Sections:

1. **Header**: Tier badge (S/A/B/C) + deck name
2. **Win Rates**: Flat + Weighted side-by-side with delta
3. **Game Plan**: Text description
4. **Finishers**: Ranked by kill count with `fin-row` components
5. **MVP Cards**: Top 5 most-cast across all matchups
6. **Top Attackers**: Most-connecting creatures
7. **Damage Engines**: Direct damage sources
8. **All Matchups**: Tier-grouped bar chart (T1 first)

### Tier Badge

```html
<span class="tier-badge" style="background:${color}20;color:${color};
  border:1px solid ${color}40">${letter}</span>
```

| WR Range | Letter | Color |
|----------|--------|-------|
| ≥65% | S | #4ade80 |
| 50-65% | A | #60a5fa |
| 35-50% | B | #d97706 |
| <35% | C | #f87171 |

## Component: Weighted WR Toggle

```html
<label>
  <input type="checkbox" id="wtToggle"> Meta-weighted
</label>
```

When toggled, all WR references switch from `A[d]` to `W[d]`. Affects:
- Tier rankings and groupings
- Sort order
- Avg column in matrix
- Deck profile win rates
- Matchup spread ordering

## Critical JS Patterns

### The forEach Brace Bug

**WRONG** (missing closing brace for if block):
```javascript
if(ev.l && ev.l.length) {
  h += '<div>header</div>';
  ev.l.forEach(([t,n]) => { h += `<div>${t}</div>` })
}  // ← this } closes forEach, NOT the if block!
```

**CORRECT**:
```javascript
if(ev.l && ev.l.length) {
  h += '<div>header</div>';
  ev.l.forEach(([t,n]) => { h += `<div>${t}</div>` });
}  // ← this } correctly closes the if block
```

### Matchup Key Flipping

When user clicks cell (row, col), the data might be stored as (col, row). Always normalize:

```javascript
function gpw(ri, ci) {
  const ki = Math.min(ri, ci), kj = Math.max(ri, ci);
  const p = data[`${ki},${kj}`];
  if (ri > ci) { /* flip d1/d2 fields */ }
  return p;
}
```
