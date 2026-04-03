# MTG Legacy BUG Tempo Simulator

Python Monte Carlo simulator for Legacy BUG Tempo matchup analysis.
19-deck meta, ~3k games/matchup, protagonist-aware sideboard simulation.

## Files
- `engine.py` — game engine, all strategy functions
- `sim.py` — simulation runner, BO3 logic, STRATEGIES registry
- `game.py` — PlayerState, mulligan, combat
- `cards.py` — card definitions, all 20 decks, sideboard plans
- `rules.py` — rules engine (Brainstorm, Daze, FoW, Veil, etc.)
- `interaction.py` — reactive counter logic
- `decks/` — plugin decks (8-Cast, TES)
- `results/overnight_sweep.json` — full 20-deck EV table
- `results/matchup_matrix.npy` — 19×19 matchup matrix

## Quick start
```python
from sim import run_any_bo3
r = run_any_bo3('bug', 'storm', 1000)
print(f"BUG vs Storm: {r['match_wr']*100:.1f}%")
```

## Pending
- 3k re-sweep for all 17 MED decks (run `python3 full_sweep.py`)
- Marit Lage tiebreak fix for Lands
- Wirewood Symbiote loops for Elves
