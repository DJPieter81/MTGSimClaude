# Design System Reference — Merged Amulet + Legacy Style

## Theme: Light Clean

```css
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #fff; color: #111; font-size: 14px; padding: 24px;
       max-width: 960px; margin: 0 auto; }
```

### Color System (3 semantic colors)
| Use | Color | Hex |
|-----|-------|-----|
| Good / favorable / keep | Green | `#1f7040` |
| Neutral / competitive | Amber | `#854f0b` |
| Bad / unfavorable / mull | Red | `#b02020` |

### Hero Stat Grid
4-column grid: Format | Sim WR (flat + weighted) | Rank/Tier | Best/Worst matchup.
Each cell: 9px uppercase label, 28px bold value, 11px grey subtitle.

### Card Role Badges
| Class | Color | Use |
|-------|-------|-----|
| `b-threat` | green | Creatures that attack |
| `b-burn` | orange | Direct damage |
| `b-reach` | purple | Conditional/big damage |
| `b-engine` | warm | Repeatable value (Eidolon, Bowmasters) |
| `b-kill` | red | Win conditions (Fireblast, Emrakul) |
| `b-enabler` | green | Setup / acceleration |
| `b-removal` | red | Interaction |
| `b-draw` / `b-tutor` | blue/gold | Card selection |
| `b-hate` | purple | Sideboard hate |
| `b-flex` | grey | Lands, flexible slots |

### Scryfall Card Image Hovers
All card names get `class="card-tip" data-card="Card Name"`.
On hover, show popup with image from:
`api.scryfall.com/cards/named?fuzzy=NAME&format=image&version=normal`
Cache in JS object. Popup follows cursor within viewport. Dotted underline affordance.
Apply to: mainboard, sideboard, hand examples, bold card mentions in strategy.

### Game Plan Timeline
Vertical line with dots connecting 3 phase boxes.
Phase border-left color matches deck identity (red=burn, blue=tempo, green=combo).

### Metagame Strategy — 7 Visual Components
1. **Archetype WR bars** — horizontal, green ≥65% / amber 45-65% / red <45%
2. **Tournament histogram** — 8-round sim (10K runs), green=Top 8, amber=bubble, red=miss
3. **Prey/Competitive/Danger triptych** — 3 cards with big WR + description
4. **Tournament arc** — segmented bar: R1-3 bank (green) → R4-6 gauntlet (amber) → R7-8 top (red)
5. **Delta proof chart** — flat→weighted drop bars for T1 decks (smaller = genuinely strong)
6. **Danger matchup cards** — red gradient header + ✗ why-lose / ⚡ auto-loss / ★ steal-line
7. **Game plan timeline** — vertical dots + phase boxes

### Hand Boxes
Green left-border (keep/won) or red (mull/lost).
Cards in monospace with Scryfall hovers. Turn-by-turn log with bold T# markers.

### Two-Column Layout
Grid 1fr 1fr, gap 28px. Mainboard left, sideboard + findings right.
Responsive: single column below 640px.

### Provenance Footer
`MTGSimClaude · run_symmetric_game() × 50/pair · N decks · N matchups · date`
