---
name: mtg-project-showcase
description: Generate interactive project showcase pages for MTG simulator projects. Use this skill whenever the user wants to create a marketing page, project showcase, architecture visualization, or "show off" page for MTGSimManu (Modern) or MTGSimClaude (Legacy). Triggers on "showcase", "marketing page", "show off the architecture", "visualize the project", "create a portfolio page", "share with friends", or any request to present the project's capabilities to an external audience. Also triggers when updating an existing showcase after new sim runs, bug fixes, or architecture changes.
---

# MTG Project Showcase — Skill

## Purpose
Generate interactive, visually polished HTML showcase pages for MTG simulator projects. The output is a standalone HTML file suitable for sharing with friends, posting on GitHub, or embedding in a portfolio.

## Design system

**Theme:** Light editorial — cream background (#faf8f4), warm paper (#f3f0ea), white cards, gold accent (#b8941e).

**Typography:** Playfair Display (serif, headings), Outfit (sans, body), JetBrains Mono (mono, data). Load via Google Fonts CDN.

**Charts:** Chart.js 4.x via cdnjs.cloudflare.com. Use for: WR bar charts (horizontal, indexAxis:'y'), convergence line charts, radar grades.

**Colors:**
```
--gold: #b8941e   --teal: #0f6e56   --blue: #185fa5
--red: #a32d2d    --amber: #d4850b  --purple: #534ab7
```

## Required sections (in order)

### 1. Hero
- Eyebrow: format + deck count + key differentiator
- Title: project name with gold accent on format word
- Subtitle: 1-2 sentences, key stats
- Counter row: 4 animated counters (data-target attr, JS animates on scroll)

### 2. Performance charts
- Chart.js grid (2 columns): WR bar chart + convergence line chart
- Real data from latest matrix JSON
- Convergence shows dashed "true value" reference line

### 3. Architecture (interactive)
- Colored horizontal bars (one per layer) with left accent stripe + icon
- Click any bar → detail panel with: description, stat grid (4 metrics), code box
- Bar colors map to layer type: gold=sim, teal=engine, purple=AI, blue=data, red=output

### 4. AI engine (interactive stepper)
- 4-tab stepper: spell casting, counter logic, combat EV, combo kill
- Each tab shows step-by-step flow + formula box in mono font
- Clicking a tab swaps the detail panel (fadeIn animation)

### 5. Output products
- 3-card grid with SVG preview illustrations
- Each card: gradient visual header, title, description, feature pills
- Matrix = blue gradient, Guide = green gradient, Replayer = amber gradient

### 6. Validation (interactive)
- Custom HTML accuracy bars (NOT Chart.js) — clickable rows that expand detail panel
- Each row: name, animated fill bar, shaded expected-range background, WR number, pass/fail icon
- Click → shows: expected range, root cause for failures, verdict text
- Full labeled heatmap table: rotated column headers, row labels, colored cells
- Click any cell → detail panel: WR, reverse WR, symmetry check, who's favored
- Floating tooltip follows cursor on hover

### 7. Bug timeline (expandable)
- Vertical timeline with colored dots: teal=verified, red=P0, amber=P1
- Click any item → expands detail with technical explanation + trace commands
- Tags: Verified / P0 / P1

### 8. Deck cloud (clickable)
- Pill-shaped chips: gold border = T1, blue border = T2, plain = field
- Meta share shown on T1 chips
- Click any chip → profile card below: flat WR, archetype, strategy type, best/worst matchup, tier badge

### 9. Cross-project cards (if applicable)
- Side-by-side gradient cards: Legacy (blue) vs Modern (gold)
- Big number + project name + description of what each teaches the other

### 10. Roadmap (expandable)
- Card grid with colored top borders (gold/blue/green for phases)
- Click any card → toggles implementation detail in mono-styled box

### 11. Footer
- Project name with gold accent, GitHub links, LoC count, date

## Data sources

For MTGSimClaude (Legacy):
```python
# Get deck WRs
from sim import run_sweep
import json, glob
files = sorted(glob.glob('results/matrix_*.json') + glob.glob('results/custom_matrix_*.json'))
with open(files[-1]) as f: data = json.load(f)
matchups = data.get('matchups', data)
```

For MTGSimManu (Modern):
```python
# Results from run_meta.py --matrix --save
import json
with open('results/latest_matrix.json') as f: data = json.load(f)
```

## Key interactive patterns

**Animated counters:** `data-target` attribute on `.num` elements. IntersectionObserver triggers count-up animation with cubic easing.

**Scroll reveal:** `.reveal` class, IntersectionObserver adds `.visible` (opacity 0→1, translateY 28px→0).

**Detail panels:** Hidden by default (`display:none`). JS toggles `.show` class. All use `animation: fadeIn .2s ease`.

**Heatmap color function:**
```javascript
function wrC(v) {
  if (v >= 60) return `rgba(15,110,86,${.12+v/250})`;
  if (v >= 50) return `rgba(15,110,86,${.06+v/500})`;
  if (v >= 40) return 'rgba(200,180,140,.1)';
  return `rgba(163,45,45,${.08+(100-v)/300})`;
}
```

## Reference implementation
The canonical reference is `mtgsimclaude_showcase.html` (456 lines, 55K). Copy design patterns from there, swap data for the target project.

## Checklist before delivery
- [ ] All counters animate on scroll
- [ ] Chart.js loads from cdnjs.cloudflare.com
- [ ] Every architecture bar is clickable with detail
- [ ] AI stepper has 4 working tabs
- [ ] Accuracy rows expand on click
- [ ] Heatmap cells expand on click
- [ ] Deck chips show profile on click
- [ ] Timeline items expand on click
- [ ] Roadmap cards expand on click
- [ ] All data is real (from matrix JSON, not invented)
- [ ] File is standalone HTML (no external deps except Google Fonts + Chart.js CDN)
