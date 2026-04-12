# MTGSimClaude — AI Architecture & Structure Guide

> **Last updated:** 2026-04-12 | **See also:** `PLANNING_REFERENCE.md` for benchmarks, backlog, and cross-pollination roadmap.

## File Structure

```
MTGSimClaude/
├── sim.py                 # Game loop: run_game(), run_sweep(), run_meta_matrix(), Bo3
├── engine.py              # Turn execution: play_turn(), 19 strategy fns, counters, combat
├── game.py                # State: GameState, PlayerState, get_attackers(), mulligan
├── rules.py               # Immutable: Card, Permanent, LandPermanent, ManaPool, MTGRules
├── cards.py               # Card builders: make_*_deck(), DECKS dict, MATCHUP_META
├── config.py              # Constants: CardRoles, MatchupCategory, InteractionParams
├── interaction.py         # classify_threat(), best_proactive_target(), answer selection
├── interaction_model.py   # Hypergeometric FoW priors, save rates, P(at_least_one)
├── gameplan.py            # Stub: GAMEPLANS dict, assess(), active_goal()
├── deck_registry.py       # Auto-discovery of deck modules in decks/
├── import_deck.py         # Paste MTGGoldfish decklist → auto-generate deck module
├── parallel.py            # Multiprocessing ~3x speedup for matrix/field runs
├── meta_results.py        # Save/load matrix JSON, timestamped persistence
├── meta_audit.py          # Post-sim outlier detection + strategy audit
├── game_replay.py         # HTML Bo3 replayer generator (17 play categories)
├── verbose_table.py       # Card-level data extraction from verbose logs
├── run_meta.py            # CLI: --list, --deck, --matchup, --matrix, --verbose, --trace
├── hypothesis_testing.py  # Statistical analysis tools
├── decks/                 # 38 deck modules (22 full + 17 proxy), auto-discovered
├── skills/                # 4 reusable Claude skills
├── templates/             # reference_meta_matrix.html, reference_deck_guide.html
├── results/               # Matrix JSON, trace logs, replay HTML
├── CLAUDE.md              # Quick-start for Claude Code
└── PLANNING_REFERENCE.md  # Planning-mode context (benchmarks, backlog, proposals)
```

**Line counts (core):**

| File | Lines | Role |
|------|-------|------|
| engine.py | 5,038 | Turn execution, all AI strategy |
| cards.py | 2,068 | Card database, deck builders |
| sim.py | 1,804 | Game loop, sweeps, matrix, Bo3 |
| game.py | 1,064 | State management, mulligan, attackers |
| rules.py | 678 | MTG rules, Card/Permanent types |
| config.py | 380 | Constants, matchup categories |
| interaction.py | 249 | Threat classification, counter selection |
| interaction_model.py | 213 | Hypergeometric priors, save rates |
| **Total core** | **11,494** | |
| decks/ (38 modules) | ~14,000 | Strategy code |

## Simulation Flow

```
sim.py: run_game(deck1, deck2)
  ├── london_mulligan() both players
  ├── coin flip → who goes first
  └── for turn 1..15:
        ├── play_turn(gs, turn, 'p1')    ← SYMMETRIC — same function for both
        │     ├── untap, clear summoning sickness
        │     ├── draw (+ Bowmasters trigger check)
        │     ├── land drop
        │     ├── ManaManager.refresh(player) → build mana budget
        │     ├── apply_lock_effects() → Trinisphere/Thalia CMC adjustment
        │     ├── dispatch to _strategy_XXX() based on deck key
        │     │     └── each spell → try_reactive_counter() check
        │     ├── combat_declare() → get_attackers() → resolve_combat()
        │     ├── restore_lock_effects()
        │     └── EOT: Vial deploy, Tamiyo flip, Eidolon damage
        │
        └── play_turn(gs, turn, 'p2')    ← SAME function, other player slot
```

**Key principle:** play_turn() is symmetric. Both p1 and p2 use the same turn function. Strategy dispatch is by deck key, not player slot.

## AI Decision Model: Rule-Tree Dispatch

19 hand-coded strategy functions with 787 if/elif branches (avg 41 per strategy). Decisions are binary — first match wins, no comparison between alternatives.

| Metric | Value |
|--------|-------|
| Strategy functions | 19 |
| Total if/elif branches | 787 |
| Unique card tags | 73 |
| Property-based checks | 76 |
| Tag-based checks | 184 |

### Storm example (how a strategy function works)

```
_strategy_storm():
  1. Cast cantrips if affordable
  2. Simulate ritual chain mana (Trinisphere tax, Chalice blocks, LED)
  3. Test 6 kill conditions (kill_A..kill_F) — first match wins
  4. Safety check: Veil active? No FoW? Desperate?
  5. Execute: Veil → kill spell → Flusterstorm backup
```

### Rule tree vs EV scoring (Modern project comparison)

| Dimension | Legacy (rule tree) | Modern (EV scoring) |
|-----------|-------------------|---------------------|
| Speed | **2.5ms/game** (91x faster) | 227ms/game |
| Scaling | O(decks) — new fn per deck | O(1) — new weights only |
| Combo modeling | **Excellent** (explicit kill lines) | Weak (calibration bugs) |
| Fair-deck play | Weak (first match wins) | **Strong** (all options compete) |

## Counter Logic (Unified)

`try_reactive_counter()` — symmetric, works for either player:

```
1. Protection: Veil of Summer? Allosaurus Shepherd? → can't counter
2. Scan defender hand for counters (O(1) tag lookup)
3. Trinisphere → disable FoW/FoN/Daze alternate costs
4. Skip cantrips (not worth countering)
5. classify_threat() → MUST (4) / HIGH (3) / MEDIUM (2) / LOW (1)
6. Priority: FoN → FoW → Counterspell → Flusterstorm → Pyroblast → Daze
7. Hand-size gates: CS needs 4+ cards, Flusterstorm needs 3+
```

## Threat Classification (interaction.py)

Property-based, not tag-based:
```
MUST_ANSWER_NOW (4): is_combo_piece, win_condition
HIGH (3):            lock_piece, engine, haste, is_mass_removal, cmc >= 5
MEDIUM (2):          is_removal, is_creature (mirror or CMC1)
LOW (1):             cantrips, rituals
```

## Thoughtseize Targeting (interaction.py)

```
win_condition: 100   combo_piece:  90   lock_piece: 80
FoW/FoN:        65   engine:       50   creature3+: 40
removal:        35   ritual:       25   cantrip:    10
```

## Combat System

**get_attackers()** — per-creature EV assessment:
- No blocker → free damage, always attack
- Flying vs no flyers → unblocked
- Favorable/even trade → attack
- Losing trade or deathtouch blocker → don't attack
- Near lethal → attack regardless

**resolve_combat()** — blocker assignment:
- Greedy, largest attacker first
- Favorable trade > even trade > chump (power >= 3 + spare blockers)
- Vial combat ambush for DnT/Boros

## Strategy Functions (all 19)

| Strategy | Archetype | Key mechanics |
|----------|-----------|---------------|
| `_strategy_storm` | Combo | Ritual chain, LED, 6 kill conditions |
| `_strategy_dimir` | Tempo | Creature deployment, counter conservation |
| `_strategy_eldrazi` | Aggro | Chalice, TKS hand disruption |
| `_strategy_show` | Combo | Show and Tell + Emrakul/Omniscience |
| `_strategy_prison` | Lock | Karn wishes, Trinisphere, Bridge |
| `_strategy_lands` | Control | Dark Depths, Wasteland lock |
| `_strategy_oops` | Combo | T1 kill attempts |
| `_strategy_doomsday` | Combo | Doomsday pile |
| `_strategy_reanimator` | Combo | Entomb + Reanimate |
| `_strategy_dnt` | Tax-Aggro | Thalia, Vial, Karakas |
| `_strategy_uwx` | Control | Wrath, Mentor tokens |
| `_strategy_painter` | Combo | Painter + Grindstone |
| `_strategy_bug` | Tempo | Wasteland, Thoughtseize |
| `_strategy_dimir_flash` | Tempo | Flash threats, WST |
| `_strategy_boros` | Aggro | Initiative, Vial |
| `_strategy_mardu` | Aggro | Energy, creature curve |
| `_strategy_mono_black` | Aggro | Dark Rit, Hymn |
| `_strategy_ur_aggro` | Aggro | Bolt, Delver |
| `_strategy_elves` | Combo | Natural Order, Craterhoof |

## Key Mechanics

| Mechanic | Location | Implementation |
|----------|----------|----------------|
| Trinisphere | apply_lock_effects() | Pre-dispatch max(cmc, 3). Blocks FoW alternate costs. |
| Thalia tax | ManaManager.effective_cmc() | Noncreature spells +1 |
| Chalice | opp_can_cast() | spell_blocked_by_chalice(cmc) |
| Bridge | get_attackers() | Hand size blocks power > N |
| FoW/FoN | try_reactive_counter() | Pitch blue, _select_fow_pitch() |
| Daze | try_reactive_counter() | Return Island, pay-through probability |
| Veil | try_reactive_counter() | Blanks all counters for the turn |
| Wasteland | strategy functions | Priority: dual > fetch > utility |
| Bowmasters | bowmasters_triggers() | 1 ping per draw, grow Orc Army |
| Narset | game.py draw() | 1 draw per turn when active |

## Deck Plugin System

Zero engine edits to add a deck:

```bash
echo "4 Delver of Secrets..." | python3 import_deck.py "My Deck" aggro,tempo
# deck_registry.py auto-discovers at import
```

## Performance

| Metric | Value |
|--------|-------|
| Per game | 2.5ms |
| Full matrix (n=30) | 94s |
| Tests | 137/137 |
| Avg game | 5.7 turns |

## Evolution Roadmap

See PLANNING_REFERENCE.md §8-9. Key adoptions from Modern:
1. Strategic logger — --trace with decision reasoning
2. Clock-based evaluation — clock.py (328 lines)
3. Bayesian hand inference — bhi.py (275 lines)
4. Declarative gameplans — JSON-driven phase tracking
