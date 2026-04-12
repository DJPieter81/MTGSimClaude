# MTGSimClaude — Legacy Format Monte Carlo Simulator

## Quick Start

```bash
# Verify installation
python3 -c "from sim import run_rules_tests; run_rules_tests()"
# Should print: 137 passed, 0 failed

# Run a game
python3 -c "from sim import run_game; r = run_game('ur_delver', 'dimir'); print(r.winner, r.win_reason)"

# Full refresh (matrix HTML + all guides + verify) — ~62s
python3 refresh_all.py

# Full refresh with matrix re-run — ~7 min
python3 refresh_all.py --resim 200
```

**Always read `PLANNING.md` first** — it has known issues, stale data warnings, and session priorities.

## Core API (all imports from `sim.py`)

```python
from sim import run_game, run_sweep, run_meta_matrix
```

### run_game(deck1, deck2)
Run a single game between any two decks. Returns `GameResult`.
```python
r = run_game('ur_delver', 'dimir')
r = run_game('storm', 'burn')
r = run_game('storm')  # legacy shorthand: BUG vs storm
```

### run_sweep(deck1, deck2, n_games=100)
Run N games, return stats dict with `p1_wr`, `p1_wins`, `p2_wins`, `avg_length`, `avg_kill`.
```python
s = run_sweep('bug', 'storm', n_games=200)
print(f"{s['p1_wr']:.1%}")
```

### run_meta_matrix(decks=None, n_games=100, top_tier=0)
Run every deck vs every deck. Returns `{(d1, d2): win_rate}`.
```python
matrix = run_meta_matrix(top_tier=8, n_games=100)       # 8 random top-meta decks
matrix = run_meta_matrix(decks=['bug','storm','dimir'])  # explicit list
```

### Other functions
```python
from sim import run_any_match, run_any_bo3, run_rules_tests

run_any_match('ur_delver', 'dimir', verbose=True)   # any deck Bo3
run_any_bo3('storm', 'bug', n_matches=100)           # Bo3 batch
run_rules_tests()                                    # 116 unit tests
```

## CLI: run_meta.py

```bash
python3 run_meta.py --list                            # All 36 decks with meta share
python3 run_meta.py --deck storm                      # Decklist, strategy, profile
python3 run_meta.py --matchup ur_delver dimir -n 100  # Head-to-head sweep
python3 run_meta.py --field bug -n 50                 # One deck vs all others
python3 run_meta.py --matrix --decks 8 -n 30          # Top-8 meta matrix
python3 run_meta.py --matrix bug storm dimir -n 50    # Custom deck matrix
python3 run_meta.py --verbose storm burn -s 42        # Full play-by-play trace (auto-saved)
python3 run_meta.py --trace storm burn -s 42          # Alias for --verbose
python3 run_meta.py --results                         # List saved result files
python3 run_meta.py --load                            # Display latest saved matrix
python3 run_meta.py --load custom_matrix              # Display specific saved result
```

Matrix and field results are auto-saved as JSON to `results/`. Load in any session:
```python
from meta_results import load_matrix, print_matrix
data = load_matrix()        # latest matrix
print_matrix(data)          # pretty-print it
```

## HTML Game Replay

Interactive turn-by-turn replay with board state, life totals, and play-by-play log.
Outputs to `results/game_replay.html`.

```bash
python3 game_replay.py storm 42                       # Single game (seed 42)
python3 game_replay.py dimir --bo3 1 3 5              # Bo3 with seeds 1,3,5
python3 game_replay.py storm --bo3 4 9 1              # Bo3 Storm as opponent
python3 game_replay.py dimir 42 --pro ur_delver       # UR Delver vs Dimir
python3 game_replay.py sneak_a --bo3 1 3 5 --pro storm  # Storm vs Sneak Bo3
```

Note: `game_replay.py` uses its own game loop (not `play_turn`). The `--pro` flag
selects the protagonist deck (default: BUG).

## Import a New Deck

Paste a raw decklist (MTGGoldfish/Moxfield format) to auto-generate a deck module:

```bash
echo "4 Delver of Secrets
4 Lightning Bolt
4 Force of Will
..." | python3 import_deck.py "My Deck Name" aggro,tempo_mirror

# Or batch import from text files:
python3 import_deck.py --scan  # reads decks/imports/*.txt
```

From Python:
```python
from import_deck import import_decklist
import_decklist(decklist_text, name='My Deck', categories={'aggro'})
```

The importer auto-matches known cards, generates a strategy, and registers the deck.
Verify with `python3 run_meta.py --deck my_deck`.

## Available Decks (36)

| Key | Deck Name |
|-----|-----------|
| `affinity` | Affinity (8-Cast variant) |
| `belcher` | Goblin Charbelcher |
| `boros` | Boros Aggro |
| `bug` | BUG Tempo |
| `burn` | Burn |
| `cephalid` | Cephalid Breakfast |
| `cloudpost` | Cloudpost (12-Post) |
| `depths` | Dark Depths |
| `dimir` | Dimir Tempo A (Nethergoyf) |
| `dimir_b` | Dimir Tempo B (Barrowgoyf) |
| `dimir_c` | Dimir Tempo C (Barrowgoyf) |
| `dimir_d` | Dimir Tempo D (Kaito) |
| `dimir_flash` | Dimir Flash (Wan Shi Tong) |
| `dnt` | Death and Taxes |
| `doomsday` | Doomsday |
| `eight_cast` | 8-Cast |
| `eldrazi` | Eldrazi Aggro |
| `elves` | Elves |
| `goblins` | Goblins |
| `infect` | Infect |
| `lands` | Lands |
| `mardu` | Mardu Aggro |
| `mono_black` | Mono Black Aggro |
| `oops` | Oops All Spells |
| `painter` | Painter |
| `prison` | Artifacts Prison |
| `reanimator` | Reanimator |
| `show` | Show and Tell |
| `sneak_a` | Sneak & Show A (rerere) |
| `sneak_b` | Sneak & Show B (JPA93) |
| `storm` | Storm (ANT) |
| `tes` | The Epic Storm |
| `ur_aggro` | UR Aggro |
| `ur_delver` | UR Delver |
| `ur_tempo` | UR Tempo (Cori-Steel) |
| `uwx` | UWx Control |

## GameResult Fields

```python
r.winner          # 'p1' or 'p2'
r.win_reason      # e.g. 'Opp life reaches -6 on turn 9'
r.kill_turn       # turn number of kill (None if timeout)
r.game_length     # total turns played
r.p1_mulls        # mulligan count
r.p2_mulls
r.p1_opening_hand # list of card names
r.p2_opening_hand
r.log_lines       # full game log
r.final_p1_life
r.final_p2_life
r.p1_went_first   # bool
r.p1_deck         # deck key
r.p2_deck
```

## Architecture

- `engine.py` — Turn functions (`play_turn`, `bug_turn`, `opp_turn`), combat, counter spells, all strategy functions
- `sim.py` — Game loop (`run_game`), sweeps, matrix, Bo3 matches, `protagonist_turn`
- `game.py` — `GameState` (slots: `p1`, `p2`), `PlayerState`, `london_mulligan`
- `cards.py` — All 36 deck builders, `DECKS` dict, `MATCHUP_META`
- `rules.py` — MTG rules: `Permanent`, `LandPermanent`, `MTGRules`, `Card`
- `config.py` — `MatchupCategory` (combo/aggro/prison/mirror classifications)
- `deck_registry.py` — Auto-discovery of deck modules in `decks/`
- `interaction_model.py` — Interaction profiles, save rates, FoW priority
- `run_meta.py` — CLI for all meta analysis commands
- `import_deck.py` — Decklist parser and deck module generator
- `parallel.py` — Multiprocessing for matrix and field runs (~3x speedup)
- `meta_results.py` — Save/load simulation results as JSON for cross-session use
- `game_replay.py` — HTML turn-by-turn game replay generator
- `meta_audit.py` — Post-sim outlier detection + strategy audit + HTML dashboard

## Key Design Principles

1. **Game rules are enforced at infrastructure level**, not in individual deck strategies. Chalice, Trinisphere, Thalia, Bridge, Maze of Ith, Narset, and Leyline are all checked in `opp_can_cast()`, `play_turn()`, or `combat_declare()`.

2. **Symmetric engine**: `gs.p1` and `gs.p2` are neutral player slots. Both sides get equal AI quality via `play_turn()`. Winner is `'p1'` or `'p2'`, never deck-specific.

3. **Adding a new deck** requires only creating a file in `decks/` with a `DECK_META` dict. No edits to engine.py, sim.py, or cards.py needed.

4. **No hardcoded numbers, arbitrary scores, or magic constants.** Every numeric threshold, probability cutoff, score weight, and ranking boundary must be:
   - Derived from a property on the `Card`/`Permanent` object (e.g. `card.cmc`, `c.power`, `opponent.life`), OR
   - Pulled from `config.py` (`InteractionParams`, `MatchupCategory`, etc.) as a named constant, OR
   - Computed from observable game state (e.g. `board_clock(...)`, `_prob_at_least_one(copies, drawn)`), OR
   - Documented in a JSON gameplan (`gameplans/*.json`) and read via `GoalEngine`.

   **Bad:** `if opponent.life <= 12: go_face`, `lethal_storm = 9`, `p_counter > 0.4`, `score += 50 if c.is_creature else 10`.
   **Good:** `go_face = (board_clock(...) > bolts_in_hand)`, `lethal_storm = max(1, (opponent.life + 1) // 2 - 1)`, `p_counter > IP.BHI_FREE_COUNTER_THRESHOLD`, `score += threat_level_to_clock_delta(classify_threat(...))`.

   When a hardcoded constant is unavoidable (e.g. rules-mandated like CR 601.2f's "cost at least 3" for Trinisphere), comment the CR reference and lift to `config.py` if it's reused.

## Lessons Learned (Strategy & Rules Audit)

### Trinisphere Enforcement (Critical Pattern)

Strategies use local `mana` variables and `card.cmc` for cost checks. Tax effects
like Trinisphere must be enforced **before** strategy dispatch, not inside strategies.

**Problem:** `opp_can_cast()` correctly applied Trinisphere, but strategies bypass it
entirely — they check `mana >= card.cmc` and deduct `card.cmc` directly. With 4+ mana,
cheap spells were cast at original cost, making Trinisphere useless.

**Solution:** In `play_turn()` and `protagonist_turn()`, temporarily raise `card.cmc`
to `max(cmc, 3)` for all cheap spells in hand before strategy dispatch, restore after.
This way ALL strategy functions automatically pay the Trinisphere tax without any
per-strategy changes.

**Also watch for:**
- `mana_cost` dict vs `cmc` — some code reads `sum(mana_cost.values())` instead of
  `cmc`. The `_ritual_cost()` fix uses `max(sum(mana_cost), cmc)` to respect both.
- Alternate costs (FoW, FoN, Daze) — must be blocked under Trinisphere since they
  pay 0 mana, not meeting the 3-mana minimum (CR 601.2f).
- LED costs 3 under Trinisphere (artifact spell, CMC 0 → taxed to 3). Kill conditions
  must check `led_castable` (can afford the taxed cost), not just `led` (in hand).
- Any new tax effect (e.g. Thalia, Sphere of Resistance) needs the same pre-dispatch
  CMC adjustment pattern. Do NOT rely on strategies calling `opp_can_cast()`.

### Strategy Must Model Win Conditions

**Problem:** Prison had Painter's Servant + Grindstone in the decklist but the strategy
never deployed them. Prison could only win via TKS beatdown or T15 timeout.
WR was 5-34% across matchups.

**Solution:** Added Painter + Grindstone combo deployment and Karn wishes for combo
pieces. WR jumped to 17-65%.

**Rule:** Every deck's strategy function MUST actively deploy its win conditions.
If a card is in the decklist, the strategy must know how to cast it. Audit checklist:
- Does the strategy deploy every nonland card in the deck?
- Does the strategy have a path to actually win (not just lock/stall)?
- Are combo pieces deployed in the correct order?
- Does Karn/tutor fetch the right piece based on board state?

### Decklist Realism

**Problem:** Prison ran 36 lands (24 Wastes) and only 24 nonlands — no real Legacy
deck runs that ratio. Result: flooded every game, couldn't assemble lock + combo.

**Solution:** Reduced to 24 lands / 36 nonlands with fast mana (Lotus Petal, Grim
Monolith) enabling T1-T2 lock pieces.

**Rule:** Decklists should approximate real tournament lists:
- 20-24 lands for most decks (combo decks can go lower with fast mana)
- Cross-check against mtgtop8.com / mtggoldfish.com for realistic ratios

### Meta Share Tiers

Meta-weighted WR uses only T1+T2 opponents, weighted by meta share:
- **T1 (>=5%):** ocelot (12%), dimir (6%), dimir_b (5%), lands (6%), oops (6%),
  doomsday (6%), prison (6%), ur_delver (6%)
- **T2 (3-4%):** sneak_a, sneak_b, show, painter, eight_cast, uwx
- `top_tier=N` is deterministic: always takes the top N decks by meta share
- Shares based on Legacy Showcase Qualifier + Challenge 32 (2026-04-04/05)

## Logging

Logs are saved to `replays/{deck1}_vs_{deck2}_s{seed}.txt` and committed after every run.

## Reproducibility

Use `random.seed(N)` or `-s N` flag for deterministic results:
```python
import random; random.seed(42)
r = run_game('storm', 'burn')  # same result every time with seed 42
```

---

## Three Products — Output Standards

### 1. Meta Matrix (HTML + JSX)

**Template**: Use `templates/reference_meta_matrix.html` as the canonical template.
Never rebuild from scratch — replace the 5 data constants (D, DA, C, I, ARCH).

**Required JS functions** (all must exist before `render()`):
`pills(cards,color)`, `wc(w)`, `tc(w)`, `muc(w)`, `getCT()`, `tierOf(w)`,
`tierTag(w)`, `getWR(d)`, `closeDet()`

After any rebuild, verify: `grep 'function pills' output.html` — if missing, inject it.

**Data layers**: D (matchup WRs), DA (deck profiles), C (card-level stats),
I (interaction events), ARCH (archetype map).

**Weighted WR**: T1+T2 opponents only (flat ≥50%). Thresholds: 58/48/33 weighted, 65/50/35 flat.

### 2. Deck Guides (HTML)

**Generator**: `python3 gen_guides.py` produces all 37 guides in ~30s (500 games/deck).
Burn is hand-crafted (51KB) and skipped by the generator. Reference: `templates/reference_deck_guide.html`

**Design**: Light theme, white bg, system sans-serif, max-width 960px.

**All 7 required features** (generator produces all of these):
- **Hero**: 4-col grid (Format, WR flat+weighted, Rank/Tier, Best/Worst)
- **Two-column**: Decklist + role badges left, findings right
- **Card role badges**: threat, burn, engine, reach, finisher, removal, draw, tutor, hate, flex
- **Scryfall hovers**: `class="card-tip" data-card="Card Name"` + JS tooltip from api.scryfall.com
- **Kill turn chart**: CSS flex bars from real sim data
- **Hand archetype WR**: Horizontal bars with baseline marker (500 games)
- **Real sim hands**: 2 winning + 1 losing with game logs
- **Provenance footer**: sim params, deck count, game count, date

**Metagame strategy** (7 visual components — NO text walls):
1. Archetype WR bars
2. Tournament histogram (8-round, 10K sims)
3. Prey / Competitive / Danger triptych cards
4. Tournament arc segmented bar (R1-3 bank → R4-6 gauntlet → R7-8 top)
5. Delta proof chart (flat→weighted drop)
6. Danger matchup cards (red header + ✗/⚡/★ bullets)
7. Game plan from deck_agg.json

**Key API note**: `run_game()` returns `p1_opening_hand` as list of **strings** (not Card objects).
Do NOT call `.name` on them — use directly.

**Do NOT inject decklists into Burn** — it already has a hand-crafted two-column layout.
The generator skips Burn (`if dk == 'burn': continue`).

### 3. Bo3 Replayer (HTML)

**API**: `generate_html(opponent, seeds=[42,99,7], protagonist='deck')`
**Reference**: See `skills/mtg-bo3-replayer/`

Design:
- Light theme, max-width 920px
- 17 play categories (zero 'other')
- Turn sections: Draw (pill) → Hand (N pills) → Plays → Combat → Board
- Combat detail boxes: `⚔ Creature` + `N dmg → life X → Y`
- Reasoning hidden by default, `·` toggle to reveal
- Response badges: `⚡ Player` for counterspells
- Legend box at top, result card with stats
- 6 board zones, mulligan reasoning, strategic narrative, life chart SVG

## Never

- Never re-run the matrix if results/*.json files exist (unless explicitly asked)
- Never use MTGSimManu imports — this is MTGSimClaude (Legacy)
- Never produce text-wall metagame sections — use the 7 visual components
- Never show reasoning by default in replayer — use toggle
- Never skip the provenance footer
- Never rebuild matrix HTML from scratch — use template + swap data constants
- Never forget pills() function in matrix HTML
- Never inject a decklist into Burn — it has a hand-crafted two-column layout already
- Never call .name on p1_opening_hand items — they're already strings
- Never generate guides without all 7 features (two-col, kt, arch, hands, findings, hover, meta)
