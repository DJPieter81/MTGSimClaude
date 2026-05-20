# MTGSimClaude — Legacy Format Monte Carlo Simulator

Python Monte Carlo simulator for Legacy MTG metagame analysis.
38 decks, 1,406 matchups, 703,000 games per matrix run (n=500).

## Products

| Product | Command | Output |
|---------|---------|--------|
| **Meta Matrix** | Template swap in `templates/reference_meta_matrix.html` | 749KB interactive HTML heatmap |
| **Deck Guides** | `python3 gen_guides.py` | 38 HTML guides (~34KB each) |
| **Bo3 Replays** | `python3 game_replay.py opp --pro deck --bo3 42 99 7` | Interactive HTML replay |

## Quick Start

```bash
# Verify
python3 -c "from sim import run_game; r = run_game('burn','ur_delver'); print(r.winner)"

# Full refresh — rebuild matrix HTML + all guides + verify (~62s)
python3 refresh_all.py

# Full refresh with matrix re-run (~7 min)
python3 refresh_all.py --resim 200

# Run matrix (50 games/pair, ~130s)
python3 -c "from sim import run_meta_matrix; run_meta_matrix(n_games=50)"

# Generate all deck guides (~30s)
python3 gen_guides.py

# Bo3 replay
python3 game_replay.py ur_delver --pro burn --bo3 42 99 7
```

## Key Files

| File | Purpose |
|------|---------|
| `sim.py` | Game runner, sweep, meta matrix, rules tests |
| `cards.py` | Card definitions, all 38 deck functions, DECKS dict |
| `game_replay.py` | Bo3 HTML replayer with 17 play categories |
| `gen_guides.py` | Generates all 38 deck guides from sim data |
| `refresh_all.py` | Single command: rebuild matrix HTML + guides + verify |
| `CLAUDE.md` | Session instructions — read this first every session |
| `PLANNING.md` | Known issues, stale data warnings, next session priorities |
| `templates/` | Reference HTML templates (matrix + Burn guide) |
| `skills/` | 3 reusable skills (meta-matrix, deck-guide, bo3-replayer) |
| `results/` | Saved matrix JSON files |

## Architecture

```
cards.py (38 decks) → sim.py (run_game) → meta_fresh.json (matrix)
                                        → deck_agg.json (profiles)
                                        → card_trimmed.json (card stats)
                                        → interact_v3.json (events)
                                        ↓
                              gen_guides.py → 38 HTML guides
                              game_replay.py → Bo3 HTML replays
                              template swap → meta matrix HTML
```

## Design System

- **Light theme** for all outputs (white bg, system sans-serif)
- **Scryfall card hovers** on all card names (`data-card` + JS tooltip)
- **7 metagame strategy components** in every deck guide (no text walls)
- **17 play categories** in replayer (zero 'other')
- **9 required JS functions** in matrix HTML (especially `pills()`)

See `CLAUDE.md` for full output standards and the Never list.
